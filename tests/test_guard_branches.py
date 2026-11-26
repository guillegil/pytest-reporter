"""A guarded check (pytest-verifier's ``guard``) with every branch, as stepdoc reads it.

stepdoc 0.6 reads each branch of a ``verify.guard(...)`` call from its source:
the condition as written, and the check as written (``wording``), also for a
lazy check that was never built, plus the default. The Procedure tab lists them
all under ``Verify 'Speed by mode', depending on the condition:``, the branch
taken with its outcome and result, the others greyed out with why they were not
checked; the Generic view lists them alike. The Checks tab's guard card shows
each condition as written, and the check of a branch that was not built.

The JS runs under Node with a minimal DOM (text only), as in
``test_each_checks.py``.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from types import SimpleNamespace as NS
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter._html_builder._js import JS
from pytest_reporter._stepdoc import _check

if TYPE_CHECKING:
    from pytest import Pytester

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _reads_guards() -> bool:
    """stepdoc with ``Branch`` (every guard branch read from the source)."""
    if importlib.util.find_spec("stepdoc") is None:
        return False
    if importlib.util.find_spec("pytest_verifier") is None:
        return False
    from stepdoc.core import model

    return hasattr(model, "Branch") and "wording" in model.Branch.__dataclass_fields__


requires_guards = pytest.mark.skipif(
    not _reads_guards(), reason="needs stepdoc that reads every guard branch (Check.branches)"
)


def _leaf(text: str, passed: bool | None = None, **fields: object) -> NS:
    return NS(text=text, passed=passed, children=[], label="Speed", **fields)


def _guard(taken: int) -> NS:
    """``Speed by mode``: fast (eager), slow (lazy) and a lazy default; ``taken`` 0..2."""
    fast_holds, slow_holds = taken == 0, taken == 1
    return NS(
        text="'Speed by mode' [guarded]",
        passed=taken == 0,
        label="Speed by mode",
        selected=["fast mode", "slow mode", None][taken],
        detail=None if taken == 0 else "[→ slow mode] — expected < 10, got 42",
        children=[],
        source={"check_type": "guard", "location": "test_g.py:10", "phase": "call"},
        branches=[
            NS(
                label="fast mode",
                condition='mode == "fast"',
                holds=fast_holds,
                taken=taken == 0,
                default=False,
                check=_leaf("'Speed': speed >= 40", True if taken == 0 else None, actual=42),
                source=None,
                wording=_leaf("'Speed': speed >= LIMIT"),
            ),
            NS(
                label="slow mode",
                condition='mode == "slow"',
                holds=slow_holds if taken >= 1 else False,
                taken=taken == 1,
                default=False,
                check=(
                    _leaf("'Speed': speed < 10", False, actual=42, detail="expected < 10, got 42")
                    if taken == 1
                    else None
                ),
                source=None if taken == 1 else 'verify.less(speed, 10, name="Speed")',
                wording=_leaf("'Speed': speed < 10"),
            ),
            NS(
                label=None,
                condition=None,
                holds=None,
                taken=taken == 2,
                default=True,
                check=_leaf("'Speed': speed == 0", False, actual=42) if taken == 2 else None,
                source=None if taken == 2 else 'verify.equal(speed, 0, name="Speed")',
                wording=_leaf("'Speed': speed == 0"),
            ),
        ],
    )


def _short(branch: dict[str, Any]) -> tuple[Any, ...]:
    return (
        branch["opening"],
        branch["condition"],
        branch["label"],
        branch["state"],
        branch.get("description"),
        branch.get("outcome"),
        branch.get("result"),
    )


def test_guard_lists_every_branch() -> None:
    node = _check(_guard(1), "1.1")
    assert node["description"] == "Verify 'Speed by mode', depending on the condition:"
    assert node["generic"] == node["description"]
    assert node["description_segments"] == [{"text": node["description"], "style": None}]
    # The branches carry the result: the line has no [→ ...], result or detail
    assert "result" not in node and "detail" not in node
    assert node["outcome"] == "failed"
    assert node["location"] == "test_g.py:10"
    assert [_short(b) for b in node["branches"]] == [
        (
            "If",
            'mode == "fast"',
            "fast mode",
            "condition false",
            "Verify 'Speed': speed >= 40",
            None,
            None,
        ),
        (
            "Else if",
            'mode == "slow"',
            "slow mode",
            "taken",
            "Verify 'Speed': speed < 10",
            "failed",
            "got 42",
        ),
        ("Otherwise", None, None, "not evaluated", "Verify 'Speed': speed == 0", None, None),
    ]
    taken = node["branches"][1]
    assert taken["taken"] is True and taken["detail"] == "expected < 10, got 42"
    assert taken["description_segments"] == [
        {"text": "Verify 'Speed': ", "style": None},
        {"text": "speed < 10", "style": "mono"},
    ]
    # The Generic view words every branch as the source does (LIMIT, not 40)
    assert [b["generic"] for b in node["branches"]] == [
        "Verify 'Speed': speed >= LIMIT",
        "Verify 'Speed': speed < 10",
        "Verify 'Speed': speed == 0",
    ]
    assert node["branches"][2]["default"] is True


def test_states_after_the_branch_taken() -> None:
    first = _check(_guard(0), "1.1")
    assert [b["state"] for b in first["branches"]] == ["taken", "not evaluated", "not evaluated"]
    assert first["branches"][0]["outcome"] == "passed"
    last = _check(_guard(2), "1.1")
    assert [b["state"] for b in last["branches"]] == [
        "condition false",
        "condition false",
        "taken",
    ]
    assert last["branches"][2]["result"] == "got 42"


def test_branch_without_wording_shows_its_source() -> None:
    guard = _guard(0)
    guard.branches[1].wording = None
    guard.branches[1].condition = None
    guard.branches[1].label = None
    node = _check(guard, "1.1")
    branch = node["branches"][1]
    assert branch["label"] == "branch 2"  # neither condition nor label: by position
    assert (
        branch["description"] == branch["generic"] == 'Verify verify.less(speed, 10, name="Speed")'
    )
    assert branch["description_segments"][1] == {
        "text": 'verify.less(speed, 10, name="Speed")',
        "style": "mono",
    }


def test_unguarded_checks_are_unchanged() -> None:
    node = _check(NS(text="'A' == 1", passed=True, actual=1, children=[], selected="x"), "1.1")
    assert "branches" not in node and node["description"] == "Verify 'A' == 1 [→ x]"
    odd = _check(NS(text="x", passed=True, children=[], branches="nope"), "1.1")
    assert "branches" not in odd


_DOM = """
function Node(tag) { this.tag = tag; this.children = []; this.className = ''; this.attrs = {}; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = v; };
Node.prototype.addEventListener = function () {};
Object.defineProperty(Node.prototype, 'textContent', {
  get() { return this.text !== undefined ? this.text
                 : this.children.map(c => c.textContent).join(''); },
  set(v) { this.text = String(v); this.children = []; },
});
const document = {
  createElement: tag => new Node(tag),
  createTextNode: text => { const n = new Node('#text'); n.text = String(text); return n; },
  createDocumentFragment: () => new Node('#fragment'),
};
function findAll(node, cls, out) {
  out = out || [];
  if ((' ' + node.className + ' ').includes(' ' + cls + ' ')) out.push(node);
  node.children.forEach(c => findAll(c, cls, out));
  return out;
}
const texts = (node, cls) => findAll(node, cls).map(n => n.textContent);
function _appendCheckInline() {}
function renderCheckDetail(check) { return el('div', {className: 'leaf'}, check.description); }
"""

_FUNCTIONS = (
    "el",
    "renderFormattedDesc",
    "renderNode",
    "renderEachValues",
    "renderBranches",
    "renderGenericNode",
    "collectGuardSources",
    "checkOperand",
    "renderCheckBody",
    "renderGuardCheck",
    "renderGuardBody",
    "renderUnbuilt",
)


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    end = JS.index("\nfunction ", start + 1)
    return JS[start:end]


def _node(script: str) -> Any:  # noqa: ANN401
    source = "\n".join(
        [_DOM, "let guardSources = {};", *(_function(n) for n in _FUNCTIONS), script]
    )
    out = subprocess.run(
        ["node", "-"],
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@requires_node
def test_procedure_tab_shows_every_branch() -> None:
    node = _check(_guard(1), "1.1")
    out = _node(f"""
      const node = {json.dumps(node)};
      const run = renderNode(node, 2, false);
      const generic = renderNode(node, 2, true);
      console.log(JSON.stringify({{
        lines: texts(run, 'procedure-step-desc'),
        taken: texts(run, 'taken'),
        off: findAll(run, 'procedure-branch').filter(n => n.className.includes('not-run')).length,
        state: texts(run, 'procedure-branch-state'),
        result: texts(run, 'procedure-result'),
        exc: texts(run, 'procedure-step-exc'),
        conds: texts(run, 'procedure-branch-cond'),
        generic: texts(generic, 'procedure-step-desc'),
        genericState: findAll(generic, 'procedure-branch-state').length,
        genericDots: findAll(generic, 'status-dot').length,
      }}));
    """)
    assert out["lines"] == [
        "Verify 'Speed by mode', depending on the condition:",
        "If mode == \"fast\" (fast mode): Verify 'Speed': speed >= 40",
        "Else if mode == \"slow\" (slow mode): Verify 'Speed': speed < 10",
        "Otherwise: Verify 'Speed': speed == 0",
    ]
    assert out["taken"] == [
        "Else if mode == \"slow\" (slow mode): Verify 'Speed': speed < 10→ got 42"
        "expected < 10, got 42"
    ]
    assert out["off"] == 2
    assert out["state"] == ["condition false", "not evaluated"]
    assert out["result"] == ["→ got 42"]
    assert out["exc"] == ["expected < 10, got 42"]
    assert out["conds"] == ['mode == "fast"', 'mode == "slow"']
    assert out["generic"] == [
        "Verify 'Speed by mode', depending on the condition:",
        "If mode == \"fast\" (fast mode): Verify 'Speed': speed >= LIMIT",
        "Else if mode == \"slow\" (slow mode): Verify 'Speed': speed < 10",
        "Otherwise: Verify 'Speed': speed == 0",
    ]
    assert out["genericState"] == 0 and out["genericDots"] == 0


_RECORD = {
    "check_type": "guard",
    "name": "Speed by mode",
    "location": "test_g.py:10",
    "matched_index": 0,
    "branches": [
        {
            "condition": True,
            "label": "fast mode",
            "check": {
                "check_type": "greater_equal",
                "name": "Speed",
                "description": "Verify 'Speed' >= 40",
                "passed": True,
            },
        },
        {"condition": None, "label": "slow mode", "check": None},
    ],
    "default": None,
    "passed": True,
}


@requires_node
def test_checks_card_shows_conditions_and_unbuilt_checks() -> None:
    proc = {"steps": [{"kind": "step", "substeps": [_check(_guard(0), "1.1")]}]}
    out = _node(f"""
      guardSources = collectGuardSources({json.dumps(proc)});
      const card = renderGuardBody({json.dumps(_RECORD)});
      guardSources = {{}};
      const bare = renderGuardBody({json.dumps(_RECORD)});
      console.log(JSON.stringify({{
        conds: texts(card, 'guard-cond-src'),
        truth: texts(card, 'guard-cond'),
        kws: texts(card, 'guard-kw'),
        unbuilt: texts(card, 'guard-unbuilt'),
        chosen: findAll(card, 'chosen').length,
        bareConds: findAll(bare, 'guard-cond-src').length,
        bareKws: texts(bare, 'guard-kw'),
        bareNomatch: findAll(bare, 'guard-nomatch').length,
      }}));
    """)
    assert out["conds"] == ['mode == "fast"', 'mode == "slow"']
    assert out["truth"] == ["true", "not evaluated"]
    # The lazy default was never built: the record has no default, stepdoc does
    assert out["kws"] == ["if", "elif", "else"]
    assert out["unbuilt"] == [
        "Verify 'Speed': speed < 10not run",
        "Verify 'Speed': speed == 0not run",
    ]
    assert out["chosen"] == 1
    # Without stepdoc the card shows what the record has
    assert out["bareConds"] == 0 and out["bareKws"] == ["if", "elif"]
    assert out["bareNomatch"] == 0


@requires_guards
def test_guard_end_to_end(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_g="""
        import pytest
        from stepdoc import step

        LIMIT = 40

        @pytest.mark.parametrize("mode", ["fast", "slow"])
        def test_speed(verify, mode):
            speed = 42
            with step("Check the speed"):
                verify.guard(
                    [
                        (mode == "fast", "fast mode",
                         verify.greater_equal(speed, LIMIT, name="Speed")),
                        (mode == "slow", "slow mode",
                         lambda: verify.less(speed, 10, name="Speed")),
                    ],
                    default=lambda: verify.equal(speed, 0, name="Speed"),
                    name="Speed by mode",
                )
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1, failed=1)
    (run,) = sorted((pytester.path / "reports" / "runs").iterdir())
    folder = run / "tests" / "test_g.py" / "test_speed"

    def guard(run_id: str) -> dict[str, Any]:
        path = folder / run_id / "procedure.json"
        (check,) = json.loads(path.read_text(encoding="utf-8"))["steps"][0]["substeps"]
        return check

    fast, slow = guard("01"), guard("02")
    assert fast["description"] == "Verify 'Speed by mode', depending on the condition:"
    assert fast["location"] == "test_g.py:10"
    assert [_short(b) for b in slow["branches"]] == [
        (
            "If",
            'mode == "fast"',
            "fast mode",
            "condition false",
            "Verify 'Speed': speed >= 40",
            None,
            None,
        ),
        (
            "Else if",
            'mode == "slow"',
            "slow mode",
            "taken",
            "Verify 'Speed': speed < 10",
            "failed",
            "got 42",
        ),
        ("Otherwise", None, None, "not evaluated", "Verify 'Speed': speed == 0", None, None),
    ]
    assert fast["branches"][0]["generic"] == "Verify 'Speed': speed >= LIMIT"
    assert [b["state"] for b in fast["branches"]] == ["taken", "not evaluated", "not evaluated"]
    html = (run / "report.html").read_text(encoding="utf-8")
    assert "renderBranches" in html and "procedure-branch" in html
