# Custom Reporters

## Reporter architecture

A reporter is just a plugin class that implements **reporting hooks**.
Register it conditionally inside `pytest_configure` (not always):

```python
# plugin.py
def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--my-report", default=None):
        config.pluginmanager.register(
            MyReporter(config),
            "myplugin_reporter",
        )
```

This ensures the reporter only loads when explicitly requested, keeping
the default test run unaffected.

---

## Core reporting hooks

```
pytest_runtest_logreport(report)    # called for setup, call, teardown phases
pytest_terminal_summary(terminalreporter, exitstatus, config)
pytest_sessionfinish(session, exitstatus)
```

---

## Minimal terminal reporter extension

```python
# src/pytest_myplugin/reporter.py
from __future__ import annotations
import time
from typing import TYPE_CHECKING
import pytest

if TYPE_CHECKING:
    from pytest import Config, TestReport


class TimingReporter:
    """Append per-test timing data to the terminal summary."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._timings: dict[str, float] = {}

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        nodeid = report.nodeid
        if report.when == "call":
            self._timings[nodeid] = report.duration

    def pytest_terminal_summary(
        self,
        terminalreporter: pytest.TerminalReporter,
        exitstatus: int,
        config: Config,
    ) -> None:
        if not self._timings:
            return
        terminalreporter.write_sep("=", "Slowest tests")
        slowest = sorted(self._timings.items(), key=lambda x: x[1], reverse=True)[:10]
        for nodeid, duration in slowest:
            terminalreporter.write_line(f"  {duration:.3f}s  {nodeid}")
```

---

## Writing a file-based reporter (JSON / JUnit extension)

```python
# src/pytest_myplugin/reporter.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, TYPE_CHECKING
import pytest

if TYPE_CHECKING:
    from pytest import Config, TestReport, Session


class JsonReporter:
    """Write a machine-readable JSON report to a file."""

    def __init__(self, config: Config, output_path: Path) -> None:
        self.output_path = output_path
        self._results: list[dict[str, Any]] = []

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        if report.when != "call":
            return
        self._results.append({
            "nodeid": report.nodeid,
            "outcome": report.outcome,          # "passed" | "failed" | "skipped"
            "duration": report.duration,
            "longrepr": str(report.longrepr) if report.failed else None,
        })

    def pytest_sessionfinish(self, session: Session, exitstatus: int) -> None:
        self.output_path.write_text(
            json.dumps({"results": self._results, "exit_code": exitstatus}, indent=2)
        )
```

Register it:
```python
def pytest_configure(config: pytest.Config) -> None:
    path_str: str | None = config.getoption("--json-report", default=None)
    if path_str:
        config.pluginmanager.register(
            JsonReporter(config, Path(path_str)),
            "myplugin_json_reporter",
        )
```

---

## `TestReport` fields reference

| Field | Type | Notes |
|---|---|---|
| `nodeid` | `str` | Unique test ID |
| `when` | `"setup"` / `"call"` / `"teardown"` | Which phase |
| `outcome` | `"passed"` / `"failed"` / `"skipped"` | Result |
| `duration` | `float` | Seconds |
| `longrepr` | `str \| ReprExceptionInfo \| None` | Failure details |
| `passed` / `failed` / `skipped` | `bool` | Convenience properties |
| `keywords` | `Mapping[str, Any]` | Markers on the test |

---

## Accessing the live terminal reporter

Sometimes you need to write to the terminal *during* a test run (not just
in `pytest_terminal_summary`). Use `config.pluginmanager.get_plugin`:

```python
def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
    if report.failed:
        tr: pytest.TerminalReporter = (
            self.config.pluginmanager.get_plugin("terminalreporter")
        )
        if tr is not None:
            tr.write_line(f"  ⚠ Custom annotation: {report.nodeid}", red=True)
```

---

## xdist compatibility

When running under `pytest-xdist`, worker processes don't have a terminal.
Guard reporter registration:

```python
def pytest_configure(config: pytest.Config) -> None:
    # Only register on the controller, not xdist workers
    if not hasattr(config, "workerinput"):
        config.pluginmanager.register(MyReporter(config), "my_reporter")
```
