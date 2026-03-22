"""Hook registrations — the entry point for pytest plugin discovery."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .reporter import Reporter

if TYPE_CHECKING:
    from pytest import Config, Parser


def pytest_addoption(parser: Parser) -> None:
    group = parser.getgroup("reporter", "Reporter options")
    group.addoption(
        "--report",
        dest="report_path",
        default=None,
        help="Path to write the JSON test report (e.g. --report=report.json)",
    )


def pytest_configure(config: Config) -> None:
    path_str: str | None = config.getoption("--report", default=None)
    if path_str:
        # Only register on the controller, not xdist workers
        if not hasattr(config, "workerinput"):
            config.pluginmanager.register(
                Reporter(config, Path(path_str)),
                "pytest_reporter",
            )
