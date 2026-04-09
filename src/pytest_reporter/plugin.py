"""Hook registrations -- the entry point for pytest plugin discovery."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ._context import RunContext
from ._logger import Logger
from ._procedure import ProcedureTracker, _set_tracker
from .reporter import Reporter

if TYPE_CHECKING:
    from pytest import Config, Parser


def pytest_addoption(parser: Parser) -> None:
    group = parser.getgroup("reporter", "Reporter options")
    group.addoption(
        "--report-dir",
        dest="report_dir",
        default=None,
        help="Directory for test reports (e.g. --report-dir=reports)",
    )
    group.addoption(
        "--report-retries",
        dest="report_retries",
        type=int,
        default=0,
        help="Maximum retry attempts per failed test (default: 0, disabled)",
    )


def pytest_configure(config: Config) -> None:
    report_dir: str | None = config.getoption("--report-dir", default=None)
    if report_dir:
        # Only register on the controller, not xdist workers
        if not hasattr(config, "workerinput"):
            max_retries: int = config.getoption("--report-retries", default=0)
            context = RunContext(Path(report_dir))
            config.pluginmanager.register(
                Reporter(config, context, max_retries=max_retries),
                "pytest_reporter",
            )


@pytest.fixture
def log(request: pytest.FixtureRequest) -> Logger:
    """Provide a structured tree-based logger for per-test logging.

    Returns a Logger instance whose entries are automatically captured
    by the reporter at the end of each phase (setup, call, teardown).
    """
    reporter: Reporter | None = request.config.pluginmanager.get_plugin(
        "pytest_reporter"
    )
    if reporter is None:
        # No report dir configured -- return a no-op logger
        return Logger()

    # Get or create logger for this test item
    item = request.node
    logger = getattr(item, "_reporter_logger", None)
    if logger is None:
        logger = Logger()
        item._reporter_logger = logger  # type: ignore[attr-defined]
    return logger


@pytest.fixture(scope="session")
def session_log(request: pytest.FixtureRequest) -> Logger:
    """Provide a structured tree-based logger for session-level logging.

    Session-scoped fixtures use this to produce structured logs that
    are written to session.log.json at the end of the test run.
    """
    reporter: Reporter | None = request.config.pluginmanager.get_plugin(
        "pytest_reporter"
    )
    if reporter is None:
        return Logger()

    return reporter.session_logger


@pytest.fixture
def report_artifacts(request: pytest.FixtureRequest) -> Path:
    """Provide a writable Path to the current test run's artifacts dir.

    Tests can save files here and they will be included in the HTML report.
    Returns a temporary directory when --report-dir is not active.
    """
    reporter: Reporter | None = request.config.pluginmanager.get_plugin(
        "pytest_reporter"
    )
    if reporter is None:
        # No report dir configured -- return a tmp path so tests still work
        tmp: Path = request.getfixturevalue("tmp_path")
        return tmp / "artifacts"

    nodeid = request.node.nodeid
    run_info = reporter.collector.get_run_info(nodeid)

    # Check if we're in a retry
    artifacts_base = reporter.get_current_run_dir(nodeid)
    if artifacts_base is None:
        run_dir = reporter.context.run_subdir(
            run_info.file_path, run_info.function_name, run_info.run_id
        )
        artifacts_dir = run_dir / "artifacts"
    else:
        artifacts_dir = artifacts_base / "artifacts"

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir
