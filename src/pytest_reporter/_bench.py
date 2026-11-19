"""Bench provenance: what was on the bench when the tests ran.

``BenchInfo`` (the ``report_bench`` fixture, and the ``bench`` argument of the
``pytest_reporter_bench`` hook) records the devices under test, the instruments
with their calibration dates, and free rows in named sections. A value that
changes after it was first given is kept as a change, with the test (and the
retry attempt) that made it. ``document()`` is what the reporter writes as
``bench.json``; ``junit_properties()`` and ``html_data()`` are the same data
for ``junit.xml`` and the HTML report.

The reporter observes: an overdue calibration is shown and warned about, and
never changes a test's outcome.
"""

from __future__ import annotations

import math
import re
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from ._strategies import js_safe

#: The section ``BenchInfo.set`` writes to when none is named.
DEFAULT_SECTION = "Bench"

#: A stored value: what ``bench.json`` holds for one key.
Value = str | int | float | bool

# An instrument's keys in the order the report shows them; others follow.
INSTRUMENT_KEYS = (
    "idn",
    "manufacturer",
    "model",
    "serial",
    "firmware",
    "calibrated",
    "cal_due",
)
DEVICE_KEYS = ("serial", "firmware", "hardware")
_IDN_PARTS = ("manufacturer", "model", "serial", "firmware")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
# Characters XML 1.0 cannot hold, even escaped
_XML_INVALID = re.compile("[^\t\n\r -퟿-�\U00010000-\U0010ffff]")

# Who is running: the test's node ID (None between tests) and its attempt
# (0 for the first run, N for the reporter's retry N).
Running = Callable[[], tuple[str | None, int]]

# Whether a fixture shared between tests (any scope above "function") is being
# set up now.
Shared = Callable[[], bool]


def _nobody() -> tuple[str | None, int]:
    return None, 0


def _never() -> bool:
    return False


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _name(value: object, what: str) -> str:
    """A label, section or name: a non-blank ``str``, stripped."""
    if not isinstance(value, str):
        raise TypeError(f"{what} must be a str, not {type(value).__name__}")
    text = value.strip()
    if not text:
        raise ValueError(f"{what} must not be blank")
    return text


def _value(value: object, what: str) -> Value | None:
    """A value as stored: text, a number, a bool; a date as ISO text.

    A member of a ``str`` or ``int`` enum (any subclass) is stored as the plain
    value, so that ``bench.json``, ``junit.xml`` and the report read the same.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return str.__str__(value)
    if isinstance(value, int):
        return int.__int__(value)
    if isinstance(value, float):
        number = float.__float__(value)
        # JSON has no NaN or Infinity
        return number if math.isfinite(number) else repr(number)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(
        f"{what} must be a str, int, float, bool, date or datetime, not {type(value).__name__}"
    )


def _cal_date(value: object, what: str) -> str | None:
    """A calibration date as ``YYYY-MM-DD``."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if _ISO_DATE.match(text):
            try:
                return date.fromisoformat(text).isoformat()
            except ValueError:
                pass
        raise ValueError(f"{what} must be a date as YYYY-MM-DD, not {value!r}")
    raise TypeError(
        f"{what} must be a date, a datetime or YYYY-MM-DD text, not {type(value).__name__}"
    )


def parse_idn(idn: str) -> dict[str, str]:
    """The four parts of a ``*IDN?`` reply, by name.

    Args:
        idn: The reply, ``"Keysight Technologies,34465A,MY12345678,A.03.01"``.

    Returns:
        ``manufacturer``, ``model``, ``serial`` and ``firmware`` when the reply
        has exactly four comma-separated parts (blank parts are left out), else
        nothing.
    """
    parts = [part.strip() for part in idn.split(",")]
    if len(parts) != len(_IDN_PARTS):
        return {}
    return {key: part for key, part in zip(_IDN_PARTS, parts, strict=True) if part}


class BenchInfo:
    """What was on the bench: devices, instruments and other facts of the setup.

    Returned by the ``report_bench`` fixture and passed to
    ``pytest_reporter_bench(config, bench)``. With ``--report-dir`` the data
    goes to ``bench.json``, ``junit.xml`` and the HTML report's Report tab.
    Without it (and in pytest-xdist workers) the arguments are still checked
    and nothing is saved.

    Giving a name or label again replaces its values. A value that differs
    from the one given before is recorded as a change, with the test that was
    running.

    Example::

        @pytest.fixture(scope="session", autouse=True)
        def bench(report_bench, dut, dmm):
            report_bench.device("DUT", serial=dut.serial, firmware=dut.fw_version)
            report_bench.instrument("DMM", idn=dmm.query("*IDN?"), cal_due="2027-03-02")
            report_bench.set("Fixture board", "FB-12")
    """

    def __init__(self) -> None:
        self._saves = False
        self._running: Running = _nobody
        self._shared: Shared = _never
        self._lock = threading.Lock()
        self._sections: dict[str, dict[str, Value]] = {}
        self._devices: dict[str, dict[str, Value]] = {}
        self._instruments: dict[str, dict[str, Value]] = {}
        self._changes: list[dict[str, Any]] = []
        # What a shared fixture (or a call outside every test) last gave each
        # key: (kind, name) -> label -> value. See _store.
        self._given: dict[tuple[str, str], dict[str, Value]] = {}
        # The idn parts of each instrument that were given by name
        self._by_name: dict[str, set[str]] = {}

    def __repr__(self) -> str:
        rows = sum(len(section) for section in self._sections.values())
        return (
            f"<BenchInfo: {len(self._devices)} devices, "
            f"{len(self._instruments)} instruments, {rows} rows>"
        )

    # -- public API ---------------------------------------------------

    def set(self, label: str, value: object, *, section: str = DEFAULT_SECTION) -> None:
        """Record one fact of the setup: ``set("Fixture board", "FB-12")``.

        Args:
            label: What the value is. Giving it again replaces the value.
            value: A ``str``, ``int``, ``float``, ``bool``, ``datetime.date`` or
                ``datetime`` (stored as ISO text). ``None`` stores nothing and
                leaves an earlier value as it is.
            section: The heading the row is shown under (default ``"Bench"``).

        Raises:
            TypeError: A label or section that is not a ``str``, or a value of
                another type.
            ValueError: A blank label or section.
        """
        self.update({label: value}, section=section)

    def update(self, values: Mapping[str, object], *, section: str = DEFAULT_SECTION) -> None:
        """Record several facts at once: ``update({"Site": "Lab 2", "Rack": 4})``.

        Args:
            values: Label to value, each as for :meth:`set`.
            section: The heading the rows are shown under (default ``"Bench"``).

        Raises:
            TypeError: ``values`` is not a mapping; a label or section that is
                not a ``str``; a value of an unsupported type.
            ValueError: A blank label or section.
        """
        if not isinstance(values, Mapping):
            raise TypeError(f"values must be a mapping, not {type(values).__name__}")
        section = _name(section, "section")
        checked = {
            _name(label, "label"): _value(value, f"the value of {label!r}")
            for label, value in values.items()
        }
        self._store("section", section, self._sections, checked)

    def device(
        self,
        name: str,
        *,
        serial: object = None,
        firmware: object = None,
        hardware: object = None,
        **more: object,
    ) -> None:
        """Record a device under test: ``device("DUT", serial="SN-0042")``.

        Calling again with the same name replaces the values given and keeps
        the others. In a test, that is how a swapped board is recorded: the
        report shows the change with the test that made it.

        Args:
            name: The device's name in the report.
            serial: Its serial number.
            firmware: Its firmware version.
            hardware: Its hardware revision.
            **more: Any other facts, by name (``lot="2231"``).

        Raises:
            TypeError: A name that is not a ``str``, or a value of an
                unsupported type (see :meth:`set`).
            ValueError: A blank name.
        """
        name = _name(name, "name")
        given = {"serial": serial, "firmware": firmware, "hardware": hardware, **more}
        checked = {
            _name(key, "key"): _value(value, f"{key} of {name!r}") for key, value in given.items()
        }
        self._store("device", name, self._devices, checked)

    def instrument(
        self,
        name: str,
        *,
        idn: str | None = None,
        serial: object = None,
        calibrated: date | str | None = None,
        cal_due: date | str | None = None,
        **more: object,
    ) -> None:
        """Record an instrument: ``instrument("DMM", idn=dmm.query("*IDN?"))``.

        An instrument whose ``cal_due`` is before the day of the run is shown
        as overdue in the report and named in a warning when the session ends.
        It never changes a test's outcome.

        Args:
            name: The instrument's name in the report.
            idn: Its ``*IDN?`` reply, kept as given. A reply of four
                comma-separated parts also gives ``manufacturer``, ``model``,
                ``serial`` and ``firmware``, unless they are given by name,
                here or in an earlier call for this instrument.
            serial: Its serial number.
            calibrated: When it was last calibrated: a ``datetime.date``, a
                ``datetime`` or ``YYYY-MM-DD`` text.
            cal_due: When its calibration is due, in the same forms.
            **more: Any other facts, by name (``manufacturer=``, ``model=``,
                ``firmware=``, ``asset="LAB-0031"``). ``overdue`` is not one:
                the report works it out from ``cal_due``.

        Raises:
            TypeError: A name or ``idn`` that is not a ``str``, or a value of
                an unsupported type.
            ValueError: A blank name, a calibration date that is not a date,
                or ``overdue=``.
        """
        name = _name(name, "name")
        if idn is not None and not isinstance(idn, str):
            raise TypeError(f"idn must be a str, not {type(idn).__name__}")
        if "overdue" in more:
            raise ValueError(
                "overdue is worked out from cal_due and cannot be given; give the fact another name"
            )
        named: dict[str, Value] = {}
        for key, value in {"serial": serial, **more}.items():
            stored = _value(value, f"{key} of {name!r}")
            if stored is not None:
                named[_name(key, "key")] = stored
        dates = {
            "calibrated": _cal_date(calibrated, "calibrated"),
            "cal_due": _cal_date(cal_due, "cal_due"),
        }
        # The idn's parts a call gave by name, now or before, are not the idn's
        kept = {key for key in _IDN_PARTS if key in named}
        if self._saves:
            with self._lock:
                kept = self._by_name.setdefault(name, set()) | kept
                self._by_name[name] = kept
        checked: dict[str, Value | None] = {}
        if idn is not None and idn.strip():
            checked["idn"] = idn.strip()
            for key, part in parse_idn(idn).items():
                if key in named:
                    checked[key] = named[key]
                elif key not in kept:
                    checked[key] = part
        checked.update(named)
        checked.update(dates)
        self._store("instrument", name, self._instruments, checked)

    # -- what the reporter reads --------------------------------------

    @property
    def empty(self) -> bool:
        """Whether nothing was recorded."""
        return not (self._sections or self._devices or self._instruments)

    def changes(
        self, nodeid: str | None = None, attempt: int | None = None
    ) -> list[dict[str, Any]]:
        """The recorded changes, oldest first.

        Args:
            nodeid: Only the changes this test made.
            attempt: With ``nodeid``, only those of this attempt (0 is the
                first run, N the reporter's retry N).

        Returns:
            Copies of the change records: ``at``, ``nodeid``, ``attempt``,
            ``kind`` (``"section"``, ``"device"`` or ``"instrument"``),
            ``name``, ``label``, ``old`` and ``new``.
        """
        with self._lock:
            found = [dict(change) for change in self._changes]
        if nodeid is not None:
            found = [c for c in found if c["nodeid"] == nodeid]
            if attempt is not None:
                found = [c for c in found if c["attempt"] == attempt]
        return found

    def overdue(self, today: date) -> list[tuple[str, str]]:
        """The instruments whose calibration was due before ``today``.

        Args:
            today: The day of the run.

        Returns:
            ``(name, cal_due)`` of each, in the order recorded.
        """
        late = []
        with self._lock:
            for name, facts in self._instruments.items():
                due = facts.get("cal_due")
                if isinstance(due, str) and _is_before(due, today):
                    late.append((name, due))
        return late

    def document(
        self, today: date, metadata: Mapping[str, Mapping[str, str]] | None = None
    ) -> dict[str, Any]:
        """The ``bench.json`` document.

        Args:
            today: The day of the run, which decides ``overdue``.
            metadata: The sections of ``report_metadata`` and the
                ``pytest_reporter_metadata`` hook, kept beside the bench data.

        Returns:
            ``sections``, ``devices``, ``instruments`` (each with ``overdue``),
            ``changes``, ``metadata`` and ``run_date``.
        """
        with self._lock:
            sections = {name: dict(rows) for name, rows in self._sections.items()}
            devices = [{"name": name, **facts} for name, facts in self._devices.items()]
            instruments = [
                {
                    "name": name,
                    **facts,
                    "overdue": _is_before(facts.get("cal_due"), today),
                }
                for name, facts in self._instruments.items()
            ]
            changes = [dict(change) for change in self._changes]
        return {
            "run_date": today.isoformat(),
            "sections": sections,
            "devices": devices,
            "instruments": instruments,
            "changes": changes,
            "metadata": {
                str(section): dict(rows) for section, rows in (metadata or {}).items() if rows
            },
        }

    # -- recording ----------------------------------------------------

    def _store(
        self,
        kind: str,
        name: str,
        table: dict[str, dict[str, Value]],
        values: Mapping[str, Value | None],
    ) -> None:
        if not self._saves:
            return
        nodeid, attempt = self._running()
        shared = self._shared()
        with self._lock:
            known = table.setdefault(name, {})
            given = self._given.setdefault((kind, name), {})
            for label, new in values.items():
                if new is None:
                    continue
                old = known.get(label)
                if shared or nodeid is None or label not in given:
                    # pytest sets a session fixture up again for a retry (of
                    # the last test, always): what it gives as it did before
                    # is no news, and must not undo what a test changed since
                    again = shared and attempt > 0 and _same(given.get(label), new)
                    given[label] = new
                    if again:
                        continue
                if old is not None and not _same(old, new):
                    self._changes.append(
                        {
                            "at": _now(),
                            "nodeid": nodeid,
                            "attempt": attempt,
                            "kind": kind,
                            "name": name,
                            "label": label,
                            "old": old,
                            "new": new,
                        }
                    )
                known[label] = new
            if not known:
                del table[name]


def recording(running: Running, shared: Shared = _never) -> BenchInfo:
    """A ``BenchInfo`` that keeps what it is given (the reporter's own).

    Args:
        running: Gives the node ID of the test running now (``None`` between
            tests) and its attempt.
        shared: Says whether a fixture shared between tests is being set up
            now. In a retry attempt, what such a fixture gives as it did
            before is not a change and replaces nothing.

    Returns:
        The session's ``BenchInfo``.
    """
    bench = BenchInfo()
    bench._saves = True
    bench._running = running
    bench._shared = shared
    return bench


def _same(old: Value | None, new: Value) -> bool:
    # 1 and True are different facts; so are 1 and 1.0
    return type(old) is type(new) and old == new


def _is_before(due: object, today: date) -> bool:
    if not isinstance(due, str):
        return False
    try:
        return date.fromisoformat(due[:10]) < today
    except ValueError:
        return False


def is_empty(document: Mapping[str, Any]) -> bool:
    """Whether a ``bench.json`` document holds nothing worth a file."""
    return not any(
        document.get(key) for key in ("sections", "devices", "instruments", "changes", "metadata")
    )


def overdue_message(name: str, due: str) -> str:
    """The warning for an instrument past its calibration date."""
    return f"pytest-reporter: instrument {name!r} calibration was due {due}"


def change_text(change: Mapping[str, Any]) -> str:
    """One change as a line: ``device DUT serial: SN-0042 -> SN-0043``."""
    where = (
        f"{change.get('name')} / {change.get('label')}"
        if change.get("kind") == "section"
        else f"{change.get('kind')} {change.get('name')} {change.get('label')}"
    )
    text = f"{where}: {change.get('old')} -> {change.get('new')}"
    attempt = change.get("attempt")
    return f"{text} (retry {attempt})" if attempt else text


def xml_text(value: object) -> str:
    """``value`` as text an XML 1.0 attribute can hold."""
    return _XML_INVALID.sub("?", str(value))


def junit_properties(document: Mapping[str, Any]) -> list[tuple[str, str]]:
    """The testsuite properties of a ``bench.json`` document, in order.

    Args:
        document: What :meth:`BenchInfo.document` returned.

    Returns:
        ``(name, value)`` pairs: ``bench.<section>.<label>``,
        ``bench.device.<name>.<key>``, ``bench.instrument.<name>.<key>`` and
        ``metadata.<section>.<label>``.
    """
    out: list[tuple[str, str]] = []
    for section, rows in document.get("sections", {}).items():
        out += [(f"bench.{section}.{label}", _text(value)) for label, value in rows.items()]
    for kind in ("device", "instrument"):
        for entry in document.get(f"{kind}s", []):
            out += [
                (f"bench.{kind}.{entry['name']}.{key}", _text(value))
                for key, value in entry.items()
                if key != "name"
            ]
    for section, rows in document.get("metadata", {}).items():
        out += [(f"metadata.{section}.{label}", _text(value)) for label, value in rows.items()]
    return [(xml_text(name), xml_text(value)) for name, value in out]


def _text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def html_data(document: Mapping[str, Any]) -> dict[str, Any] | None:
    """``DATA.bench`` of the HTML report (``None`` when there is no bench data).

    The old metadata is not part of it: the System Data panel shows that.

    Args:
        document: What :meth:`BenchInfo.document` returned.

    Returns:
        The document without ``metadata``, with integers too large for a
        JavaScript number written as text.
    """
    data = {key: value for key, value in document.items() if key != "metadata"}
    if not any(data.get(key) for key in ("sections", "devices", "instruments", "changes")):
        return None
    safe: dict[str, Any] = js_safe(data)
    return safe
