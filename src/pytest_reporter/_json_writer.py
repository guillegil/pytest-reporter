"""JSON file writers for all per-test output files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from ._types import (
    LogEntryDict,
    ParamEntry,
    ParametersJson,
    PhaseData,
    PhaseLog,
    RunInfo,
    SessionLog,
    TestLogJson,
)


def _write_json(path: Path, data: Any) -> None:  # noqa: ANN401
    """Write a JSON file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def write_phase_log(path: Path, phase: PhaseData) -> None:
    """Write a setup.log.json, call.log.json, or teardown.log.json file."""
    log = PhaseLog(
        phase=phase.when,
        outcome=phase.outcome,
        start_time=phase.start_time,
        end_time=phase.end_time,
        duration_seconds=round(phase.duration, 4),
        longrepr=phase.longrepr,
        entries=cast(list[LogEntryDict], phase.entries),
    )
    _write_json(path, log)


def write_parameters_json(path: Path, run_info: RunInfo) -> None:
    """Write parameters.json for a test run."""
    params: dict[str, ParamEntry] = {}
    for name, value in run_info.params.items():
        params[name] = ParamEntry(
            type=type(value).__name__,
            value=str(value),
        )
    data = ParametersJson(
        parametrize_id=run_info.parametrize_id,
        params=params,
    )
    _write_json(path, data)


def write_procedure_json(path: Path, procedure_data: dict[str, Any]) -> None:
    """Write procedure.json for a test run."""
    _write_json(path, procedure_data)


def write_test_log_json(path: Path, aggregate: TestLogJson) -> None:
    """Write test.log.json aggregate for a test function."""
    _write_json(path, aggregate)


def write_session_log_json(
    path: Path,
    start_time: str,
    end_time: str,
    duration_seconds: float,
    entries: list[dict[str, Any]],
) -> None:
    """Write session.log.json to the run root directory."""
    data = SessionLog(
        phase="session",
        start_time=start_time,
        end_time=end_time,
        duration_seconds=round(duration_seconds, 4),
        entries=cast(list[LogEntryDict], entries),
    )
    _write_json(path, data)


def write_failure_log(path: Path, nodeid: str, longrepr: str) -> None:
    """Write an error log file to the failures directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"Test: {nodeid}\n{'=' * 60}\n{longrepr}\n"
    path.write_text(content, encoding="utf-8")
