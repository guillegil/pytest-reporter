"""Phase log capture helpers — serialize, write tables, record, write phase files."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ._context import sanitize_path_component
from ._json_writer import write_failure_log, write_phase_log, write_procedure_json
from ._table import build_table_artifact_html

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from ._logger import Logger
    from .reporter import Reporter


def flush_table_artifacts(logger: Logger, run_dir: Path) -> None:
    """Write any pending table HTML artifacts from the logger and reset it.

    Writes each table payload as a self-contained HTML file in
    ``run_dir/artifacts/``, then calls ``logger.reset()`` so the next phase
    starts with an empty entry list.

    Args:
        logger: The active per-test (or per-retry) logger instance.
        run_dir: The run directory whose ``artifacts/`` sub-directory will
            receive the table HTML files.
    """
    table_payloads = logger.get_table_payloads()
    if table_payloads:
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        for _seq, payload in table_payloads.items():
            html = build_table_artifact_html(payload.name, payload.columns, payload.rows)
            (artifacts_dir / payload.artifact_name).write_text(html, encoding="utf-8")
    logger.reset()


def capture_phase_logs(reporter: Reporter, report: pytest.TestReport) -> None:
    """Capture log entries for one test phase and write all related files.

    Ordering (must be preserved exactly):
    1. Serialize logger → capture entries.
    2. Write table artifacts and reset logger (``flush_table_artifacts``).
    3. ``collector.record_phase(entries=…)`` — entries captured *before* reset.
    4. Write ``{phase}.log.json``.
    5. Write failure log for original call-phase failures (not retries).

    Args:
        reporter: The active ``Reporter`` instance.
        report: The ``TestReport`` for the phase being recorded.
    """
    nodeid = report.nodeid
    logger = reporter._test_loggers.get(nodeid)
    entries: list[dict[str, Any]] = []
    if logger is not None:
        serialized = logger.serialize()
        entries = serialized.get("entries", [])

        # Write table artifacts before resetting the logger
        run_dir = reporter._get_run_dir(nodeid)
        flush_table_artifacts(logger, run_dir)

    # Record phase data with entries
    reporter.collector.record_phase(report, entries=entries)

    run_dir = reporter._get_run_dir(nodeid)

    # Write phase log immediately
    phase = reporter.collector.get_phase(nodeid, report.when)
    if phase is not None:
        write_phase_log(run_dir / f"{report.when}.log.json", phase)

    # Write failure log (only for original failures, not retries)
    if (
        report.when == "call"
        and report.failed
        and report.longrepr
        and nodeid not in reporter._retry_paths
    ):
        run_info = reporter.collector.get_run_info(nodeid)
        safe_func = sanitize_path_component(run_info.function_name)
        failure_name = f"{safe_func}_{run_info.run_id}_error.log"
        write_failure_log(
            reporter.context.failures_dir / failure_name,
            nodeid,
            str(report.longrepr),
        )


def write_run_finish_files(
    reporter: Reporter,
    nodeid: str,
    location: tuple[str, int | None, str],
    get_check_results: Callable[..., list[dict[str, Any]]] | None = None,
) -> None:
    """Write per-run finish files (procedure.json, parameters.json) and clean up.

    Gated on ``nodeid not in reporter._finished_runs``.  Also captures
    verification check results from pytest-verify and resets the active tracker.

    Args:
        reporter: The active ``Reporter`` instance.
        nodeid: The test node ID.
        location: The pytest location tuple ``(file, lineno, testname)``.
        get_check_results: The ``get_check_results`` callable from
            ``pytest_verify``, or ``None`` when the plugin is absent.  The
            caller (``reporter.py``) holds the module-level reference so that
            monkeypatching via ``monkeypatch.setattr(reporter_mod,
            "get_check_results", ...)`` continues to work as expected.
    """
    from ._json_writer import write_parameters_json
    from ._procedure import _set_tracker

    run_info = reporter.collector.get_run_info(nodeid)
    run_dir = reporter._get_run_dir(nodeid)

    # Write procedure.json
    tracker = reporter._procedure_trackers.get(nodeid)
    procedure_data = tracker.serialize() if tracker else {"steps": []}
    write_procedure_json(run_dir / "procedure.json", procedure_data)

    # Write parameters.json (only in main run dir, not retries)
    if nodeid not in reporter._retry_paths:
        write_parameters_json(run_dir / "parameters.json", run_info)

    # Capture verification check results from pytest-verify public API
    if get_check_results is not None:
        item = reporter._items.get(nodeid)
        if item is not None:
            checks = get_check_results(item)
            if checks:
                reporter._check_results[nodeid] = checks

    # Create artifacts directory
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    # Clean up the active tracker
    _set_tracker(None)
