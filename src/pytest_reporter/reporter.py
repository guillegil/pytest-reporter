"""Reporter -- main orchestrator that wires hooks to writers."""

from __future__ import annotations

import base64
import json
import mimetypes
import platform
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from ._collector import DataCollector
from ._console_capture import TeeFile, finalize_capture, install_capture
from ._context import RunContext
from ._json_writer import (
    write_failure_log,
    write_parameters_json,
    write_phase_log,
    write_procedure_json,
    write_session_log_json,
    write_test_log_json,
)
from ._junit_writer import write_junit_xml
from ._logger import Logger
from ._procedure import ProcedureTracker, _set_tracker
from ._symlinks import update_latest_copy
from ._table import build_table_artifact_html
from ._types import PhaseData, RetryData

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
        # Retry state: nodeid -> RetryData
        self._retry_state: dict[str, RetryData] = {}
        # Verification check results from pytest-verify: nodeid -> list[dict]
        self._check_results: dict[str, list[dict[str, Any]]] = {}
        # Item references for stash access: nodeid -> Item
        self._items: dict[str, Item] = {}

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

        # If we already handled this test via protocol hook, skip re-processing
        # (the protocol hook dispatches final reports to the hook chain for
        # terminal reporter / outcome counters, but we already wrote our files)
        if nodeid in self._finished_runs:
            return

        # Get logger entries for this phase
        logger = self._test_loggers.get(nodeid)
        entries: list[dict[str, Any]] = []
        if logger is not None:
            serialized = logger.serialize()
            entries = serialized.get("entries", [])

            # Write table artifacts before resetting the logger
            table_payloads = logger.get_table_payloads()
            if table_payloads:
                run_dir = self._get_run_dir(nodeid)
                artifacts_dir = run_dir / "artifacts"
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                for _seq, payload in table_payloads.items():
                    html = build_table_artifact_html(payload.name, payload.columns, payload.rows)
                    (artifacts_dir / payload.artifact_name).write_text(html, encoding="utf-8")

            # Reset logger after capturing entries for this phase
            # (each phase gets its own entries)
            logger.reset()

        # Record phase data with entries
        self.collector.record_phase(report, entries=entries)

        run_dir = self._get_run_dir(nodeid)

        # Write phase log immediately
        phase = self.collector.get_phase(nodeid, report.when)
        if phase is not None:
            write_phase_log(run_dir / f"{report.when}.log.json", phase)

        # Write failure log (only for original failures, not retries)
        if (
            report.when == "call"
            and report.failed
            and report.longrepr
            and nodeid not in self._retry_paths
        ):
            run_info = self.collector.get_run_info(nodeid)
            failure_name = f"{run_info.function_name}_{run_info.run_id}_error.log"
            write_failure_log(
                self.context.failures_dir / failure_name,
                nodeid,
                str(report.longrepr),
            )

    def pytest_runtest_logfinish(
        self,
        nodeid: str,
        location: tuple[str, int | None, str],
    ) -> None:
        if nodeid not in self.collector._run_map:
            return
        if nodeid in self._finished_runs:
            return

        run_info = self.collector.get_run_info(nodeid)
        run_dir = self._get_run_dir(nodeid)

        # Write procedure.json
        tracker = self._procedure_trackers.get(nodeid)
        procedure_data = tracker.serialize() if tracker else {"steps": []}
        write_procedure_json(run_dir / "procedure.json", procedure_data)

        # Write parameters.json (only in main run dir, not retries)
        if nodeid not in self._retry_paths:
            write_parameters_json(run_dir / "parameters.json", run_info)

        # Capture verification check results from pytest-verify public API
        if get_check_results is not None:
            item = self._items.get(nodeid)
            if item is not None:
                checks = get_check_results(item)
                if checks:
                    self._check_results[nodeid] = checks

        # Create artifacts directory
        (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)

        # Clean up the active tracker
        _set_tracker(None)

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_protocol(self, item: Item, nextitem: Item | None) -> bool | None:
        """Override test protocol to implement retry logic."""
        if self.max_retries <= 0:
            return None  # Let pytest handle normally

        nodeid = item.nodeid
        if nodeid not in self.collector._run_map:
            return None

        from _pytest.runner import runtestprotocol

        # Run the test normally first (log=False so we control report dispatch)
        reports = runtestprotocol(item, nextitem=nextitem, log=False)

        # Process reports: since log=False, the logger was NOT reset between
        # phases.  All entries accumulated during the full run belong to the
        # call phase (setup/teardown only run fixture code, not user code).
        # Capture entries once and assign to the call-phase report.
        logger = self._test_loggers.get(nodeid)
        all_entries: list[dict[str, Any]] = []
        if logger is not None:
            all_entries = logger.serialize().get("entries", [])

            # Write table artifacts
            table_payloads = logger.get_table_payloads()
            if table_payloads:
                run_dir = self._get_run_dir(nodeid)
                artifacts_dir = run_dir / "artifacts"
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                for _seq, payload in table_payloads.items():
                    html = build_table_artifact_html(payload.name, payload.columns, payload.rows)
                    (artifacts_dir / payload.artifact_name).write_text(html, encoding="utf-8")

            logger.reset()

        for report in reports:
            entries = all_entries if report.when == "call" else []
            self.collector.record_phase(report, entries=entries)
            phase = self.collector.get_phase(nodeid, report.when)
            if phase is not None:
                run_dir = self._get_run_dir(nodeid)
                write_phase_log(run_dir / f"{report.when}.log.json", phase)
            # Write failure log for call-phase failures
            if (
                report.when == "call"
                and report.failed
                and report.longrepr
                and nodeid not in self._retry_paths
            ):
                run_info = self.collector.get_run_info(nodeid)
                failure_name = f"{run_info.function_name}_{run_info.run_id}_error.log"
                write_failure_log(
                    self.context.failures_dir / failure_name,
                    nodeid,
                    str(report.longrepr),
                )

        # Write per-run files for original execution
        self.pytest_runtest_logfinish(nodeid=nodeid, location=item.location)

        # Check if call phase failed
        call_report = None
        for report in reports:
            if report.when == "call":
                call_report = report
                break

        if call_report is None or not call_report.failed:
            # Mark finished BEFORE dispatching to prevent our own
            # logreport hook from re-processing (and overwriting entries)
            self._finished_runs.add(nodeid)
            # Dispatch reports to pytest for terminal output
            for report in reports:
                item.config.hook.pytest_runtest_logreport(report=report)
            item.config.hook.pytest_runtest_logfinish(nodeid=nodeid, location=item.location)
            return True

        # Start retry loop
        run_info = self.collector.get_run_info(nodeid)
        main_run_dir = self.context.run_subdir(
            run_info.file_path, run_info.function_name, run_info.run_id
        )

        retry_data = RetryData(
            max_retries=self.max_retries,
            attempts=0,
            original_outcome="failed",
            history=["failed"],
        )

        final_reports = reports  # will be updated if retry succeeds

        for attempt in range(1, self.max_retries + 1):
            retry_dir = main_run_dir / "retries" / f"{attempt:02d}"
            retry_dir.mkdir(parents=True, exist_ok=True)

            # Set retry path so writes go to retry subfolder
            self._retry_paths[nodeid] = retry_dir

            # Create fresh logger and procedure tracker for retry
            logger = Logger()
            self._test_loggers[nodeid] = logger
            item._reporter_logger = logger  # type: ignore[attr-defined]

            tracker = ProcedureTracker()
            self._procedure_trackers[nodeid] = tracker
            _set_tracker(tracker)

            # Re-execute the test
            retry_reports = runtestprotocol(item, nextitem=None, log=False)

            # Write retry phase logs directly to disk (don't overwrite collector)
            for report in retry_reports:
                retry_entries: list[dict[str, Any]] = []
                if logger is not None:
                    serialized = logger.serialize()
                    retry_entries = serialized.get("entries", [])

                    # Write table artifacts for retry
                    table_payloads = logger.get_table_payloads()
                    if table_payloads:
                        retry_artifacts = retry_dir / "artifacts"
                        retry_artifacts.mkdir(parents=True, exist_ok=True)
                        for _seq, payload in table_payloads.items():
                            html = build_table_artifact_html(
                                payload.name, payload.columns, payload.rows
                            )
                            (retry_artifacts / payload.artifact_name).write_text(
                                html, encoding="utf-8"
                            )

                    logger.reset()

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
        self._retry_paths.pop(nodeid, None)

        # Store retry data
        self.collector.set_retry_data(nodeid, retry_data)

        # Mark as finished BEFORE dispatching to prevent our hooks from
        # re-processing the reports (which would overwrite original phase data)
        self._finished_runs.add(nodeid)

        # Dispatch the FINAL outcome to pytest's hook system
        # This ensures terminal reporter and outcome counters reflect the retry result
        for report in final_reports:
            item.config.hook.pytest_runtest_logreport(report=report)
        item.config.hook.pytest_runtest_logfinish(nodeid=nodeid, location=item.location)

        return True  # We handled the protocol

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

        # Write HTML report
        from ._html_builder import build_html_report

        html_data = self._build_html_data(duration, exitstatus)
        html = build_html_report(html_data)
        (self.context.run_dir / "report.html").write_text(html, encoding="utf-8")

        # Refresh the 01_latest hard copy of this run
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

    def _build_html_data(self, duration: float, exitstatus: int) -> dict:  # type: ignore[type-arg]
        """Build the data dict for the HTML report."""
        # Collect all test data
        tests: list[dict] = []  # type: ignore[type-arg]
        for base_nodeid in self.collector.get_all_base_nodeids():
            aggregate = self.collector.get_function_aggregate(base_nodeid)
            runs: list[dict] = []  # type: ignore[type-arg]
            for nodeid in self.collector.get_function_nodeids(base_nodeid):
                run_info = self.collector.get_run_info(nodeid)
                phases = {}
                for when in ("setup", "call", "teardown"):
                    phase = self.collector.get_phase(nodeid, when)
                    if phase is not None:
                        phases[when] = {
                            "phase": phase.when,
                            "outcome": phase.outcome,
                            "start_time": phase.start_time,
                            "end_time": phase.end_time,
                            "duration": round(phase.duration, 4),
                            "longrepr": phase.longrepr,
                            "entries": phase.entries,
                        }

                # Collect artifacts from disk
                run_dir = self.context.run_subdir(
                    run_info.file_path,
                    run_info.function_name,
                    run_info.run_id,
                )
                artifacts = self._collect_artifacts(run_dir / "artifacts")

                # Collect procedure
                tracker = self._procedure_trackers.get(nodeid)
                procedure = tracker.serialize() if tracker else {"steps": []}

                # Collect retry data
                retry_data = self.collector.get_retry_data(nodeid)
                retries_info = None
                retry_attempts = []
                if retry_data and retry_data.attempts > 0:
                    retries_info = {
                        "attempts": retry_data.attempts,
                        "original_outcome": retry_data.original_outcome,
                        "history": retry_data.history,
                    }
                    # Collect retry attempt data from disk
                    retries_base = run_dir / "retries"
                    if retries_base.is_dir():
                        for attempt_dir in sorted(retries_base.iterdir()):
                            if attempt_dir.is_dir():
                                attempt_data: dict[str, Any] = {
                                    "attempt": attempt_dir.name,
                                    "phases": {},
                                    "artifacts": self._collect_artifacts(attempt_dir / "artifacts"),
                                }
                                # Read phase logs from retry dir
                                for phase_name in ("setup", "call", "teardown"):
                                    phase_file = attempt_dir / f"{phase_name}.log.json"
                                    if phase_file.exists():
                                        attempt_data["phases"][phase_name] = json.loads(
                                            phase_file.read_text()
                                        )
                                # Read procedure
                                proc_file = attempt_dir / "procedure.json"
                                if proc_file.exists():
                                    attempt_data["procedure"] = json.loads(proc_file.read_text())
                                retry_attempts.append(attempt_data)

                # Collect verification check results from pytest-verify
                check_results = self._check_results.get(nodeid, [])

                runs.append(
                    {
                        "run_id": run_info.run_id,
                        "nodeid": nodeid,
                        "parametrize_id": run_info.parametrize_id,
                        "params": {
                            k: {"type": type(v).__name__, "value": str(v)}
                            for k, v in run_info.params.items()
                        },
                        "outcome": self.collector.get_outcome(nodeid),
                        "duration": round(self.collector.get_duration(nodeid), 4),
                        "phases": phases,
                        "procedure": procedure,
                        "artifacts": artifacts,
                        "retries": retries_info,
                        "retry_attempts": retry_attempts,
                        "check_results": check_results,
                    }
                )
            tests.append(
                {
                    "base_nodeid": base_nodeid,
                    "aggregate": dict(aggregate),
                    "runs": runs,
                }
            )

        # Collect environment info
        plugin_list = []
        pm = self.config.pluginmanager
        for plugin in pm.get_plugins():
            name = pm.get_name(plugin) or getattr(plugin, "__name__", None)
            if name and not name.startswith("_"):
                plugin_list.append(name)

        cmdline = self.config.invocation_params.args

        # Session log data
        session_log_data = self.session_logger.serialize()

        return {
            "timestamp": self.context.timestamp,
            "duration": round(duration, 2),
            "exit_code": exitstatus,
            "python_version": sys.version,
            "pytest_version": pytest.__version__,
            "platform": platform.platform(),
            "plugins": plugin_list,
            "cmdline": [str(a) for a in cmdline],
            "tests": tests,
            "session_log": session_log_data,
            "retries_enabled": self.max_retries > 0,
            "max_retries": self.max_retries,
        }

    @staticmethod
    def _collect_artifacts(artifacts_dir: Path) -> list[dict[str, object]]:
        """Read artifacts from disk and encode embeddable ones as data URIs."""
        if not artifacts_dir.is_dir():
            return []

        result: list[dict[str, object]] = []
        embeddable = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".svg",
            ".bmp",
            ".html",
            ".htm",
        }

        for path in sorted(artifacts_dir.iterdir()):
            if not path.is_file():
                continue
            entry: dict[str, object] = {
                "name": path.name,
                "size": path.stat().st_size,
            }
            ext = path.suffix.lower()
            if ext in embeddable:
                mime = mimetypes.guess_type(path.name)[0] or (
                    "text/html" if ext in (".html", ".htm") else "application/octet-stream"
                )
                raw = path.read_bytes()
                b64 = base64.b64encode(raw).decode("ascii")
                entry["data_uri"] = f"data:{mime};base64,{b64}"
            result.append(entry)
        return result
