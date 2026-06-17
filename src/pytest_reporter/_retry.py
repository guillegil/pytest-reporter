"""Retry protocol — full pytest_runtest_protocol body for the retry engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from ._json_writer import write_failure_log, write_phase_log, write_procedure_json
from ._logger import Logger
from ._phase_capture import flush_table_artifacts
from ._procedure import ProcedureTracker, _set_tracker
from ._types import PhaseData, RetryData

if TYPE_CHECKING:
    import pytest

    from .reporter import Reporter


def run_with_retries(
    reporter: Reporter,
    item: pytest.Item,
    nextitem: pytest.Item | None,
) -> bool | None:
    """Implement the full retry protocol for a single test item.

    Runs the test via ``runtestprotocol(log=False)`` so that phase-log
    entries are captured once (all entries belong to the call phase).
    On first-run failure, retries up to ``reporter.max_retries`` times.
    Dispatches the final reports to pytest's hook system.

    CRITICAL invariants (must not be reordered):
    1. ``_finished_runs`` is populated BEFORE dispatching reports to the hook
       chain — this prevents our own ``logreport``/``logfinish`` hookimpls
       from re-processing the already-written files.
    2. ``log=False`` in ``runtestprotocol`` keeps the logger un-reset between
       phases; all entries accumulate and are captured once, assigned to the
       call phase; setup/teardown get ``[]``.
    3. ``_retry_paths`` is set per attempt and popped after the loop — it gates
       ``parameters.json`` and failure-log writes so they only happen on the
       main (non-retry) path.

    Args:
        reporter: The active ``Reporter`` instance.
        item: The pytest item to run.
        nextitem: The next item (passed to runtestprotocol for teardown scoping).

    Returns:
        ``True`` if the protocol was fully handled here; ``None`` to let pytest
        handle normally (when retries are disabled or item is unregistered).
    """
    if reporter.max_retries <= 0:
        return None  # Let pytest handle normally

    nodeid = item.nodeid
    if nodeid not in reporter.collector._run_map:
        return None

    from _pytest.runner import runtestprotocol

    # Run the test normally first (log=False so we control report dispatch)
    reports = runtestprotocol(item, nextitem=nextitem, log=False)

    # Process reports: since log=False, the logger was NOT reset between
    # phases.  All entries accumulated during the full run belong to the
    # call phase (setup/teardown only run fixture code, not user code).
    # Capture entries once and assign to the call-phase report.
    logger = reporter._test_loggers.get(nodeid)
    all_entries: list[dict[str, Any]] = []
    if logger is not None:
        all_entries = logger.serialize().get("entries", [])
        run_dir = reporter._get_run_dir(nodeid)
        flush_table_artifacts(logger, run_dir)

    for report in reports:
        entries = all_entries if report.when == "call" else []
        reporter.collector.record_phase(report, entries=entries)
        phase = reporter.collector.get_phase(nodeid, report.when)
        if phase is not None:
            run_dir = reporter._get_run_dir(nodeid)
            write_phase_log(run_dir / f"{report.when}.log.json", phase)
        # Write failure log for call-phase failures
        if (
            report.when == "call"
            and report.failed
            and report.longrepr
            and nodeid not in reporter._retry_paths
        ):
            run_info = reporter.collector.get_run_info(nodeid)
            failure_name = f"{run_info.function_name}_{run_info.run_id}_error.log"
            write_failure_log(
                reporter.context.failures_dir / failure_name,
                nodeid,
                str(report.longrepr),
            )

    # Write per-run files for original execution
    reporter.pytest_runtest_logfinish(nodeid=nodeid, location=item.location)

    # Check if call phase failed
    call_report = None
    for report in reports:
        if report.when == "call":
            call_report = report
            break

    if call_report is None or not call_report.failed:
        # Mark finished BEFORE dispatching to prevent our own
        # logreport hook from re-processing (and overwriting entries)
        reporter._finished_runs.add(nodeid)
        # Dispatch reports to pytest for terminal output
        for report in reports:
            item.config.hook.pytest_runtest_logreport(report=report)
        item.config.hook.pytest_runtest_logfinish(nodeid=nodeid, location=item.location)
        return True

    # Start retry loop
    run_info = reporter.collector.get_run_info(nodeid)
    main_run_dir = reporter.context.run_subdir(
        run_info.file_path, run_info.function_name, run_info.run_id
    )

    retry_data = RetryData(
        max_retries=reporter.max_retries,
        attempts=0,
        original_outcome="failed",
        history=["failed"],
    )

    final_reports = reports  # will be updated if retry succeeds

    for attempt in range(1, reporter.max_retries + 1):
        retry_dir = main_run_dir / "retries" / f"{attempt:02d}"
        retry_dir.mkdir(parents=True, exist_ok=True)

        # Set retry path so writes go to retry subfolder
        reporter._retry_paths[nodeid] = retry_dir

        # Create fresh logger and procedure tracker for retry
        logger = Logger()
        reporter._test_loggers[nodeid] = logger
        item._reporter_logger = logger  # type: ignore[attr-defined]

        tracker = ProcedureTracker()
        reporter._procedure_trackers[nodeid] = tracker
        _set_tracker(tracker)

        # Re-execute the test
        retry_reports = runtestprotocol(item, nextitem=None, log=False)

        # Write retry phase logs directly to disk (don't overwrite collector)
        for report in retry_reports:
            retry_entries: list[dict[str, Any]] = []
            if logger is not None:
                serialized = logger.serialize()
                retry_entries = serialized.get("entries", [])
                flush_table_artifacts(logger, retry_dir)

            end_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            start_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00")) - timedelta(
                seconds=report.duration
            )
            start_time = start_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            retry_phase = PhaseData(
                when=report.when,
                outcome=report.outcome,
                duration=report.duration,
                longrepr=str(report.longrepr) if report.longrepr else None,
                start_time=start_time,
                end_time=end_time,
                entries=retry_entries,
            )
            write_phase_log(retry_dir / f"{report.when}.log.json", retry_phase)

        # Write procedure.json for retry
        procedure_data = tracker.serialize() if tracker else {"steps": []}
        write_procedure_json(retry_dir / "procedure.json", procedure_data)
        (retry_dir / "artifacts").mkdir(parents=True, exist_ok=True)

        _set_tracker(None)

        # Check retry outcome
        retry_call = None
        for report in retry_reports:
            if report.when == "call":
                retry_call = report
                break

        retry_outcome = retry_call.outcome if retry_call else "error"
        retry_data.attempts = attempt
        retry_data.history.append(retry_outcome)

        if retry_outcome == "passed":
            final_reports = retry_reports
            break  # Success!

    # Clean up retry path
    reporter._retry_paths.pop(nodeid, None)

    # Store retry data
    reporter.collector.set_retry_data(nodeid, retry_data)

    # Mark as finished BEFORE dispatching to prevent our hooks from
    # re-processing the reports (which would overwrite original phase data)
    reporter._finished_runs.add(nodeid)

    # Dispatch the FINAL outcome to pytest's hook system
    # This ensures terminal reporter and outcome counters reflect the retry result
    for report in final_reports:
        item.config.hook.pytest_runtest_logreport(report=report)
    item.config.hook.pytest_runtest_logfinish(nodeid=nodeid, location=item.location)

    return True  # We handled the protocol
