"""Reporter plugin class that collects results and writes reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from ._types import TestResult

if TYPE_CHECKING:
    from pytest import Config, Session, TestReport


class Reporter:
    """Collect test results and write a JSON report at session end."""

    def __init__(self, config: Config, output_path: Path) -> None:
        self.config = config
        self.output_path = output_path
        self._results: list[TestResult] = []

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        # Capture call-phase results, plus skips from setup phase
        if report.when == "call" or (
            report.when == "setup" and report.skipped
        ):
            self._results.append(
                TestResult(
                    nodeid=report.nodeid,
                    outcome=report.outcome,
                    duration=report.duration,
                    longrepr=str(report.longrepr) if report.failed else None,
                )
            )

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: Session, exitstatus: int) -> None:
        report_data: dict[str, Any] = {
            "exit_code": exitstatus,
            "total": len(self._results),
            "passed": sum(1 for r in self._results if r["outcome"] == "passed"),
            "failed": sum(1 for r in self._results if r["outcome"] == "failed"),
            "skipped": sum(1 for r in self._results if r["outcome"] == "skipped"),
            "results": self._results,
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps(report_data, indent=2))

    def pytest_terminal_summary(
        self,
        terminalreporter: pytest.TerminalReporter,
        exitstatus: int,
        config: Config,
    ) -> None:
        terminalreporter.write_sep("=", "Report")
        terminalreporter.write_line(f"Report written to: {self.output_path}")
