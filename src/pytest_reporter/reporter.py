"""Reporter -- main orchestrator that wires hooks to writers."""

from __future__ import annotations

import shutil
import time
import warnings
from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from ._collector import DataCollector
from ._console_capture import TeeFile, finalize_capture, install_capture
from ._context import RunContext
from ._html_builder._degraded import build_degraded_report
from ._json_writer import write_session_log_json, write_test_log_json
from ._junit_writer import write_junit_xml
from ._logger import Logger
from ._phase_capture import capture_phase_logs, write_run_finish_files
from ._report_builder import build_html_data
from ._retry import run_with_retries
from ._safety import guard, guard_void
from ._stepdoc import StepCollector
from ._strategies import StrategyExport
from ._symlinks import update_latest_copy
from ._tabs import ReportTabs

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import Config, Item, Session, TestReport


class Reporter:
    """Orchestrates data collection and report generation."""

    def __init__(self, config: Config, context: RunContext, *, max_retries: int = 0) -> None:
        self.config = config
        self.context = context
        self.collector = DataCollector()
        self.session_logger = Logger()
        self.max_retries = max_retries
        self._tee: TeeFile | None = None
        self._start_time: float = 0.0
        self._session_start_iso: str = ""
        self._finished_runs: set[str] = set()
        # stepdoc steps of each test attempt (the Procedure tab)
        self.steps = StepCollector()
        # pytest-strategies' run export: where it is written, and the document
        # read from it when the session ends (strategies.vectors.json)
        self.strategies = StrategyExport(config, context.run_dir)
        self.strategy_export: dict[str, Any] | None = None
        # procedure.json of each finished run (first attempt): nodeid -> dict
        self._procedures: dict[str, dict[str, Any]] = {}
        # Per-test loggers: nodeid -> Logger
        self._test_loggers: dict[str, Logger] = {}
        # Current retry write paths: nodeid -> Path (for retry subfolder)
        self._retry_paths: dict[str, Path] = {}
        # pytest-verifier checks of each run (first attempt), from
        # report.verify_checks: nodeid -> list[dict]
        self._check_results: dict[str, list[dict[str, Any]]] = {}
        # Checks of the attempt running now: nodeid -> list[dict]
        self._attempt_checks: dict[str, list[dict[str, Any]]] = {}
        # Custom HTML tabs of the attempt running now: nodeid -> ReportTabs
        self._tabs: dict[str, ReportTabs] = {}
        # Item references for stash access: nodeid -> Item
        self._items: dict[str, Item] = {}
        # Mutable metadata dict populated via report_metadata fixture or hook
        self.metadata_store: dict[str, dict[str, Any]] = {}
        # Mutable list populated via report_dashboard fixture
        self.dashboard_store: list[object] = []
        # Mutable dict for manual seed override via report_seed fixture
        # Set report_seed["value"] = <int|str> to override auto-detected seed.
        self.seed_store: dict[str, object] = {}

    def get_current_run_dir(self, nodeid: str) -> Path | None:
        """Get the current write directory for a test (retry-aware)."""
        return self._retry_paths.get(nodeid)

    def tabs_for(self, nodeid: str) -> ReportTabs:
        """The custom tabs of the attempt of a test that is running now.

        Args:
            nodeid: The test's node ID.

        Returns:
            The attempt's ``ReportTabs``; one that saves nothing for a test the
            reporter does not know.
        """
        tabs = self._tabs.get(nodeid)
        if tabs is None:
            tabs = ReportTabs()
            if nodeid in self.collector._run_map:
                tabs = self._tabs[nodeid] = ReportTabs(self._get_run_dir(nodeid) / "tabs")
        return tabs

    def _get_run_dir(self, nodeid: str) -> Path:
        """Get the write directory for a test, considering retries."""
        retry_path = self._retry_paths.get(nodeid)
        if retry_path is not None:
            return retry_path
        run_info = self.collector.get_run_info(nodeid)
        return self.context.run_subdir(run_info.file_path, run_info.function_name, run_info.run_id)

    # ------------------------------------------------------------------
    # Hook shells — thin wrappers that delegate to _do_* via guard/guard_void
    # ------------------------------------------------------------------

    def pytest_sessionstart(self, session: Session) -> None:
        """Hook shell: crash-safe wrapper around _do_sessionstart."""
        guard_void("pytest_sessionstart", lambda: self._do_sessionstart(session))

    def pytest_collection_modifyitems(
        self,
        session: Session,
        config: Config,
        items: list[Item],
    ) -> None:
        """Hook shell: crash-safe wrapper around _do_collection_modifyitems."""
        guard_void(
            "pytest_collection_modifyitems",
            lambda: self._do_collection_modifyitems(session, config, items),
        )

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item: Item) -> None:
        """Hook shell: crash-safe wrapper around _do_runtest_setup."""
        guard_void("pytest_runtest_setup", lambda: self._do_runtest_setup(item))

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_teardown(self, item: Item) -> None:
        """Ask conftests and plugins for the test's custom tabs, fixtures still alive."""
        guard_void("pytest_reporter_test_tabs", lambda: self._ask_for_tabs(item))

    def _ask_for_tabs(self, item: Item) -> None:
        """Call each ``pytest_reporter_test_tabs`` implementation on its own.

        One that raises costs only its own tabs, and nothing it raises reaches
        the test: this runs inside the test's teardown, where even
        ``pytest.skip()`` would leave the fixtures alive and fail the next test.
        """
        tabs = self.tabs_for(item.nodeid)
        given = {"item": item, "tabs": tabs}
        hook = item.config.hook.pytest_reporter_test_tabs
        # get_hookimpls() is in registration order; pluggy calls the last first
        for impl in reversed(hook.get_hookimpls()):
            if impl.hookwrapper or getattr(impl, "wrapper", False):
                continue
            try:
                impl.function(**{name: given[name] for name in impl.argnames})
            except (KeyboardInterrupt, SystemExit, pytest.exit.Exception):
                raise
            except BaseException as exc:  # noqa: BLE001 - skip/fail are not Exceptions
                warnings.warn(
                    f"pytest-reporter: pytest_reporter_test_tabs of {impl.plugin_name} "
                    f"failed and was skipped: {type(exc).__name__}: {exc}",
                    stacklevel=2,
                )

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        """Hook shell: crash-safe wrapper around _do_runtest_logreport."""
        guard_void("pytest_runtest_logreport", lambda: self._do_runtest_logreport(report))

    def pytest_runtest_logfinish(
        self,
        nodeid: str,
        location: tuple[str, int | None, str],
    ) -> None:
        """Hook shell: crash-safe wrapper around _do_runtest_logfinish."""
        guard_void(
            "pytest_runtest_logfinish",
            lambda: self._do_runtest_logfinish(nodeid, location),
        )

    @pytest.hookimpl(optionalhook=True)
    def pytest_stepdoc_step_started(self, item: Item, step: Any) -> None:  # noqa: ANN401
        """stepdoc hook: a step started (only called while stepdoc records)."""
        guard_void("pytest_stepdoc_step_started", lambda: self.steps.started(item, step))

    @pytest.hookimpl(optionalhook=True)
    def pytest_stepdoc_step_finished(self, item: Item, step: Any) -> None:  # noqa: ANN401
        """stepdoc hook: a step ended."""
        guard_void("pytest_stepdoc_step_finished", lambda: self.steps.finished(item, step))

    @pytest.hookimpl(optionalhook=True)
    def pytest_stepdoc_test_doc(self, item: Item, doc: dict[str, str]) -> None:
        """stepdoc hook: the test's docstring, parsed (once, before it runs)."""
        guard_void("pytest_stepdoc_test_doc", lambda: self.steps.test_doc(item, doc))

    @pytest.hookimpl(hookwrapper=True, optionalhook=True)
    def pytest_strategies_export_dir(self, config: Config) -> Generator[None, Any, None]:  # noqa: ARG002
        """pytest-strategies hook (4.3+): the folder of its run export.

        A wrapper, so every other answer comes first: the run folder is given
        only when no implementation chose a folder (and the user's
        ``strategies_export_dir`` ini option names none).
        """
        outcome = yield
        try:
            hooked = outcome.get_result()
        except BaseException:  # noqa: BLE001 - the hook's own error: pluggy raises it
            return
        answer = guard(
            "pytest_strategies_export_dir",
            lambda: self.strategies.answer(hooked),
            default=hooked,
        )
        if answer is not hooked:
            outcome.force_result(answer)

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_protocol(self, item: Item, nextitem: Item | None) -> bool | None:
        """Override test protocol to implement retry logic."""
        return guard(
            "pytest_runtest_protocol",
            lambda: run_with_retries(self, item, nextitem),
            default=None,
        )

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: Session, exitstatus: int) -> None:
        """Hook shell: crash-safe wrapper around _do_sessionfinish."""
        guard_void("pytest_sessionfinish", lambda: self._do_sessionfinish(session, exitstatus))

    def pytest_terminal_summary(
        self,
        terminalreporter: pytest.TerminalReporter,
        exitstatus: int,
        config: Config,
    ) -> None:
        """Hook shell: crash-safe wrapper around _do_terminal_summary."""
        guard_void(
            "pytest_terminal_summary",
            lambda: self._do_terminal_summary(terminalreporter, exitstatus, config),
        )

    # ------------------------------------------------------------------
    # Real hook bodies — all logic lives here
    # ------------------------------------------------------------------

    def _do_sessionstart(self, session: Session) -> None:
        """Real body of pytest_sessionstart."""
        self._start_time = time.time()
        self._session_start_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        self.context.ensure_dirs()
        self._tee = install_capture(self.config)

    def _do_collection_modifyitems(
        self,
        session: Session,  # noqa: ARG002
        config: Config,  # noqa: ARG002
        items: list[Item],
    ) -> None:
        """Real body of pytest_collection_modifyitems."""
        self.collector.register_items(items)

    def _do_runtest_setup(self, item: Item) -> None:
        """Real body of pytest_runtest_setup: fresh logger, steps and checks per attempt."""
        nodeid = item.nodeid
        if nodeid not in self.collector._run_map:
            return

        # Store item reference for stash access at finish time
        self._items[nodeid] = item

        # Create fresh logger
        logger = Logger()
        self._test_loggers[nodeid] = logger
        item._reporter_logger = logger  # type: ignore[attr-defined]

        # Start a new attempt: its own stepdoc steps and verifier checks
        self.steps.begin(nodeid)
        self._attempt_checks[nodeid] = []
        self._tabs.pop(nodeid, None)
        # Another plugin may run the test again (pytest-rerunfailures): the
        # attempt's folder must not keep the tabs of the run before
        shutil.rmtree(self._get_run_dir(nodeid) / "tabs", ignore_errors=True)

    def _do_runtest_logreport(self, report: TestReport) -> None:
        """Real body of pytest_runtest_logreport."""
        nodeid = report.nodeid
        if nodeid not in self.collector._run_map:
            return
        if report.when == "setup":
            # Every run reports its setup first, also from an xdist worker
            # (which names itself) and after the reporter's own retries
            worker = getattr(report, "worker_id", None)
            self.collector.record_start(nodeid, worker if isinstance(worker, str) else None)
        if nodeid in self._finished_runs:
            return
        capture_phase_logs(self, report)

    def _do_runtest_logfinish(
        self,
        nodeid: str,
        location: tuple[str, int | None, str],
    ) -> None:
        """Real body of pytest_runtest_logfinish."""
        if nodeid not in self.collector._run_map:
            return
        if nodeid in self._finished_runs:
            return
        write_run_finish_files(self, nodeid, location)

    def _do_sessionfinish(self, session: Session, exitstatus: int) -> None:  # noqa: ARG002
        """Real body of pytest_sessionfinish.

        The inner HTML try/except block (C1 guard) is preserved verbatim from the
        original implementation. It produces a degraded report on HTML build failure
        and still refreshes 01_latest/. The outer guard (in the hook shell) acts as
        the last-resort net for any exception OUTSIDE this inner block.
        """
        duration = time.time() - self._start_time
        session_end_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Write test.log.json aggregates
        for base_nodeid in self.collector.get_all_base_nodeids():
            aggregate = self.collector.get_function_aggregate(base_nodeid)
            func_dir = self.context.test_function_dir(aggregate["file"], aggregate["function_name"])
            write_test_log_json(func_dir / "test.log.json", aggregate)

        # Write JUnit XML
        write_junit_xml(
            self.context.run_dir / "junit.xml",
            self.collector,
            duration,
            retries_enabled=self.max_retries > 0,
        )

        # Write session.log.json
        session_entries = self.session_logger.serialize().get("entries", [])
        write_session_log_json(
            self.context.run_dir / "session.log.json",
            self._session_start_iso,
            session_end_iso,
            duration,
            session_entries,
        )

        # Finalize console capture
        finalize_capture(self._tee, self.context.run_dir / "pytest.log")

        # pytest-strategies wrote its run export in its own pytest_sessionfinish
        # (ours is trylast): read it for the HTML report.
        self.strategy_export = guard(
            "pytest_sessionfinish (strategy export)",
            lambda: self.strategies.load(self._start_time),
            default=None,
        )

        # Write HTML report — guarded so sessionfinish never raises (REQ-1).
        # Any exception in the build pipeline is caught, warned, and replaced
        # with a minimal degraded report.  01_latest/ is refreshed regardless.
        from ._html_builder import build_html_report

        try:
            html_data = build_html_data(self, duration, exitstatus)
            html = build_html_report(html_data)
            (self.context.run_dir / "report.html").write_text(html, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"pytest-reporter: HTML report build failed, writing degraded report: {exc}",
                stacklevel=2,
            )
            degraded = build_degraded_report(self.context.run_dir, exc)
            (self.context.run_dir / "report.html").write_text(degraded, encoding="utf-8")

        # Refresh the 01_latest hard copy of this run — always runs after the
        # guarded write block above so it fires even when the build failed.
        update_latest_copy(self.context.reports_dir, self.context.run_dir)

    def _do_terminal_summary(
        self,
        terminalreporter: pytest.TerminalReporter,
        exitstatus: int,  # noqa: ARG002
        config: Config,  # noqa: ARG002
    ) -> None:
        """Real body of pytest_terminal_summary."""
        terminalreporter.write_sep("=", "Report")
        terminalreporter.write_line(f"  HTML:  {self.context.run_dir / 'report.html'}")
        terminalreporter.write_line(f"  JUnit: {self.context.run_dir / 'junit.xml'}")
        terminalreporter.write_line(f"  Latest: {self.context.reports_dir / '01_latest'}")
