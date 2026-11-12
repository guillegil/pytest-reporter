"""Test procedures from stepdoc — an optional integration.

pytest-reporter has no step API of its own. Tests write their procedure with
`stepdoc <https://github.com/guillegil/stepdoc>`_ (``from stepdoc import step``),
and the reporter turns each attempt's steps into ``procedure.json`` and the
HTML Procedure tab.

stepdoc is never imported here. The reporter follows steps through stepdoc's
public hooks (``pytest_stepdoc_step_started`` / ``pytest_stepdoc_step_finished``,
implemented with ``optionalhook=True`` on the ``Reporter``) and reads the
attributes of the ``stepdoc.Step``/``Action``/``Check`` objects it is handed.
Without stepdoc installed the hooks never fire and every procedure is empty.

stepdoc only records (and calls its hooks) when one of its output options is
given. When ``--report-dir`` is active and the user gave none, :func:`activate`
points ``--stepdoc-record`` at ``<run>/stepdoc.json``, so stepdoc records and its
run record is saved with the report. The ``report_stepdoc`` ini setting turns
this off.
"""

from __future__ import annotations

import difflib
import re
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

#: File name of stepdoc's run record inside the run folder.
RECORD_NAME = "stepdoc.json"

# stepdoc step status -> reporter outcome (status-dot class).
_OUTCOME = {
    "passed": "passed",
    "failed": "failed",
    "error": "error",
    "not_run": "skipped",
    "unknown": "unknown",
}
_ASSIGN_OPS = {"write", "set"}
_BARE_OPS = {"request"}
_MAX_VALUE = 200
_TICKS = re.compile(r"`+")
# Words (with a decimal part), <names>, runs of spaces, or any other character.
_TOKEN = re.compile(r"<[^<>\s]+>|\w+(?:\.\w+)*|\s+|.")


def title_segments(title: str) -> list[dict[str, Any]] | None:
    """A step title's Markdown code spans as ``description_segments``.

    stepdoc titles mark monospace with backticks (``"Write `dut.reg1 = 1`"``,
    or ``stepdoc.fmt.mono``). A run of backticks opens a span that ends at the
    next run of the same length; an unmatched run is plain text; one space is
    stripped from both ends of a padded span (Markdown's rules, as in
    ``stepdoc.fmt.spans``). Returns ``None`` when the title has no span.
    """
    out: list[dict[str, Any]] = []

    def add(text: str, mono: bool) -> None:
        if not text:
            return
        if out and not mono and out[-1]["style"] is None:
            out[-1]["text"] += text
        else:
            out.append({"text": text, "style": "mono" if mono else None})

    pos = 0
    while True:
        m = _TICKS.search(title, pos)
        if m is None:
            add(title[pos:], False)
            break
        n = len(m.group())
        close = next((c for c in _TICKS.finditer(title, m.end()) if len(c.group()) == n), None)
        if close is None:
            add(title[pos : m.end()], False)
            pos = m.end()
            continue
        add(title[pos : m.start()], False)
        body = title[m.end() : close.start()]
        if len(body) >= 2 and body[0] == " " and body[-1] == " " and body.strip():
            body = body[1:-1]
        if body.strip():
            add(body, True)
        else:
            add(title[m.start() : close.end()], False)
        pos = close.end()
    return out if any(seg["style"] == "mono" for seg in out) else None


def activate(config: pytest.Config, run_dir: Path) -> str | None:
    """Make stepdoc record this session when it would stay inert.

    Called from the reporter's ``pytest_configure`` (``tryfirst``), before
    stepdoc's own ``pytest_configure`` reads its options.

    Args:
        config: The pytest config.
        run_dir: This run's folder, where stepdoc's record is written.

    Returns:
        The record path set, or ``None`` when nothing was changed (stepdoc not
        installed, turned off with ``report_stepdoc = false``, or already
        recording because the user passed a stepdoc option).
    """
    if not config.pluginmanager.has_plugin("stepdoc"):
        return None
    try:
        enabled = config.getini("report_stepdoc")
    except ValueError:  # pragma: no cover - ini registered by our plugin
        enabled = True
    if not enabled:
        return None
    opt = config.option
    if not hasattr(opt, "stepdoc_record"):
        return None  # an older stepdoc without the option
    names = ("stepdoc_record", "stepdoc_procedure", "stepdoc_report", "stepdoc_dry_run")
    if any(getattr(opt, n, None) for n in names):
        return None  # already recording, with the user's own outputs
    path = str(run_dir / RECORD_NAME)
    opt.stepdoc_record = path
    return path


class StepCollector:
    """The top-level stepdoc steps of each test attempt, by node ID.

    stepdoc keeps one recorder per test protocol, and the reporter's retries
    run inside that protocol, so :meth:`begin` starts a new list for each
    attempt: an attempt's procedure holds only the steps it opened.
    """

    def __init__(self) -> None:
        self._steps: dict[str, list[Any]] = {}
        # id(step) -> (step, wall start, wall end); the step is kept so its id
        # is not reused while the entry lives.
        self._times: dict[int, tuple[Any, float, float | None]] = {}

    def begin(self, nodeid: str) -> None:
        """Start a new attempt of ``nodeid``."""
        for step in self._steps.get(nodeid, []):
            self._forget(step)
        self._steps[nodeid] = []

    def started(self, item: pytest.Item, step: Any) -> None:  # noqa: ANN401
        """``pytest_stepdoc_step_started``: remember top-level steps and times."""
        self._times[id(step)] = (step, time.time(), None)
        if "." not in str(getattr(step, "number", "")):
            self._steps.setdefault(item.nodeid, []).append(step)

    def finished(self, item: pytest.Item, step: Any) -> None:  # noqa: ARG002, ANN401
        """``pytest_stepdoc_step_finished``: remember when the step ended."""
        entry = self._times.get(id(step))
        start = entry[1] if entry is not None else time.time()
        self._times[id(step)] = (step, start, time.time())

    def procedure(self, nodeid: str) -> dict[str, Any]:
        """The ``procedure.json`` document of the current attempt of ``nodeid``."""
        steps = self._steps.get(nodeid, [])
        if not steps:
            return {"steps": []}
        counters: dict[str, int] = {}
        nodes = []
        for step in steps:
            section = str(getattr(step, "section", "procedure") or "procedure")
            counters[section] = counters.get(section, 0) + 1
            prefix = {"setup": "S", "teardown": "T"}.get(section, "")
            nodes.append(self._step(step, f"{prefix}{counters[section]}"))
        return {"steps": nodes, "source": "stepdoc"}

    def discard(self, nodeid: str) -> None:
        """Drop what is kept for ``nodeid`` once its files are written."""
        for step in self._steps.pop(nodeid, []):
            self._forget(step)

    # ------------------------------------------------------------------

    def _forget(self, step: Any) -> None:  # noqa: ANN401
        self._times.pop(id(step), None)
        for child in getattr(step, "entries", None) or []:
            if hasattr(child, "entries"):
                self._forget(child)

    def _wall(self, step: Any) -> tuple[float, float]:  # noqa: ANN401
        """Wall-clock start and end of ``step`` (seconds since the epoch)."""
        entry = self._times.get(id(step))
        start = entry[1] if entry is not None else time.time()
        end = entry[2] if entry is not None and entry[2] is not None else None
        if end is None:
            spent = _float(getattr(step, "ended", 0.0)) - _float(getattr(step, "started", 0.0))
            end = start + max(spent, 0.0)
        return start, max(end, start)

    def _step(self, step: Any, number: str) -> dict[str, Any]:  # noqa: ANN401
        start, end = self._wall(step)
        status = str(getattr(step, "status", "unknown"))
        node: dict[str, Any] = {
            "kind": "step",
            "number": number,
            "description": str(getattr(step, "title", "")),
            "outcome": _OUTCOME.get(status, "unknown"),
            "start_time": _iso(start),
            "end_time": _iso(end),
            "duration_seconds": round(end - start, 6),
            "exc": _exc(getattr(step, "error", None)),
            "section": str(getattr(step, "section", "procedure") or "procedure"),
        }
        segments = title_segments(node["description"])
        if segments is not None:
            node["description_segments"] = segments
        children = [
            self._entry(e, f"{number}.{i}")
            for i, e in enumerate(getattr(step, "entries", None) or [], 1)
        ]
        if children:
            node["substeps"] = children
        return node

    def _entry(self, entry: Any, number: str) -> dict[str, Any]:  # noqa: ANN401
        if hasattr(entry, "entries") and hasattr(entry, "title"):
            return self._step(entry, number)
        if hasattr(entry, "passed") and hasattr(entry, "text"):
            return _check(entry, number)
        return _action(entry, number)


def _check(check: Any, number: str) -> dict[str, Any]:  # noqa: ANN401
    passed = getattr(check, "passed", None)
    text = str(getattr(check, "text", ""))
    symbolic = getattr(check, "symbolic_text", None)
    if isinstance(symbolic, str) and symbolic and symbolic != text:
        text = with_values(symbolic, text)
    selected = getattr(check, "selected", None)
    if selected:
        text += f" [→ {selected}]"
    node: dict[str, Any] = {
        "kind": "check",
        "number": number,
        "description": f"Verify {text}",
        "outcome": "unknown" if passed is None else ("passed" if passed else "failed"),
        "exc": None,
    }
    result = _check_result(check)
    if result is not None:
        node["result"] = result
    detail = getattr(check, "detail", None)
    if detail:
        node["detail"] = str(detail)
    children = [
        _check(child, f"{number}.{i}")
        for i, child in enumerate(getattr(check, "children", None) or [], 1)
    ]
    if children:
        node["substeps"] = children
    return node


def with_values(symbolic: str, concrete: str) -> str:
    """A check's symbolic text with this run's values after the names they replace.

    stepdoc's procedure reads ``'Readback' == <wdata>``; this run's check reads
    ``'Readback' == 243``. Each part where the two differ keeps the symbolic
    form, followed by the run's value in parentheses: ``'Readback' == <wdata> (243)``.
    """
    sym, conc = _TOKEN.findall(symbolic), _TOKEN.findall(concrete)
    out: list[str] = []
    matcher = difflib.SequenceMatcher(None, sym, conc, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        sym_part, conc_part = "".join(sym[i1:i2]), "".join(conc[j1:j2])
        if op == "equal" or not sym_part.strip():
            out.append(conc_part)
        elif not conc_part.strip():
            out.append(sym_part)
        else:
            lead = sym_part[: len(sym_part) - len(sym_part.lstrip())]
            trail = sym_part[len(sym_part.rstrip()) :]
            out.append(f"{lead}{sym_part.strip()} ({conc_part.strip()}){trail}")
    return "".join(out)


def _check_result(check: Any) -> str | None:  # noqa: ANN401
    actual = getattr(check, "actual", None)
    if actual is not None:
        return f"got {_show(actual)}"
    reads = getattr(check, "reads", None) or []
    if len(reads) == 1:
        return f"got {_show(getattr(reads[0], 'value', None))}"
    if reads:
        return "got " + ", ".join(
            f"{getattr(r, 'target', '?')} = {_show(getattr(r, 'value', None))}" for r in reads
        )
    return None


def _action(action: Any, number: str) -> dict[str, Any]:  # noqa: ANN401
    """An action as a line of the executed report, like stepdoc's own."""
    op = str(getattr(action, "op", ""))
    target = str(getattr(action, "target", ""))
    direction = str(getattr(action, "direction", "in"))
    meta = getattr(action, "meta", None) or {}
    raw = getattr(action, "value", None)
    unit = f" {meta['unit']}" if isinstance(meta, dict) and meta.get("unit") else ""
    value = ""
    if raw is not None and direction != "out":
        value = _show(raw) + (unit if direction == "in" else "")
    result: str | None = None
    if direction == "out":
        result = _show(raw) + unit
    elif direction == "exchange" and isinstance(meta, dict):
        if "result" in meta:
            result = _show(meta["result"])
        elif "status" in meta:
            result = _show(meta["status"])
    count = int(getattr(action, "count", 1) or 1)
    if count > 1:
        noun = "reads" if direction == "out" else "calls"
        text = f"Poll {target} {value}".rstrip()
        result = f"{result} ({count} {noun})" if result else f"({count} {noun})"
    elif direction == "in" and op in _ASSIGN_OPS:
        text = f"{target} = {value}" if value else target
    elif op in _BARE_OPS:
        text = f"{target}  {value}".rstrip()
    else:
        text = f"{op.capitalize()} {target} {value}".rstrip()
    node: dict[str, Any] = {
        "kind": "action",
        "number": number,
        "description": text,
        "outcome": "info",
        "exc": None,
    }
    if result is not None:
        node["result"] = result
    return node


def _show(value: Any) -> str:  # noqa: ANN401
    try:
        text = repr(value)
    except Exception:  # noqa: BLE001
        text = f"<{type(value).__name__}>"
    return text if len(text) <= _MAX_VALUE else text[: _MAX_VALUE - 1] + "…"


def _exc(error: Any) -> dict[str, str] | None:  # noqa: ANN401
    """stepdoc's ``"Type: message"`` error text as the reporter's exception dict."""
    if not error:
        return None
    text = str(error)
    kind, sep, msg = text.partition(": ")
    if not sep or " " in kind:
        return {"type": "Error", "msg": text, "tb": ""}
    return {"type": kind, "msg": msg, "tb": ""}


def _float(value: Any) -> float:  # noqa: ANN401
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
