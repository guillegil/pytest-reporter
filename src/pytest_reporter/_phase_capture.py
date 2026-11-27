"""Phase log capture helpers — serialize, write tables, record, write phase files."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ._context import sanitize_path_component
from ._json_writer import write_failure_log, write_phase_log, write_procedure_json
from ._log_capture import phase_entries, phase_tables
from ._table import build_table_artifact_html

if TYPE_CHECKING:
    import pytest

    from .reporter import Reporter


def verify_checks(report: object) -> list[dict[str, Any]]:
    """The pytest-verifier checks a phase report carries (``report.verify_checks``).

    pytest-verifier puts the checks it judged at the end of a phase on that
    phase's report. They are JSON-safe, so they survive pytest-xdist, and checks
    nested in a composite are inside their parent. Reading the attribute needs
    no import: without pytest-verifier it is simply absent.

    Args:
        report: A ``TestReport``.

    Returns:
        The phase's check dicts (empty when there are none).
    """
    checks = getattr(report, "verify_checks", None)
    if not isinstance(checks, (list, tuple)):
        return []
    return [dict(c) for c in checks if isinstance(c, dict)]


def note_verify_checks(reporter: Reporter, report: object) -> None:
    """Add a phase report's verifier checks to the attempt running now."""
    nodeid = str(getattr(report, "nodeid", ""))
    checks = verify_checks(report)
    if checks:
        reporter._attempt_checks.setdefault(nodeid, []).extend(checks)


def write_table_artifacts(report: object, run_dir: Path) -> None:
    """Save the tables logged in a phase as HTML files in ``run_dir/artifacts/``.

    Args:
        report: The phase's ``TestReport`` (its ``reporter_log_tables``).
        run_dir: The run (or retry attempt) directory.
    """
    tables = phase_tables(report)  # type: ignore[arg-type]
    if not tables:
        return
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for table in tables:
        try:
            html = build_table_artifact_html(
                str(table["name"]), list(table["columns"]), list(table["rows"])
            )
            name = Path(str(table["artifact_name"])).name
            (artifacts_dir / name).write_text(html, encoding="utf-8")
        except (KeyError, TypeError, ValueError, OSError):
            continue


def capture_phase_logs(reporter: Reporter, report: pytest.TestReport) -> None:
    """Capture log entries for one test phase and write all related files.

    1. Write the tables logged in the phase as artifacts.
    2. ``collector.record_phase(entries=…)`` with the phase's logging records
       (``report.reporter_log``, set by ``_log_capture.LogCapture``).
    3. Write ``{phase}.log.json``.
    4. Write failure log for original call-phase failures (not retries).

    Args:
        reporter: The active ``Reporter`` instance.
        report: The ``TestReport`` for the phase being recorded.
    """
    nodeid = report.nodeid
    run_dir = reporter._get_run_dir(nodeid)
    write_table_artifacts(report, run_dir)

    # Record phase data with the logging records captured in the phase
    reporter.collector.record_phase(report, entries=phase_entries(report))
    note_verify_checks(reporter, report)

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


PHASES = ("setup", "call", "teardown")


def copy_failed_phase_logs(reporter: Reporter, nodeid: str, run_dir: Path) -> None:
    """Copy a failed run's phase logs into ``failures/``.

    When a phase of the run's first attempt failed (a failed call, or an error
    in setup or teardown), its ``setup.log.json``, ``call.log.json`` and
    ``teardown.log.json`` are copied to ``failures/<function>_<run>_<phase>.log.json``,
    next to ``<function>_<run>_error.log``. Retry attempts are not copied.

    Args:
        reporter: The active ``Reporter`` instance.
        nodeid: The test node ID.
        run_dir: The run directory holding the phase logs.
    """
    phases = [reporter.collector.get_phase(nodeid, when) for when in PHASES]
    if not any(phase is not None and phase.outcome == "failed" for phase in phases):
        return
    run_info = reporter.collector.get_run_info(nodeid)
    prefix = f"{sanitize_path_component(run_info.function_name)}_{run_info.run_id}"
    failures_dir = reporter.context.failures_dir
    for when in PHASES:
        source = run_dir / f"{when}.log.json"
        if not source.is_file():
            continue
        try:
            failures_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, failures_dir / f"{prefix}_{when}.log.json")
        except OSError:
            continue


def write_run_finish_files(
    reporter: Reporter,
    nodeid: str,
    location: tuple[str, int | None, str],  # noqa: ARG001
) -> None:
    """Write per-run finish files (procedure.json, parameters.json, checks.json).

    A failed first attempt also gets its phase logs copied into ``failures/``
    (``copy_failed_phase_logs``).

    Gated on ``nodeid not in reporter._finished_runs``. Keeps the run's
    procedure (from stepdoc's steps) and its pytest-verifier checks for the
    HTML report.

    Args:
        reporter: The active ``Reporter`` instance.
        nodeid: The test node ID.
        location: The pytest location tuple ``(file, lineno, testname)``.
    """
    from ._json_writer import write_checks_json, write_parameters_json

    run_info = reporter.collector.get_run_info(nodeid)
    run_dir = reporter._get_run_dir(nodeid)

    # Write procedure.json
    procedure_data = reporter.steps.procedure(nodeid)
    reporter._procedures[nodeid] = procedure_data
    write_procedure_json(run_dir / "procedure.json", procedure_data)

    # Write parameters.json (only in main run dir, not retries)
    if nodeid not in reporter._retry_paths:
        write_parameters_json(run_dir / "parameters.json", run_info)
        copy_failed_phase_logs(reporter, nodeid, run_dir)

    # Verification checks from pytest-verifier (report.verify_checks)
    checks = reporter._attempt_checks.pop(nodeid, [])
    if checks:
        reporter._check_results[nodeid] = checks
        write_checks_json(run_dir / "checks.json", checks)
    reporter.steps.discard(nodeid)

    # Create artifacts directory
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
