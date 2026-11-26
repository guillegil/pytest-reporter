"""Capture of standard Python ``logging`` records for the report.

The reporter has no logger of its own: tests, fixtures and libraries log with
``logging.getLogger(...)`` and the records end up in the phase logs. A handler
on the root logger collects them:

* while a test's setup, call or teardown runs, into that phase. The entries go
  on the phase's report as ``report.reporter_log`` (JSON-safe, so they survive
  pytest-xdist; the run's tables go as ``report.reporter_log_tables``), and the
  ``Reporter`` writes them into ``{phase}.log.json``;
* at any other time (collection, plugin hooks at session start and finish),
  into the session log (``session.log.json``, the Session Logs tab), on the
  process that writes the report.

An entry keeps the record's level, logger name (as ``source``, split on dots),
time, message and exception. The ``extra=`` fields of a record are its
``data`` (``extra={"data": {...}}`` gives that dict, for keys logging
reserves); ``extra={"report_table": rows}`` logs a table (shown inline and
saved as an HTML artifact), named by the message.

The level is ``report_log_level`` (ini), else pytest's ``log_level``, else
``INFO``. The root logger is lowered to that level when it is higher: during
each test phase (set back afterwards, as pytest does for ``log_level``) and,
on the process that writes the report, for the whole session, so the session
log gets the same levels (set back when pytest unconfigures).
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from ._table import SERIALIZED_ROW_LIMIT, normalize_table, sanitize_filename

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest import CallInfo, Config, Item, TestReport

#: Report attribute holding a phase's log entries.
LOG_ATTR = "reporter_log"
#: Report attribute holding the full tables logged in a phase.
TABLES_ATTR = "reporter_log_tables"
#: The ``extra=`` key that makes a record a table.
TABLE_KEY = "report_table"

# Attributes every LogRecord has (plus the ones formatters add): the rest are
# the fields given with extra=.
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
}


def _now(created: float) -> str:
    return datetime.fromtimestamp(created, UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _json_safe(value: Any, depth: int = 0) -> Any:  # noqa: ANN401
    """A copy of ``value`` made of JSON types only (``repr`` for anything else)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth < 20:
        if isinstance(value, dict):
            return {str(k): _json_safe(v, depth + 1) for k, v in value.items()}
        if isinstance(value, (list, tuple, set, frozenset)):
            return [_json_safe(v, depth + 1) for v in value]
    try:
        return repr(value)
    except Exception:  # noqa: BLE001 - a raising repr
        return f"<unrepresentable {type(value).__name__}>"


def _message(record: logging.LogRecord) -> str:
    try:
        return record.getMessage()
    except Exception:  # noqa: BLE001 - bad %-args: keep what was given
        return f"{record.msg!s} {record.args!r}"


def _exception(record: logging.LogRecord) -> dict[str, str] | None:
    info = record.exc_info
    if info and info[1] is not None:
        exc_type, exc, tb = info
        name = exc_type.__name__ if exc_type is not None else type(exc).__name__
        return {
            "type": name,
            "msg": str(exc),
            "tb": "".join(traceback.format_exception(exc_type, exc, tb)),
        }
    if record.exc_text:
        return {"type": "", "msg": "", "tb": record.exc_text}
    return None


@dataclass
class _Buffer:
    """The entries (and full tables) collected for one phase or the session."""

    keep_tables: bool = True
    names: set[str] = field(default_factory=set)
    entries: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)

    def add(self, record: logging.LogRecord) -> None:
        msg = _message(record)
        extras = {k: v for k, v in vars(record).items() if k not in _STANDARD}
        table = extras.pop(TABLE_KEY, None)
        data: dict[str, Any] | None = None
        if table is not None:
            data = self._table(msg, table)
        if data is None and extras:
            given = extras.get("data")
            if len(extras) == 1 and isinstance(given, dict):
                # extra={"data": {...}}: the dict itself (keys such as "name"
                # cannot be extra= fields: logging reserves them)
                extras = given
            data = _json_safe(extras)
        self.entries.append(
            {
                "seq": len(self.entries),
                "t": _now(record.created),
                "level": record.levelname,
                "source": [] if record.name == "root" else record.name.split("."),
                "msg": msg,
                "data": data,
                "exc": _exception(record),
            }
        )

    def _table(self, name: str, table: Any) -> dict[str, Any] | None:  # noqa: ANN401
        try:
            columns, rows = normalize_table(table)
        except Exception:  # noqa: BLE001 - not a table: logged as plain data
            return None
        base = sanitize_filename(name or "table")
        artifact = f"{base}.html"
        counter = 2
        while artifact in self.names:
            artifact = f"{base}_{counter}.html"
            counter += 1
        self.names.add(artifact)
        if self.keep_tables:
            self.tables.append(
                {"name": name, "columns": columns, "rows": rows, "artifact_name": artifact}
            )
        return {
            "_type": "table",
            "name": name,
            "columns": columns,
            "rows": rows[:SERIALIZED_ROW_LIMIT],
            "total_rows": len(rows),
            "truncated": len(rows) > SERIALIZED_ROW_LIMIT,
            "artifact_name": artifact,
        }


class _Handler(logging.Handler):
    """Sends each record to the running phase, else to the session log."""

    def __init__(self, level: int) -> None:
        super().__init__(level)
        self.phase: _Buffer | None = None
        self.session: _Buffer | None = None

    def emit(self, record: logging.LogRecord) -> None:
        target = self.phase if self.phase is not None else self.session
        if target is None:
            return
        try:
            target.add(record)
        except Exception:  # noqa: BLE001,S110 - logging must never fail a test
            pass


_PHASES_KEY = pytest.StashKey[dict[str, Any]]()


def _parse_level(text: str, setting: str) -> int:
    value = text.strip()
    if value.isdigit():
        return int(value)
    level = logging.getLevelName(value.upper())
    if not isinstance(level, int):
        raise pytest.UsageError(
            f"{setting}: {text!r} is not a logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
        )
    return level


def capture_level(config: Config) -> int:
    """``report_log_level``, else pytest's ``log_level``, else ``INFO``."""
    own = str(config.getini("report_log_level") or "").strip()
    if own:
        return _parse_level(own, "report_log_level")
    pytest_level = config.getoption("log_level", default=None) or config.getini("log_level")
    if pytest_level:
        return _parse_level(str(pytest_level), "log_level")
    return logging.INFO


class LogCapture:
    """Plugin that collects ``logging`` records per test phase and for the session."""

    def __init__(self, config: Config, *, session: bool) -> None:
        self.level = capture_level(config)
        self.handler = _Handler(self.level)
        if session:
            self.handler.session = _Buffer(keep_tables=False)
        self._saved_level: int | None = None
        # Outside the test phases too (session log): lower the root logger for
        # the whole session, set back at unconfigure
        root = logging.getLogger()
        self._session_level: int | None = None
        if session and root.level > self.level:
            self._session_level = root.level
            root.setLevel(self.level)
        self._attach()

    def _attach(self) -> None:
        root = logging.getLogger()
        if self.handler not in root.handlers:
            root.addHandler(self.handler)

    def detach(self) -> None:
        """Take the handler off the root logger (and restore its level)."""
        root = logging.getLogger()
        root.removeHandler(self.handler)
        if self._session_level is not None:
            root.setLevel(self._session_level)
            self._session_level = None

    def session_entries(self) -> list[dict[str, Any]]:
        """The entries logged outside tests so far."""
        session = self.handler.session
        return list(session.entries) if session is not None else []

    # -- phases --------------------------------------------------------

    def _start(self, item: Item, when: str) -> None:
        if when == "setup" or _PHASES_KEY not in item.stash:
            item.stash[_PHASES_KEY] = {"names": set()}
        phases = item.stash[_PHASES_KEY]
        buffer = _Buffer(names=phases["names"])
        phases[when] = buffer
        self._attach()
        root = logging.getLogger()
        self._saved_level = root.level
        if root.level > self.level:
            root.setLevel(self.level)
        self.handler.phase = buffer

    def _stop(self) -> None:
        self.handler.phase = None
        if self._saved_level is not None:
            logging.getLogger().setLevel(self._saved_level)
            self._saved_level = None

    @pytest.hookimpl(hookwrapper=True, trylast=True)
    def pytest_runtest_setup(self, item: Item) -> Generator[None, None, None]:
        self._start(item, "setup")
        try:
            yield
        finally:
            self._stop()

    @pytest.hookimpl(hookwrapper=True, trylast=True)
    def pytest_runtest_call(self, item: Item) -> Generator[None, None, None]:
        self._start(item, "call")
        try:
            yield
        finally:
            self._stop()

    @pytest.hookimpl(hookwrapper=True, trylast=True)
    def pytest_runtest_teardown(self, item: Item) -> Generator[None, None, None]:
        self._start(item, "teardown")
        try:
            yield
        finally:
            self._stop()

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(
        self,
        item: Item,
        call: CallInfo[None],
    ) -> Generator[None, Any, None]:
        outcome = yield
        try:
            report = outcome.get_result()
        except BaseException:  # noqa: BLE001 - pluggy re-raises it
            return
        phases = item.stash.get(_PHASES_KEY, None)
        buffer = phases.pop(call.when, None) if phases is not None else None
        if isinstance(buffer, _Buffer):
            setattr(report, LOG_ATTR, buffer.entries)
            if buffer.tables:
                setattr(report, TABLES_ATTR, buffer.tables)

    def pytest_unconfigure(self) -> None:
        self.detach()


def phase_entries(report: TestReport) -> list[dict[str, Any]]:
    """The log entries a phase report carries (``report.reporter_log``)."""
    entries = getattr(report, LOG_ATTR, None)
    if not isinstance(entries, (list, tuple)):
        return []
    return [e for e in entries if isinstance(e, dict)]


def phase_tables(report: TestReport) -> list[dict[str, Any]]:
    """The full tables logged in a phase (``report.reporter_log_tables``)."""
    tables = getattr(report, TABLES_ATTR, None)
    if not isinstance(tables, (list, tuple)):
        return []
    return [t for t in tables if isinstance(t, dict)]
