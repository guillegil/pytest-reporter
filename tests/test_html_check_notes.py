"""Check notes in the HTML report.

A check may carry a note: pytest-verifier's ``note=`` (``report.verify_checks``)
or, in a procedure, stepdoc's ``Check.note`` (``note=`` or a source comment).
The Procedure tab shows it after the check's text in parentheses, as stepdoc
does; verification cards show it after the statement. A name pytest-verifier
took from the source (``auto_name``) is shown as code.

The renderers run under Node with a minimal DOM (text only: what textContent
would give), so the tests see the text a reader sees.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter._html_builder._js import JS

if TYPE_CHECKING:
    from pytest import Pytester

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

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
function find(node, cls) {
  if ((' ' + node.className + ' ').includes(' ' + cls + ' ')) return node;
  for (const c of node.children) { const f = find(c, cls); if (f) return f; }
  return null;
}
"""


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    end = JS.index("\nfunction ", start + 1)
    return JS[start:end]


def _run(script: str) -> Any:  # noqa: ANN401
    source = "\n".join(
        [_DOM]
        + [
            _function(n)
            for n in (
                "el",
                "_appendCheckInline",
                "renderFormattedDesc",
                "renderNode",
                "renderEachValues",
                "renderBranches",
                "checkNote",
            )
        ]
        + [_function("checkLabel"), script]
    )
    # The script goes through stdin and both ways as UTF-8: argv and the default
    # text encoding follow the locale (cp1252 on Windows runners).
    out = subprocess.run(
        ["node", "-"],
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    return json.loads(out.stdout)


@requires_node
def test_procedure_check_note_follows_the_text() -> None:
    nodes = [
        {
            "kind": "check",
            "number": "1.1",
            "description": "Verify dev.block.esmi3_32dat.txfe == 1",
            "outcome": "passed",
            "result": "got 1",
            "note": "CMD FIFO empty",
        },
        {"kind": "check", "number": "1.2", "description": "Verify x == 1", "outcome": "passed"},
        {
            "kind": "step",
            "number": "2",
            "description": "Turn off",
            "outcome": "passed",
            "note": "Power is cut first.",
        },
        {
            "kind": "check",
            "number": "1.3",
            "description": "Verify y == 2",
            "outcome": "passed",
            "note": "<b>not markup</b>",
        },
    ]
    got = _run(
        "const nodes = " + json.dumps(nodes) + ";\n"
        "console.log(JSON.stringify(nodes.map(n => {\n"
        "  const row = renderNode(n, 2);\n"
        "  const note = find(row, 'procedure-note');\n"
        "  return [find(row, 'procedure-step-desc').textContent, note && note.textContent];\n"
        "})));"
    )
    assert got == [
        ["Verify dev.block.esmi3_32dat.txfe == 1 (CMD FIFO empty)", None],
        ["Verify x == 1", None],
        ["Turn off", "Power is cut first."],  # steps keep the note line under them
        ["Verify y == 2 (<b>not markup</b>)", None],  # text, never parsed as HTML
    ]


@requires_node
def test_card_note_and_label() -> None:
    checks = [
        {"name": "dat.txfe", "auto_name": True, "note": " CMD FIFO empty "},
        {"name": "Vout", "section": ["3V3"]},
        {"note": 5},
    ]
    got = _run(
        "const checks = " + json.dumps(checks) + ";\n"
        "console.log(JSON.stringify(checks.map((c, i) => [checkLabel(c, i), checkNote(c)])));"
    )
    assert got == [["dat.txfe", "CMD FIFO empty"], ["3V3 › Vout", ""], ["Check #3", ""]]


def test_cards_render_the_note() -> None:
    """The card header and the failure strip show a check's note; the card body
    lists it among the fields; an auto-named check's label is code."""
    assert "checkNote(check)" in JS
    assert "checkNote(c)" in JS
    assert "['note', 'Note']" in _function("renderCheckDetail")
    assert "check.auto_name === true ? ' auto-name'" in JS


def test_note_reaches_the_report_data(pytester: Pytester) -> None:
    """A note on report.verify_checks is in the HTML data, escaped."""
    pytester.makeconftest("""
        import pytest

        @pytest.hookimpl(wrapper=True)
        def pytest_runtest_makereport(item, call):
            report = yield
            if report.when == "call":
                report.verify_checks = [{
                    "check_type": "equal", "name": "dat.txfe", "auto_name": True,
                    "description": "Verify 'dat.txfe' == 1", "note": "</script>FIFO empty",
                    "actual": 1, "expected": 1, "passed": True, "detail": "1 == 1",
                    "phase": "call",
                }]
            return report
    """)
    pytester.makepyfile(test_x="def test_a():\n    pass\n")
    pytester.runpytest("--report-dir=reports", "-p", "no:pytest_verifier").assert_outcomes(passed=1)
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    html = (runs[0] / "report.html").read_text(encoding="utf-8")
    marker = '<script type="application/json" id="report-data">'
    start = html.index(marker) + len(marker)
    block = html[start : html.index("</script>", start)]
    check = json.loads(block)["tests"][0]["runs"][0]["check_results"][0]
    assert check["note"] == "</script>FIFO empty"
    assert check["auto_name"] is True
