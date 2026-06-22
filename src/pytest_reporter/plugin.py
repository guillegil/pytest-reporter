"""Hook registrations -- the entry point for pytest plugin discovery."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from . import _hookspecs
from ._context import RunContext
from ._logger import Logger
from .reporter import Reporter

if TYPE_CHECKING:
    from pytest import Config, Parser


def pytest_addhooks(pluginmanager: pytest.PytestPluginManager) -> None:
    """Register pytest-reporter hookspecs early, before conftest collection."""
    pluginmanager.add_hookspecs(_hookspecs.ReporterSpec)


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
    reporter: Reporter | None = request.config.pluginmanager.get_plugin("pytest_reporter")
    if reporter is None:
        # No report dir configured -- return a no-op logger
        return Logger()

    # Get or create logger for this test item
    item = request.node
    logger = getattr(item, "_reporter_logger", None)
    if logger is None:
        logger = Logger()
        item._reporter_logger = logger  # dynamic attribute on pytest.Item
    return logger


@pytest.fixture(scope="session")
def session_log(request: pytest.FixtureRequest) -> Logger:
    """Provide a structured tree-based logger for session-level logging.

    Session-scoped fixtures use this to produce structured logs that
    are written to session.log.json at the end of the test run.
    """
    reporter: Reporter | None = request.config.pluginmanager.get_plugin("pytest_reporter")
    if reporter is None:
        return Logger()

    return reporter.session_logger


@pytest.fixture
def report_artifacts(request: pytest.FixtureRequest) -> Path:
    """Provide a writable Path to the current test run's artifacts dir.

    Tests can save files here and they will be included in the HTML report.
    Returns a temporary directory when --report-dir is not active.
    """
    reporter: Reporter | None = request.config.pluginmanager.get_plugin("pytest_reporter")
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


@pytest.fixture(scope="session")
def report_dashboard(request: pytest.FixtureRequest) -> list[object]:
    """Provide a mutable session-level list for dashboard group specs.

    Session-scoped fixtures append :class:`~pytest_reporter._types.DashboardGroupSpec`
    dicts here; they are merged with ``pytest_reporter_dashboard`` hook
    contributions and embedded in the HTML report at session end.  Fixture
    values are appended last (after hook contributions) so they take precedence
    in ordering.

    When ``--report-dir`` is not active (reporter inactive), returns a
    throwaway list so callers never crash.

    Returns:
        A mutable list of raw group spec dicts shared across the session.
    """
    reporter: Reporter | None = request.config.pluginmanager.get_plugin("pytest_reporter")
    if reporter is None:
        # Reporter inactive (no --report-dir) — return a throwaway list
        return []
    return reporter.dashboard_store


@pytest.fixture(scope="session")
def report_metadata(request: pytest.FixtureRequest) -> dict[str, dict[str, object]]:
    """Provide a mutable session-level metadata dict for the HTML Report tab.

    Tests and session-scoped fixtures populate this dict during setup; the
    values are merged with hook contributions and embedded in the HTML report
    at session end.  Fixture values override hook values on key collision
    within the same section.

    When ``--report-dir`` is not active (reporter inactive), returns a
    throwaway dict so callers never crash.

    Returns:
        A mutable ``{section: {label: value}}`` dict shared across the session.
    """
    reporter: Reporter | None = request.config.pluginmanager.get_plugin("pytest_reporter")
    if reporter is None:
        # Reporter inactive (no --report-dir) -- return a throwaway dict
        return {}
    return reporter.metadata_store


@pytest.fixture(scope="session")
def report_seed(request: pytest.FixtureRequest) -> dict[str, object]:
    """Provide a mutable seed holder for the HTML Report tab's Seed row.

    Set ``report_seed["value"]`` to an ``int`` or ``str`` to override the
    auto-detected RNG seed (from ``pytest_reporter_seed`` hook or
    ``pytest_strategy``).  Manual fixture value takes highest precedence.

    When ``--report-dir`` is not active (reporter inactive), returns a
    throwaway dict so callers never crash.

    Example::

        def test_something(report_seed):
            report_seed["value"] = 42  # forces 'Seed: 42' in the report

    Returns:
        A mutable ``{"value": <int|str>}`` dict shared across the session.
    """
    reporter: Reporter | None = request.config.pluginmanager.get_plugin("pytest_reporter")
    if reporter is None:
        # Reporter inactive (no --report-dir) -- return a throwaway dict
        return {}
    return reporter.seed_store
