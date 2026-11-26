"""A check made once per item (pytest-verifier's ``all_satisfy``) as one line.

stepdoc folds the item checks that read the same into one check, ``for each w
in waveforms, w & INDEX_ERROR_BIT == 0``, with ``Check.each`` (how many items,
how many failed, the value each got) and only the failed items as children,
each with its ``index``. The Procedure tab shows the line with ``12 of 12
passed`` or ``2 of 12 failed``, the failed items under it and a closed list of
every item's value; the Generic view shows the line alone.

The JS runs under Node with a minimal DOM (text only), as in
``test_operand_names.py``.
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

LINE = "'Index error clear': for each w in waveforms, w & INDEX_ERROR_BIT == 0"


def _folds_all_satisfy() -> bool:
    """stepdoc with ``Check.each`` and a pytest-verifier that names the items."""
    if importlib.util.find_spec("stepdoc") is None:
        return False
    if importlib.util.find_spec("pytest_verifier") is None:
        return False
    import stepdoc
    from pytest_verifier import CheckDescriptor

    return hasattr(stepdoc, "Each") and "item_name" in CheckDescriptor.__annotations__


requires_folding = pytest.mark.skipif(
    not _folds_all_satisfy(),
    reason="needs stepdoc with Check.each and pytest-verifier with item_name",
)


def _item(index: int, actual: object) -> NS:
    return NS(
        text="w & INDEX_ERROR_BIT == 0",
        passed=False,
        actual=actual,
        index=index,
        children=[],
        detail="expected 0, got 64",
    )


def _folded(values: list[int], count: int | None = None, **fields: object) -> NS:
    bad = [i for i, v in enumerate(values) if v]
    base: dict[str, Any] = {
        "text": LINE,
        "label": "Index error clear",
        "passed": not bad,
        "detail": "expected all to pass" if bad else None,
        "children": [_item(i, values[i]) for i in bad],
        "each": NS(
            count=len(values) if count is None else count,
            failed=len(bad),
            item="w",
            items="waveforms",
            values=values,
        ),
    }
    base.update(fields)
    return NS(**base)


def test_all_items_passed() -> None:
    node = _check(_folded([0] * 12), "20.1")
    assert node["description"] == f"Verify {LINE}"
    assert node["generic"] == f"Verify {LINE}"
    assert node["result"] == "12 of 12 passed"
    assert node["outcome"] == "passed"
    assert "substeps" not in node
    assert node["each"] == {
        "count": 12,
        "failed": 0,
        "failed_items": [],
        "values": ["0"] * 12,
        "values_cut": False,
        "item": "w",
        "items": "waveforms",
    }
    assert node["description_segments"] == [
        {"text": "Verify 'Index error clear': ", "style": None},
        {"text": "for each w in waveforms, w & INDEX_ERROR_BIT == 0", "style": "mono"},
    ]


def test_failed_items_are_listed_with_their_index() -> None:
    values = [0, 0, 0, 64, 0, 0, 0, 0, 0, 64, 0, 0]
    node = _check(_folded(values), "20.1")
    assert node["result"] == "2 of 12 failed"
    assert node["outcome"] == "failed"
    # The items say what failed: the summary text is not repeated under the line
    assert "detail" not in node
    assert node["each"]["failed_items"] == [3, 9]
    items = node["substeps"]
    assert [(s["number"], s["description"], s["result"]) for s in items] == [
        ("20.1.1", "Verify item [3]: w & INDEX_ERROR_BIT == 0", "got 64"),
        ("20.1.2", "Verify item [9]: w & INDEX_ERROR_BIT == 0", "got 64"),
    ]
    assert items[0]["description_segments"] == [
        {"text": "Verify item [3]: ", "style": None},
        {"text": "w & INDEX_ERROR_BIT == 0", "style": "mono"},
    ]
    assert items[0]["outcome"] == "failed"


def test_not_judged_and_cut_values() -> None:
    dry = _check(_folded([0, 0], passed=None), "1.1")
    assert (dry["result"], dry["outcome"]) == ("2 items", "unknown")
    one = _check(_folded([0], passed=None), "1.1")
    assert one["result"] == "1 item"
    # stepdoc keeps the first and the last 32 values of a longer list
    cut = _check(_folded([0] * 64, count=1000), "1.1")
    assert cut["each"]["values_cut"] is True and cut["result"] == "1000 of 1000 passed"


def test_checks_without_each_are_unchanged() -> None:
    node = _check(NS(text="'A' == 1", passed=True, actual=1, children=[]), "1.1")
    assert "each" not in node and node["result"] == "got 1"
    odd = _check(NS(text="x", passed=True, children=[], each=NS(count="12", failed=0)), "1.1")
    assert "each" not in odd


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
"""

_FUNCTIONS = (
    "el",
    "renderFormattedDesc",
    "renderNode",
    "renderEachValues",
    "renderBranches",
    "renderGenericNode",
)


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    end = JS.index("\nfunction ", start + 1)
    return JS[start:end]


def _node(script: str) -> Any:  # noqa: ANN401
    source = "\n".join([_DOM, *(_function(n) for n in _FUNCTIONS), script])
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
def test_procedure_tab_shows_the_values_and_the_failed_items() -> None:
    values = [0, 0, 0, 64, 0, 0, 0, 0, 0, 64, 0, 0]
    node = _check(_folded(values), "20.1")
    out = _node(f"""
      const node = {json.dumps(node)};
      const run = renderNode(node, 2, false);
      const generic = renderNode(node, 2, true);
      console.log(JSON.stringify({{
        result: texts(run, 'procedure-result'),
        summary: findAll(run, 'procedure-each')[0].children[0].textContent,
        values: texts(run, 'procedure-each-value'),
        failed: texts(run, 'procedure-each-value').filter(t => t.endsWith('64')),
        items: texts(run, 'procedure-step-desc'),
        exc: texts(run, 'procedure-step-exc').length,
        generic: texts(generic, 'procedure-step-desc'),
        genericNumber: texts(generic, 'procedure-step-number'),
        genericValues: findAll(generic, 'procedure-each').length,
      }}));
    """)
    assert out["result"] == ["→ 2 of 12 failed", "→ got 64", "→ got 64"]
    assert out["summary"] == "Values of waveforms (12 items)"
    assert out["values"][:4] == ["[0]0", "[1]0", "[2]0", "[3]64"] and len(out["values"]) == 12
    assert out["failed"] == ["[3]64", "[9]64"]
    assert out["items"] == [
        f"Verify {LINE}",
        "Verify item [3]: w & INDEX_ERROR_BIT == 0",
        "Verify item [9]: w & INDEX_ERROR_BIT == 0",
    ]
    assert out["exc"] == 2  # each failed item's own detail; none for the line
    # The Generic view: the line alone, a leaf, without this run's items or values
    assert out["generic"] == [f"Verify {LINE}"]
    assert out["genericNumber"] == ["20.1"]
    assert out["genericValues"] == 0


@requires_node
def test_cut_values_keep_their_positions() -> None:
    node = _check(_folded([0] * 4, count=10), "1.1")
    node["each"]["failed_items"] = [9]
    out = _node(f"""
      const box = renderEachValues({json.dumps(node["each"])});
      console.log(JSON.stringify({{
        values: texts(box, 'procedure-each-value'),
        gap: texts(box, 'procedure-each-gap').length,
        failed: texts(box, 'failed'),
        none: renderEachValues({{count: 3, values: []}}) === null,
        missing: renderEachValues(undefined) === null,
      }}));
    """)
    assert out["values"] == ["[0]0", "[1]0", "[8]0", "[9]0"]
    assert out["gap"] == 1 and out["failed"] == ["[9]0"]
    assert out["none"] is True and out["missing"] is True


@requires_folding
def test_all_satisfy_end_to_end(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_w="""
        from stepdoc import step

        INDEX_ERROR_BIT = 0x40

        def test_a(verify):
            waveforms = [0x40 if i in (3, 9) else 0x01 for i in range(12)]
            with step("Verify the Index Error bit is 0"):
                verify.all_satisfy(
                    waveforms,
                    lambda w: verify.equal(w & INDEX_ERROR_BIT, 0),
                    name="Index error clear",
                )
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(failed=1)
    (run,) = sorted((pytester.path / "reports" / "runs").iterdir())
    path = run / "tests" / "test_w.py" / "test_a" / "default" / "procedure.json"
    (check,) = json.loads(path.read_text(encoding="utf-8"))["steps"][0]["substeps"]
    assert check["description"] == f"Verify {LINE}"
    assert check["result"] == "2 of 12 failed"
    assert check["each"]["failed_items"] == [3, 9] and check["each"]["values"][3] == "64"
    assert [s["description"] for s in check["substeps"]] == [
        "Verify item [3]: w & INDEX_ERROR_BIT == 0",
        "Verify item [9]: w & INDEX_ERROR_BIT == 0",
    ]
