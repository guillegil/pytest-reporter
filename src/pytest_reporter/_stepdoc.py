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
stepdoc also parses each test function's docstring once and hands it to
``pytest_stepdoc_test_doc``: it becomes ``procedure.json``'s ``doc`` and the
"About this test" block of the run's Summary sub-tab (:func:`doc_html_data`).

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
from collections.abc import Mapping
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
# Number prefix of a section's top-level steps (the procedure's own have none).
_PREFIX = {"precondition": "P", "setup": "S", "teardown": "T"}
_ASSIGN_OPS = {"write", "set"}
_BARE_OPS = {"request"}
_MAX_VALUE = 200
_TICKS = re.compile(r"`+")
# Words (with a decimal part), <names>, runs of spaces, or any other character.
_TOKEN = re.compile(r"<[^<>\s]+>|\w+(?:\.\w+)*|\s+|.")
# A check text's parts: ``'<name>': `` (a name given beside the checked
# expression), then the expression, the operator and the expected side.
_OPERATOR = re.compile(r" (?:==|!=|>=|<=|>|<|∈|∉|is not|is) ")
# A test's docstring as stepdoc parsed it (pytest_stepdoc_test_doc): its
# sections, in the order shown, with the label each one has in the report.
DOC_SECTIONS = (
    ("description", None),
    ("objective", "Objective"),
    ("acceptance", "Acceptance criteria"),
)
# List items of a docstring section: ``- item`` / ``* item``, ``1. item`` / ``1) item``.
_BULLET = re.compile(r"([-*])\s+(.*)")
_NUMBER = re.compile(r"(\d+)([.)])\s+(.*)")


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


def clean_doc(doc: Any) -> dict[str, str] | None:  # noqa: ANN401
    """The sections of a ``pytest_stepdoc_test_doc`` dict that have text.

    Args:
        doc: The dict stepdoc passed (``description``, ``objective``,
            ``acceptance``; each a str).

    Returns:
        A copy with only the known keys whose value is non-blank text, or
        ``None`` when nothing is left.
    """
    if not isinstance(doc, Mapping):
        return None
    out = {key: doc[key] for key, _ in DOC_SECTIONS if isinstance(doc.get(key), str)}
    out = {key: text for key, text in out.items() if text.strip()}
    return out or None


def doc_blocks(text: str) -> list[dict[str, Any]]:
    """Paragraphs and lists of one docstring section, for the HTML report.

    Follows stepdoc's own reading of a section (``stepdoc.renderers.common.
    doc_blocks``): lines of a paragraph are joined by a space and a blank line
    ends it; ``-``/``*`` items make a bullet list and ``1.``/``1)`` items a
    numbered one that keeps the author's numbers, indented or not; a line
    under an item (indented past its marker, or right after it and not left of
    it) joins that item; a numbered line right after paragraph text starts a
    list only at 1.

    Args:
        text: One section's text, as stepdoc gave it.

    Returns:
        Blocks ``{"kind": "p" | "ul" | "ol", "items": [...]}``; each item has
        ``segments`` (backtick spans as ``mono``, see :func:`title_segments`)
        and, in a numbered list, its ``number``.
    """
    blocks: list[dict[str, Any]] = []
    marker = -1  # indent of the open list item's marker; -1: no open item
    gap = False  # a blank line since the last text
    for line in text.split("\n"):
        body = line.lstrip()
        if not body:
            gap = True
            continue
        indent = len(line) - len(body)
        bullet, number = _BULLET.fullmatch(body), _NUMBER.fullmatch(body)
        last = blocks[-1] if blocks else None
        # As in CommonMark, a numbered line right after paragraph text starts a
        # list only at 1 ("... reaches\n512. Then" is one paragraph).
        if number and last is not None and last["kind"] == "p" and not gap:
            if int(number.group(1)) != 1:
                number = None
        if bullet or number:
            kind = "ul" if bullet else "ol"
            if last is None or last["kind"] != kind:
                last = {"kind": kind, "items": []}
                blocks.append(last)
            item: dict[str, Any]
            if number:
                item = {"text": number.group(3).strip(), "number": int(number.group(1))}
            else:
                assert bullet is not None
                item = {"text": bullet.group(2).strip()}
            last["items"].append(item)
            marker = indent
        elif last is not None and (
            (marker >= 0 and (indent > marker or (not gap and indent >= marker)))
            or (last["kind"] == "p" and not gap)
        ):
            last["items"][-1]["text"] += " " + body
        else:
            blocks.append({"kind": "p", "items": [{"text": body}]})
            marker = -1
        gap = False
    for block in blocks:
        for item in block["items"]:
            text_ = item.pop("text")
            item["segments"] = title_segments(text_) or [{"text": text_, "style": None}]
    return blocks


def doc_html_data(doc: Mapping[str, str] | None) -> list[dict[str, Any]] | None:
    """A test's docstring for the HTML report's "About this test" block.

    Args:
        doc: The parsed docstring (:func:`clean_doc`), or ``None``.

    Returns:
        The sections with text, in order: ``{"key", "title", "blocks"}``
        (``title`` is ``None`` for the description); ``None`` without a doc.
    """
    if not doc:
        return None
    out = []
    for key, title in DOC_SECTIONS:
        text = doc.get(key)
        blocks = doc_blocks(text) if isinstance(text, str) else []
        if blocks:
            out.append({"key": key, "title": title, "blocks": blocks})
    return out or None


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
        # nodeid -> the test's parsed docstring (pytest_stepdoc_test_doc). Given
        # once, before any attempt runs, so it is kept for every attempt.
        self._docs: dict[str, dict[str, str]] = {}
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

    def test_doc(self, item: pytest.Item, doc: Any) -> None:  # noqa: ANN401
        """``pytest_stepdoc_test_doc``: keep the test's parsed docstring."""
        cleaned = clean_doc(doc)
        if cleaned:
            self._docs[item.nodeid] = cleaned

    def doc(self, nodeid: str) -> dict[str, str] | None:
        """The parsed docstring of ``nodeid``, when stepdoc gave one."""
        return self._docs.get(nodeid)

    def procedure(self, nodeid: str) -> dict[str, Any]:
        """The ``procedure.json`` document of the current attempt of ``nodeid``.

        ``doc`` (the test's docstring sections) is added next to ``steps`` only
        when the test has one.
        """
        steps = self._steps.get(nodeid, [])
        doc = self._docs.get(nodeid)
        extra: dict[str, Any] = {"doc": dict(doc)} if doc else {}
        if not steps:
            return {"steps": [], **extra}
        # Pre-conditions (stepdoc.precondition) open the procedure. stepdoc calls
        # the hooks for the ones a shared fixture established for an earlier
        # test at the end of setup, after the ones this attempt applied itself:
        # they are listed first, as in stepdoc's own documents.
        pre = [s for s in steps if _section(s) == "precondition"]
        ordered = [
            *(s for s in pre if _applied_in(s) is not None),
            *(s for s in pre if _applied_in(s) is None),
            *(s for s in steps if _section(s) != "precondition"),
        ]
        counters: dict[str, int] = {}
        nodes = []
        for step in ordered:
            section = _section(step)
            counters[section] = counters.get(section, 0) + 1
            nodes.append(self._step(step, f"{_PREFIX.get(section, '')}{counters[section]}"))
        return {"steps": nodes, "source": "stepdoc", **extra}

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
            "section": _section(step),
        }
        applied_in = _applied_in(step)
        if applied_in is not None:
            # Not run in this attempt: the status is the one it got when applied.
            node["applied_in"] = applied_in
            node["end_time"] = node["start_time"]
            node["duration_seconds"] = 0.0
        loop = getattr(step, "loop", None)
        if loop is not None:  # a titled stepdoc.repeat(): its entries are one pass
            node["description"] += f" ({_loop_words(loop)})"
            result = _times(getattr(loop, "count", None))
            if result:
                node["result"] = result
        segments = title_segments(node["description"])
        if segments is not None:
            node["description_segments"] = segments
        _add_note(node, step)
        children = [
            self._entry(e, f"{number}.{i}")
            for i, e in enumerate(getattr(step, "entries", None) or [], 1)
        ]
        if children:
            node["substeps"] = children
        return node

    def _entry(self, entry: Any, number: str) -> dict[str, Any]:  # noqa: ANN401
        if hasattr(entry, "entries") and hasattr(entry, "until"):  # before steps: both have titles
            return self._repeat(entry, number)
        if hasattr(entry, "entries") and hasattr(entry, "title"):
            return self._step(entry, number)
        if hasattr(entry, "passed") and hasattr(entry, "text"):
            return _check(entry, number)
        return _action(entry, number)

    def _repeat(self, repeat: Any, number: str) -> dict[str, Any]:  # noqa: ANN401
        """A loop stepdoc collapsed (stepdoc 0.3+): one pass, and how many ran."""
        words = _loop_words(repeat)
        description = words[0].upper() + words[1:]
        title = getattr(repeat, "title", None)
        if title:  # an earlier stepdoc 0.3 build named repeat entries
            description = f"{title} ({words})"
        children = [
            self._entry(e, f"{number}.{i}")
            for i, e in enumerate(getattr(repeat, "entries", None) or [], 1)
        ]
        outcomes = [c["outcome"] for c in children if c["kind"] != "action"]
        node: dict[str, Any] = {
            "kind": "repeat",
            "number": number,
            "description": description,
            "outcome": max(outcomes, key=lambda o: _RANK.get(o, 0)) if outcomes else "info",
            "exc": None,
        }
        result = _times(getattr(repeat, "count", None))
        if result:
            node["result"] = result
        _add_note(node, repeat)
        if children:
            node["substeps"] = children
        return node


def _section(step: Any) -> str:  # noqa: ANN401
    """``precondition``, ``setup``, ``procedure`` or ``teardown``."""
    return str(getattr(step, "section", "procedure") or "procedure")


def _applied_in(step: Any) -> str | None:  # noqa: ANN401
    """The test that applied a pre-condition this attempt found established.

    stepdoc sets ``Step.applied_in`` on the entry it adds to a test that uses a
    shared fixture (session, module or class scope) whose pre-condition an
    earlier test applied. ``None`` for every other step, and with a stepdoc
    that has no pre-conditions.
    """
    value = getattr(step, "applied_in", None)
    return value if isinstance(value, str) and value else None


def _loop_words(loop: Any) -> str:  # noqa: ANN401
    """``repeat until FIFO is empty, counting write_count``, as stepdoc writes it."""
    until = getattr(loop, "until", None)
    words = f"repeat until {until}" if until else "repeat"
    counter = getattr(loop, "counter", None)
    if counter:
        inc = getattr(loop, "inc", None)
        if not isinstance(inc, (int, float)) or isinstance(inc, bool) or inc == 1:
            words += f", counting {counter}"
        else:
            sign = "+" if inc >= 0 else "-"
            words += f", {counter} {sign}{_number(abs(inc))} each pass"
    return words


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _times(count: Any) -> str | None:  # noqa: ANN401
    if not isinstance(count, int) or isinstance(count, bool):
        return None
    return "once" if count == 1 else f"{count} times"


def _add_note(node: dict[str, Any], source: Any) -> None:  # noqa: ANN401
    """stepdoc's ``note=`` on a step, repeat or check: a sentence for the reader.

    A check's note is pytest-verifier's ``note=`` or the source comment stepdoc
    found at the check; the Procedure tab shows it after the text, in parentheses.
    """
    note = getattr(source, "note", None)
    if isinstance(note, str) and note.strip():
        node["note"] = note.strip()


# Worst outcome wins, as in the Procedure tab.
_RANK = {"error": 5, "failed": 4, "unknown": 3, "passed": 2, "skipped": 1, "info": 0}


def _check(check: Any, number: str) -> dict[str, Any]:  # noqa: ANN401
    passed = getattr(check, "passed", None)
    text = str(getattr(check, "text", ""))
    symbolic = getattr(check, "symbolic_text", None)
    if not isinstance(symbolic, str) or not symbolic or symbolic == text:
        symbolic = None
    names = _operand_names(check)
    # The check without this run's values: the Procedure tab's Generic view
    generic = symbolic if symbolic is not None else text
    operands = getattr(check, "operands", None)
    if isinstance(operands, dict) and operands:
        # stepdoc worded both texts with the operand names itself: this run's
        # (reg3.F == wdata (243)) and the generic one (reg<channel>.F == <wdata>)
        named = None
    else:
        named = _named_text(names, text, symbolic) if names else None
        if named is not None:
            generic = _named_generic(names, text, symbolic) or generic
            text = named
        elif symbolic is not None:
            text = with_values(symbolic, text)
    selected = getattr(check, "selected", None)
    if selected:
        text += f" [→ {selected}]"
        generic += f" [→ {selected}]"
    label = getattr(check, "label", None)
    index = getattr(check, "index", None)
    head = "Verify "
    if isinstance(index, int) and not isinstance(index, bool):
        # One failed item of a check stepdoc folded into one line (all_satisfy)
        head, label = f"Verify item [{index}]: ", None
    node: dict[str, Any] = {
        "kind": "check",
        "number": number,
        "description": f"{head}{text}",
        "description_segments": _check_segments(text, label, head),
        "generic": f"Verify {generic}",
        "generic_segments": _check_segments(generic, label),
        "outcome": "unknown" if passed is None else ("passed" if passed else "failed"),
        "exc": None,
    }
    # The checked value's name as this run has it, when the text shows another
    # form of it (the symbolic one): "got tb.dev.map.block.reg3.F = 240".
    actual_name = names.get("actual_name") if named is not None else None
    for key in ("actual_name", "expected_name"):
        if names.get(key):
            node[key] = names[key]
    result = _check_result(
        check, actual_name if actual_name and names.get("actual_name_symbolic") else None
    )
    each = _each(check)
    if each is not None:
        node["each"] = each
        result = _each_result(each, passed is not None)
    if result is not None:
        node["result"] = result
    _add_note(node, check)
    detail = getattr(check, "detail", None)
    if detail and not (each and each["failed_items"]):
        # A folded check lists its failed items itself
        node["detail"] = str(detail)
    children = [
        _check(child, f"{number}.{i}")
        for i, child in enumerate(getattr(check, "children", None) or [], 1)
    ]
    if children:
        node["substeps"] = children
    branches = _branches(check)
    if branches is not None:
        _guarded(node, check, branches)
    return node


def _guarded(node: dict[str, Any], check: Any, branches: list[dict[str, Any]]) -> None:  # noqa: ANN401
    """Word a guarded check as stepdoc does: its name, then every branch.

    The line reads ``Verify 'Speed by mode', depending on the condition:``;
    the branches carry the rest (the condition, the check, the result), so the
    line loses the ``[→ fast mode]`` suffix, its result and its detail. The
    pytest-verifier record's ``location`` comes along: the Checks tab finds the
    branches' source wording by it.
    """
    label = getattr(check, "label", None)
    text = (
        f"'{label}', depending on the condition:"
        if isinstance(label, str) and label
        else "depending on the condition:"
    )
    for key in ("description", "generic"):
        node[key] = f"Verify {text}"
        node[f"{key}_segments"] = [{"text": node[key], "style": None}]
    for key in ("result", "detail"):
        node.pop(key, None)
    node["branches"] = branches
    source = getattr(check, "source", None)
    location = source.get("location") if isinstance(source, Mapping) else None
    if isinstance(location, str) and location:
        node["location"] = location


def _branches(check: Any) -> list[dict[str, Any]] | None:  # noqa: ANN401
    """stepdoc's ``Check.branches``: every branch of a guarded check (stepdoc 0.6+).

    pytest-verifier's ``guard`` checks the first branch whose condition holds,
    else its default. stepdoc reads every branch from the call's source: the
    condition as written, and the check as written (``wording``, test
    parameters as ``<name>``), also for a lazy check that was never built. Each
    branch becomes ``{"opening", "condition", "label", "default", "taken",
    "state", ...}`` with the line's texts: this run's for the branch taken
    (with its outcome, result and detail), the check this run built or else
    its wording for the others, and the wording for the Generic view.
    ``state`` is ``taken``, ``condition false`` (a branch before the one taken)
    or ``not evaluated``. None for a check that is not guarded.
    """
    raw = getattr(check, "branches", None)
    if not isinstance(raw, (list, tuple)) or not raw:
        return None
    out: list[dict[str, Any]] = []
    seen_taken = False
    for i, branch in enumerate(raw):
        is_default = getattr(branch, "default", False) is True
        taken = getattr(branch, "taken", False) is True
        holds = getattr(branch, "holds", None)
        condition = getattr(branch, "condition", None)
        label = getattr(branch, "label", None)
        condition = condition if isinstance(condition, str) and condition else None
        label = label if isinstance(label, str) and label else None
        if is_default:
            opening, condition, label = "Otherwise", None, None
        else:
            opening = "If" if i == 0 else "Else if"
            if condition is None and label is None:
                label = f"branch {i + 1}"
        if taken:
            state = "taken"
            seen_taken = True
        elif holds is False and not seen_taken:
            state = "condition false"
        else:
            state = "not evaluated"
        node: dict[str, Any] = {
            "opening": opening,
            "condition": condition,
            "label": label,
            "default": is_default,
            "taken": taken,
            "state": state,
        }
        built, wording = getattr(branch, "check", None), getattr(branch, "wording", None)
        shown = built if built is not None else wording
        generic = wording if wording is not None else built
        if shown is not None:
            line = _check(shown, "")
            for key in ("description", "description_segments", "note"):
                if key in line:
                    node[key] = line[key]
            if taken:
                for key in ("outcome", "result", "detail", "each", "substeps", "branches"):
                    if key in line:
                        node[key] = line[key]
        if generic is not None:
            line = _check(generic, "")
            node["generic"] = line["generic"]
            node["generic_segments"] = line["generic_segments"]
        source = getattr(branch, "source", None)
        if isinstance(source, str) and source:
            # A check that was not built and has no wording: the call as written
            for key in ("description", "generic"):
                if key not in node:
                    node[key] = f"Verify {source}"
                    node[f"{key}_segments"] = [
                        {"text": "Verify ", "style": None},
                        {"text": source, "style": "mono"},
                    ]
        out.append(node)
    return out


def _each(check: Any) -> dict[str, Any] | None:  # noqa: ANN401
    """stepdoc's ``Check.each``: one check per item, folded into one line.

    pytest-verifier's ``all_satisfy`` checks every item of a collection. stepdoc
    words it as ``for each w in waveforms, <check>`` and keeps only the failed
    items as children. The node carries how many items there were, how many
    failed, which ones (``failed_items``, their positions from 0) and the value
    each item's check got (``values``; stepdoc keeps the first and last 32 of a
    longer list, ``values_cut`` then says so).
    """
    each = getattr(check, "each", None)
    count, failed = getattr(each, "count", None), getattr(each, "failed", None)
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        return None
    failed = failed if isinstance(failed, int) and not isinstance(failed, bool) else 0
    values = getattr(each, "values", None)
    values = list(values) if isinstance(values, (list, tuple)) else []
    indices = [
        i
        for i in (getattr(c, "index", None) for c in getattr(check, "children", None) or [])
        if isinstance(i, int) and not isinstance(i, bool)
    ]
    node: dict[str, Any] = {
        "count": count,
        "failed": failed,
        "failed_items": indices,
        "values": [_show(v) for v in values],
        "values_cut": len(values) < count,
    }
    for key in ("item", "items"):
        word = getattr(each, key, None)
        if isinstance(word, str) and word:
            node[key] = word
    return node


def _each_result(each: dict[str, Any], judged: bool) -> str:
    count, failed = each["count"], each["failed"]
    if not judged:
        return f"{count} item{'' if count == 1 else 's'}"
    return f"{failed} of {count} failed" if failed else f"{count} of {count} passed"


def _check_segments(text: str, label: Any, verb: str = "Verify ") -> list[dict[str, Any]]:  # noqa: ANN401
    """A check's line as segments: the words plain, the code in monospace.

    ``Verify`` and the check's name (``'Stored word':``) are words; the checked
    expression, the comparison and the operand names are code. The name is
    stepdoc's ``Check.label`` when the text starts with it in quotes, else what
    stands before the first ``': `` of a text that opens with a quote.
    """
    head = ""
    if isinstance(label, str) and label:
        for quoted in (f"'{label}': ", f"'{label}' "):
            if text.startswith(quoted) and len(text) > len(quoted):
                head = quoted
                break
    elif text.startswith("'"):
        end = text.find("': ", 1)
        if 0 < end < len(text) - 3:
            head = text[: end + 3]
    return [
        {"text": f"{verb}{head}", "style": None},
        {"text": text[len(head) :], "style": "mono"},
    ]


_NAME_KEYS = ("actual_name", "actual_name_symbolic", "expected_name", "expected_name_symbolic")
_REST_OPERATOR = re.compile(r"(?:==|!=|>=|<=|>|<|∈|∉|is not|is) ")


def _operand_names(check: Any) -> dict[str, str]:  # noqa: ANN401
    """The operand names of a pytest-verifier check (``actual_name=``, ``expected_name=``).

    stepdoc keeps the record it built a check from as ``Check.source``. The
    record has each name as this run spells it (``tb.dev.map.block.reg3.F``)
    and, when pytest-verifier knows it, with every interpolation as
    ``<expression>`` (``tb.dev.map.block.reg<channel>.F``, the ``_symbolic``
    key). Its ``name``, ``auto_name`` and ``description`` come along, for
    :func:`_named_text`. Empty when the check has no operand name.
    """
    source = getattr(check, "source", None)
    if not isinstance(source, Mapping):
        return {}
    names = {
        key: source[key].strip()
        for key in _NAME_KEYS
        if isinstance(source.get(key), str) and source[key].strip()
    }
    if "actual_name" not in names and "expected_name" not in names:
        return {}
    for key in ("name", "description"):
        if isinstance(source.get(key), str):
            names[key] = source[key]
    if source.get("auto_name") is True:
        names["auto_name"] = "true"
    return names


def _named_text(names: dict[str, str], text: str, symbolic: str | None) -> str | None:
    """A check's procedure text, worded with its operand names.

    The procedure reads as the test is written, so each name shows its symbolic
    form when there is one: ``tb.dev.map.block.reg<channel>.F == wdata (243)``,
    or ``'Stored word': tb.dev.map.block.reg<channel>.F == wdata (243)`` for a
    check that also has a ``name=``. The expected side is pytest-verifier's own
    (the name, then this run's value); without an ``expected_name`` it is
    stepdoc's, as :func:`with_values` shows it (``== <wdata> (243)``). Without
    an ``actual_name`` the checked value keeps stepdoc's wording.

    Returns:
        The text, or ``None`` when the record's description has another shape
        (the check then reads as stepdoc worded it).
    """
    name = names.get("name")
    description = names.get("description", "")
    prefix = f"Verify '{name}' "
    if name is None or not description.startswith(prefix):
        return None
    rest = description[len(prefix) :]
    if not rest or not text.endswith(rest):
        return None

    actual = names.get("actual_name")
    if actual is not None:
        label = "" if names.get("auto_name") else f"'{name}': "
        left = f"{label}{names.get('actual_name_symbolic', actual)} "
    else:
        left = text[: len(text) - len(rest)]

    expected = names.get("expected_name")
    if expected is not None:
        right = _expected_symbolic(rest, expected, names.get("expected_name_symbolic", expected))
    else:
        right = _symbolic_rest(rest, symbolic, text[: len(text) - len(rest)])
    return left + right


def _named_generic(names: dict[str, str], text: str, symbolic: str | None) -> str | None:
    """A check :func:`_named_text` worded, without this run's values.

    For a stepdoc that does not word checks with operand names itself: the
    symbolic ``actual_name``, then the expected side as stepdoc's symbolic text
    has it (``tb.dev.map.block.reg<channel>.F == <wdata>``). ``None`` when
    there is no ``actual_name`` or the expected side cannot be told apart.
    """
    actual = names.get("actual_name")
    name = names.get("name")
    rest = names.get("description", "")[len(f"Verify '{name}' ") :]
    if actual is None or not rest:
        return None
    operator = _REST_OPERATOR.match(rest)
    if operator is None:
        return None
    right = rest[operator.end() :]
    if symbolic is not None:
        found = _symbolic_right(rest, symbolic, text[: len(text) - len(rest)])
        if found is None:
            return None
        right = found
    elif "expected_name" in names:
        return None  # the description's value cannot be told from the name
    label = "" if names.get("auto_name") else f"'{name}': "
    return f"{label}{names.get('actual_name_symbolic', actual)} {operator.group()}{right}"


def _expected_symbolic(rest: str, expected: str, symbolic: str) -> str:
    """``rest`` (``== wdata (243)``) with the expected name in its symbolic form.

    pytest-verifier writes the name after the operator words and before the
    value in parentheses, so that occurrence is the one replaced: a name whose
    text also occurs in the operator (``has length``, ``==``) leaves it alone.
    """
    if symbolic == expected:
        return rest
    operator = _REST_OPERATOR.match(rest)
    start = operator.end() if operator else 0
    found = rest.find(f"{expected} (", start)
    if found < 0:
        found = rest.find(expected, start)
    if found < 0:
        return rest
    return rest[:found] + symbolic + rest[found + len(expected) :]


def _symbolic_rest(rest: str, symbolic: str | None, left: str = "") -> str:
    """``rest`` (``== 243``) with the names stepdoc found for it: ``== <wdata> (243)``.

    ``left`` is this run's text before ``rest``. The checked expression or the
    check's name may hold the operator too (``a == b == <flag>``,
    ``'x == y' == <wdata>``), so the operator that starts the expected side in
    the symbolic text is the one after as many operators as ``left`` has.
    """
    operator = _REST_OPERATOR.match(rest)
    sym_right = _symbolic_right(rest, symbolic, left)
    if operator is None or sym_right is None:
        return rest
    return operator.group() + _annotate(sym_right, rest[operator.end() :])


def _symbolic_right(rest: str, symbolic: str | None, left: str) -> str | None:
    """What follows the operator of ``rest`` in stepdoc's symbolic text, or ``None``."""
    operator = _REST_OPERATOR.match(rest)
    if symbolic is None or operator is None:
        return None
    needle = f" {operator.group()}"
    found = -1
    for _ in range((left + operator.group()).count(needle)):
        found = symbolic.find(needle, found + 1)
        if found < 0:
            return None
    if found < 0:
        return None
    return symbolic[found + len(needle) :]


def with_values(symbolic: str, concrete: str) -> str:
    """A check's symbolic text with this run's values after the names they replace.

    stepdoc's procedure reads ``'Readback' == <wdata>``; this run's check reads
    ``'Readback' == 243``. Each part where the two differ keeps the symbolic
    form, followed by the run's value in parentheses: ``'Readback' == <wdata> (243)``.

    The checked value before the operator is shown as this run has it: the
    procedure's ``dev.blk.esmi<channel>_ctl.tx == 1`` reads
    ``dev.blk.esmi3_ctl.tx == 1``, and a name given to the check
    (``'Ready': dev.blk.esmi<channel>_ctl.tx == 1``) is kept.
    """
    head = _name_prefix(symbolic, concrete)
    if head:
        return head + with_values(symbolic[len(head) :], concrete[len(head) :])
    sym_op, conc_op = _OPERATOR.search(symbolic), _OPERATOR.search(concrete)
    if sym_op and conc_op and sym_op.group() == conc_op.group():
        left = concrete[: conc_op.start()]
        if symbolic[: sym_op.start()] != left:
            right = _annotate(symbolic[sym_op.end() :], concrete[conc_op.end() :])
            return left + conc_op.group() + right
    return _annotate(symbolic, concrete)


def _name_prefix(symbolic: str, concrete: str) -> str:
    """The ``'<name>': `` both texts start with, or ``""``.

    stepdoc writes the name raw (``f"'{name}': "``), so a name may hold an
    apostrophe or an operator. The prefix ends at the first ``': ``, and counts
    only when the run's text starts with it too.
    """
    if not symbolic.startswith("'"):
        return ""
    end = symbolic.find("': ", 1)
    if end < 0:
        return ""
    head = symbolic[: end + 3]
    return head if concrete.startswith(head) else ""


def _annotate(symbolic: str, concrete: str) -> str:
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


def _check_result(check: Any, actual_name: str | None = None) -> str | None:  # noqa: ANN401
    actual = getattr(check, "actual", None)
    if actual is not None:
        return f"got {actual_name} = {_show(actual)}" if actual_name else f"got {_show(actual)}"
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
    if count > 1 and direction != "in":  # polling: the same read or request again
        noun = "reads" if direction == "out" else "calls"
        text = f"Poll {target} {value}".rstrip()
        result = f"{result} ({count} {noun})" if result else f"({count} {noun})"
    elif direction == "in" and op in _ASSIGN_OPS:
        text = f"{target} = {value}" if value else target
    elif op in _BARE_OPS:
        text = f"{target}  {value}".rstrip()
    else:
        text = f"{op.capitalize()} {target} {value}".rstrip()
    if count > 1 and direction == "in":  # the same write again, from one line (a loop)
        plain = op in _ASSIGN_OPS or op in _BARE_OPS
        text = "Repeat " + (text if plain else f"{op} {target} {value}".rstrip())
        result = f"({count} times)"
    node: dict[str, Any] = {
        "kind": "action",
        "number": number,
        "description": text,
        "outcome": "info",
        "exc": None,
    }
    if result is not None:
        node["result"] = result
    generic, bound = _action_generic(action)
    if generic != text:
        node["generic"] = generic
    if bound is not None:
        node["generic_result"] = bound
    return node


def _action_generic(action: Any) -> tuple[str, str | None]:  # noqa: ANN401
    """An action without this run's values, as stepdoc's procedure words it.

    The target and the value are the symbolic ones stepdoc found
    (``dev.reg<channel> = <wdata>``); a value it found no name for stays this
    run's. A read shows the name its value was bound to (``<rdata>``).
    """
    op = str(getattr(action, "op", ""))
    direction = str(getattr(action, "direction", "in"))
    target = getattr(action, "symbolic_target", None)
    if not isinstance(target, str) or not target:
        target = str(getattr(action, "target", ""))
    value = ""
    if direction != "out":
        symbolic = getattr(action, "symbolic_value", None)
        raw = getattr(action, "value", None)
        if isinstance(symbolic, str) and symbolic:
            value = symbolic
        elif raw is not None:
            value = _show(raw)
    bound = getattr(action, "bound_to", None)
    result = f"<{bound}>" if direction == "out" and isinstance(bound, str) and bound else None
    count = int(getattr(action, "count", 1) or 1)
    if count > 1 and direction != "in":
        return f"Poll {target} {value}".rstrip(), result
    if direction == "in" and op in _ASSIGN_OPS:
        text = f"{target} = {value}" if value else target
    elif op in _BARE_OPS:
        text = f"{target}  {value}".rstrip()
    else:
        text = f"{op.capitalize()} {target} {value}".rstrip()
    if count > 1:
        plain = op in _ASSIGN_OPS or op in _BARE_OPS
        text = "Repeat " + (text if plain else f"{op} {target} {value}".rstrip())
    return text, result


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
