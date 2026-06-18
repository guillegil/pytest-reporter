"""Reporter -- main orchestrator that wires hooks to writers."""

from __future__ import annotations

import time
import warnings
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
from ._procedure import ProcedureTracker, _set_tracker
from ._report_builder import build_html_data
from ._retry import run_with_retries
from ._symlinks import update_latest_copy

try:
    from pytest_verify import get_check_results  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    get_check_results = None

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
        # Per-test procedure trackers: nodeid -> ProcedureTracker
        self._procedure_trackers: dict[str, ProcedureTracker] = {}
        # Per-test loggers: nodeid -> Logger
        self._test_loggers: dict[str, Logger] = {}
        # Current retry write paths: nodeid -> Path (for retry subfolder)
        self._retry_paths: dict[str, Path] = {}
        # Verification check results from pytest-verify: nodeid -> list[dict]
        self._check_results: dict[str, list[dict[str, Any]]] = {}
        # Item references for stash access: nodeid -> Item
        self._items: dict[str, Item] = {}
        # Mutable metadata dict populated via report_metadata fixture or hook
        self.metadata_store: dict[str, dict[str, Any]] = {}

    def get_current_run_dir(self, nodeid: str) -> Path | None:
        """Get the current write directory for a test (retry-aware)."""
        return self._retry_paths.get(nodeid)

    def _get_run_dir(self, nodeid: str) -> Path:
        """Get the write directory for a test, considering retries."""
        retry_path = self._retry_paths.get(nodeid)
        if retry_path is not None:
            return retry_path
        run_info = self.collector.get_run_info(nodeid)
        return self.context.run_subdir(run_info.file_path, run_info.function_name, run_info.run_id)

    def pytest_sessionstart(self, session: Session) -> None:
        self._start_time = time.time()
        self._session_start_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        self.context.ensure_dirs()
        self._tee = install_capture(self.config)

    def pytest_collection_modifyitems(
        self,
        session: Session,
        config: Config,
        items: list[Item],
    ) -> None:
        self.collector.register_items(items)

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item: Item) -> None:
        """Create a fresh logger and procedure tracker for each test."""
        nodeid = item.nodeid
        if nodeid not in self.collector._run_map:
            return

        # Store item reference for stash access at finish time
        self._items[nodeid] = item

        # Create fresh logger
        logger = Logger()
        self._test_loggers[nodeid] = logger
        item._reporter_logger = logger  # type: ignore[attr-defined]

        # Create fresh procedure tracker
        tracker = ProcedureTracker()
        self._procedure_trackers[nodeid] = tracker
        _set_tracker(tracker)

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        nodeid = report.nodeid
        if nodeid not in self.collector._run_map:
            return
        if nodeid in self._finished_runs:
            return
        capture_phase_logs(self, report)

    def pytest_runtest_logfinish(
        self,
        nodeid: str,
        location: tuple[str, int | None, str],
    ) -> None:
        if nodeid not in self.collector._run_map:
            return
        if nodeid in self._finished_runs:
            return
        write_run_finish_files(self, nodeid, location, get_check_results)

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_protocol(self, item: Item, nextitem: Item | None) -> bool | None:
        """Override test protocol to implement retry logic."""
        return run_with_retries(self, item, nextitem)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: Session, exitstatus: int) -> None:
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

    def pytest_terminal_summary(
        self,
        terminalreporter: pytest.TerminalReporter,
        exitstatus: int,
        config: Config,
    ) -> None:
        terminalreporter.write_sep("=", "Report")
        terminalreporter.write_line(f"  HTML:  {self.context.run_dir / 'report.html'}")
        terminalreporter.write_line(f"  JUnit: {self.context.run_dir / 'junit.xml'}")
        terminalreporter.write_line(f"  Latest: {self.context.reports_dir / '01_latest'}")
