"""A test's docstring in the report: "About this test" (from stepdoc).

stepdoc parses the test function's own docstring once and hands it to
``pytest_stepdoc_test_doc`` (description, objective, acceptance criteria). The
reporter keeps it per test, adds it to ``procedure.json`` as ``doc`` and shows
it at the top of the run's Summary sub-tab. Without stepdoc, without a
docstring, or with ``report_stepdoc = false`` nothing new appears.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter._html_builder._css import CSS
from pytest_reporter._html_builder._js import JS
from pytest_reporter._stepdoc import clean_doc, doc_blocks, doc_html_data

if TYPE_CHECKING:
    from pytest import Pytester

requires_stepdoc = pytest.mark.skipif(
    importlib.util.find_spec("stepdoc") is None, reason="stepdoc is not installed"
)
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

_DATA_BLOCK = '<script type="application/json" id="report-data">'

_FIFO = '''
import pytest
from stepdoc import step


@pytest.mark.parametrize("channel", [0, 3])
def test_cmd_fifo_fill(channel):
    """Fill the CMD FIFO until the TX flag sets.

    Objective:
        Confirm the FIFO accepts its full depth before it reports full.

    Acceptance criteria:
        1. The TX flag sets after exactly 500 writes.
        2. No write is lost or reported as an error.
    """
    with step("Fill"):
        pass


def test_link():
    """Bring the link up.

    Pass criteria:
        - The `LOCK` bit sets.
        - No CRC errors,
          on both lanes.
    """


def test_plain():
    with step("Nothing to say"):
        pass
'''

_FIFO_DOC = {
    "description": "Fill the CMD FIFO until the TX flag sets.",
    "objective": "Confirm the FIFO accepts its full depth before it reports full.",
    "acceptance": (
        "1. The TX flag sets after exactly 500 writes.\n"
        "2. No write is lost or reported as an error."
    ),
}


def _run_dir(pytester: Pytester) -> Path:
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def _procedure(pytester: Pytester, module: str, func: str, *rest: str) -> dict[str, Any]:
    path = _run_dir(pytester) / "tests" / f"{module}.py" / func
    for part in rest:
        path = path / part
    return json.loads((path / "procedure.json").read_text())  # type: ignore[no-any-return]


def _data(pytester: Pytester) -> dict[str, Any]:
    html = (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")
    start = html.index(_DATA_BLOCK) + len(_DATA_BLOCK)
    return json.loads(html[start : html.index("</script>", start)])  # type: ignore[no-any-return]


def _runs(data: dict[str, Any]) -> dict[str, Any]:
    return {run["nodeid"]: run for test in data["tests"] for run in test["runs"]}


def _seg(text: str) -> list[dict[str, Any]]:
    return [{"text": text, "style": None}]


# ----------------------------------------------------------------------
# Python: the doc's blocks for the HTML report
# ----------------------------------------------------------------------


def test_clean_doc_keeps_known_sections_with_text() -> None:
    assert clean_doc({"description": "A", "objective": "  ", "other": "x", "acceptance": 3}) == {
        "description": "A"
    }
    assert clean_doc({"objective": ""}) is None
    assert clean_doc(None) is None
    assert clean_doc("text") is None


def test_doc_blocks_paragraphs_and_lists() -> None:
    text = (
        "First line\nwraps here.\n\nSecond paragraph.\n"
        "- one\n  more of one\n* two\n\n3) three\n4) four\n7. seven"
    )
    assert doc_blocks(text) == [
        {"kind": "p", "items": [{"segments": _seg("First line wraps here.")}]},
        {"kind": "p", "items": [{"segments": _seg("Second paragraph.")}]},
        {
            "kind": "ul",
            "items": [{"segments": _seg("one more of one")}, {"segments": _seg("two")}],
        },
        {
            "kind": "ol",
            "items": [
                {"segments": _seg("three"), "number": 3},
                {"segments": _seg("four"), "number": 4},
                {"segments": _seg("seven"), "number": 7},
            ],
        },
    ]


def test_doc_blocks_sentence_is_a_paragraph_and_backticks_are_mono() -> None:
    assert doc_blocks("The `TX` flag sets.") == [
        {
            "kind": "p",
            "items": [
                {
                    "segments": [
                        {"text": "The ", "style": None},
                        {"text": "TX", "style": "mono"},
                        {"text": " flag sets.", "style": None},
                    ]
                }
            ],
        }
    ]


def _shape(text: str) -> list[tuple[str, list[str], list[int]]]:
    return [
        (
            b["kind"],
            ["".join(seg["text"] for seg in i["segments"]) for i in b["items"]],
            [i["number"] for i in b["items"] if "number" in i],
        )
        for b in doc_blocks(text)
    ]


@pytest.mark.parametrize(
    ("text", "shape"),
    [
        (
            "The device passes when:\n\n  - a\n  - b\nNotes: x",
            [
                ("p", ["The device passes when:"], []),
                ("ul", ["a", "b"], []),
                ("p", ["Notes: x"], []),
            ],
        ),
        ("Intro:\n  1. a\n  2. b", [("p", ["Intro:"], []), ("ol", ["a", "b"], [1, 2])]),
        (" 9. nine\n10. ten", [("ol", ["nine", "ten"], [9, 10])]),
        ("It reaches\n512. Then stops.", [("p", ["It reaches 512. Then stops."], [])]),
    ],
)
def test_doc_blocks_indented_lists_read_like_stepdoc(
    text: str, shape: list[tuple[str, list[str], list[int]]]
) -> None:
    assert _shape(text) == shape


def test_doc_html_data_orders_sections_and_titles_them() -> None:
    data = doc_html_data({"acceptance": "- a", "description": "D", "objective": "O"})
    assert data is not None
    assert [(s["key"], s["title"]) for s in data] == [
        ("description", None),
        ("objective", "Objective"),
        ("acceptance", "Acceptance criteria"),
    ]
    assert doc_html_data(None) is None
    assert doc_html_data({}) is None


# ----------------------------------------------------------------------
# End to end, with stepdoc
# ----------------------------------------------------------------------


@requires_stepdoc
def test_doc_reaches_procedure_json_and_html_data(pytester: Pytester) -> None:
    pytester.makepyfile(test_fifo=_FIFO)
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=4)

    for run_id in ("01", "02"):
        proc = _procedure(pytester, "test_fifo", "test_cmd_fifo_fill", run_id)
        assert proc["doc"] == _FIFO_DOC
        assert proc["steps"]
    # A test without steps still gets its doc next to the empty steps
    assert _procedure(pytester, "test_fifo", "test_link", "default")["doc"]["acceptance"] == (
        "- The `LOCK` bit sets.\n- No CRC errors,\n  on both lanes."
    )
    # No docstring: procedure.json and the run data are as before
    assert "doc" not in _procedure(pytester, "test_fifo", "test_plain", "default")

    runs = _runs(_data(pytester))
    fifo = runs["test_fifo.py::test_cmd_fifo_fill[0]"]["doc"]
    assert [s["key"] for s in fifo] == ["description", "objective", "acceptance"]
    assert fifo[2]["blocks"] == [
        {
            "kind": "ol",
            "items": [
                {"segments": _seg("The TX flag sets after exactly 500 writes."), "number": 1},
                {"segments": _seg("No write is lost or reported as an error."), "number": 2},
            ],
        }
    ]
    link = runs["test_fifo.py::test_link"]["doc"]
    assert link[1]["key"] == "acceptance"
    assert link[1]["blocks"][0]["kind"] == "ul"
    assert link[1]["blocks"][0]["items"][1]["segments"] == _seg("No CRC errors, on both lanes.")
    assert runs["test_fifo.py::test_plain"]["doc"] is None


@requires_stepdoc
def test_report_stepdoc_false_shows_no_doc(pytester: Pytester) -> None:
    pytester.makepyfile(test_fifo=_FIFO)
    pytester.makeini("[pytest]\nreport_stepdoc = false\n")
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=4)
    assert "doc" not in _procedure(pytester, "test_fifo", "test_cmd_fifo_fill", "01")
    assert all(run["doc"] is None for run in _runs(_data(pytester)).values())


def test_no_doc_without_stepdoc_hook(pytester: Pytester) -> None:
    """The reporter never parses docstrings itself: only stepdoc's hook gives one."""
    pytester.makepyfile(
        test_plain='''
        def test_a():
            """Something.

            Objective: show it.
            """
        '''
    )
    pytester.makeini("[pytest]\nreport_stepdoc = false\n")
    pytester.runpytest("--report-dir=reports", "-p", "no:stepdoc").assert_outcomes(passed=1)
    assert "doc" not in _procedure(pytester, "test_plain", "test_a", "default")
    assert all(run["doc"] is None for run in _runs(_data(pytester)).values())


@requires_stepdoc
def test_retries_keep_the_doc(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_retry='''
        _n = 0

        def test_flaky():
            """Pass on the second try.

            Acceptance criteria: the second attempt passes.
            """
            global _n
            _n += 1
            assert _n >= 2
        '''
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=1").assert_outcomes(passed=1)
    doc = {"description": "Pass on the second try.", "acceptance": "the second attempt passes."}
    assert _procedure(pytester, "test_retry", "test_flaky", "default")["doc"] == doc
    retry = _procedure(pytester, "test_retry", "test_flaky", "default", "retries", "01")
    assert retry["doc"] == doc
    run = _runs(_data(pytester))["test_retry.py::test_flaky"]
    assert [s["key"] for s in run["doc"]] == ["description", "acceptance"]
    assert run["retry_attempts"][0]["procedure"]["doc"] == doc


@requires_stepdoc
def test_hostile_doc_text_stays_data(pytester: Pytester) -> None:
    pytester.makepyfile(
        test_xss='''
        def test_a():
            """</script><script>alert(1)</script> <img src=x onerror=alert(2)>

            Objective: `<b>bold</b>`
            """
        '''
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    html = (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")
    assert "<script>alert(1)" not in html
    assert "<img src=x" not in html
    run = _runs(_data(pytester))["test_xss.py::test_a"]
    assert run["doc"][0]["blocks"][0]["items"][0]["segments"][0]["text"].startswith(
        "</script><script>alert(1)</script>"
    )
    assert run["doc"][1]["blocks"][0]["items"][0]["segments"] == [
        {"text": "<b>bold</b>", "style": "mono"}
    ]


# ----------------------------------------------------------------------
# The renderer (under Node, with a minimal DOM)
# ----------------------------------------------------------------------

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
function shape(n) {
  if (n.tag === '#text') return n.text;
  const out = {tag: n.tag};
  if (n.className) out.cls = n.className;
  if (n.start !== undefined) out.start = n.start;
  if (n.value !== undefined) out.value = n.value;
  if (n.text !== undefined) out.text = n.text;
  const kids = n.children.map(shape);
  if (kids.length) out.children = kids;
  return out;
}
"""


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    end = JS.index("\n}\n", start) + 2  # a top-level function ends at column 0
    return JS[start:end]


def _render(doc: Any) -> Any:  # noqa: ANN401
    names = ("el", "renderFormattedDesc", "renderDocBlock", "renderTestDoc")
    source = "\n".join(
        [_DOM, *(_function(n) for n in names)]
        + [
            f"const r = renderTestDoc({json.dumps(doc)});"
            "console.log(JSON.stringify(r ? shape(r) : null));"
        ]
    )
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
def test_about_block_renders_sections_and_lists() -> None:
    doc = doc_html_data(
        {
            "description": "Fill the FIFO.\n\nUses `cmd`.",
            "objective": "Show it.",
            "acceptance": "3. three\n4. four\n9. nine",
        }
    )
    out = _render(doc)
    assert out["tag"] == "section"
    assert out["cls"] == "test-doc"
    desc, objective, acceptance = out["children"]
    assert desc["cls"] == "test-doc-section test-doc-description"
    assert [c["tag"] for c in desc["children"]] == ["p", "p"]
    mono = desc["children"][1]["children"][0]["children"][1]
    assert mono == {"tag": "span", "cls": "proc-mono", "text": "cmd"}
    assert objective["children"][0] == {
        "tag": "h3",
        "cls": "test-doc-label",
        "children": ["Objective"],
    }
    label, ol = acceptance["children"]
    assert label["children"] == ["Acceptance criteria"]
    assert ol["tag"] == "ol"
    assert ol["start"] == 3
    assert [li.get("value") for li in ol["children"]] == [None, None, 9]


@requires_node
def test_about_block_bullets_and_absent_without_doc() -> None:
    out = _render(doc_html_data({"acceptance": "- a\n- b"}))
    (section,) = out["children"]
    assert section["children"][1]["tag"] == "ul"
    assert _render(None) is None
    assert _render([]) is None
    assert _render([{"key": "evil", "title": "x", "blocks": [{"kind": "p", "items": []}]}]) is None


def test_about_block_is_built_with_text_nodes_only() -> None:
    """Doc text reaches the DOM through text nodes, never as markup."""
    for name in ("renderTestDoc", "renderDocBlock", "renderFormattedDesc"):
        assert "innerHTML" not in _function(name), name
    assert "renderTestDoc(run.doc)" in JS


def test_about_block_styles_use_tokens() -> None:
    start = CSS.index("/* About this test")
    block = CSS[start : CSS.index("\n.", CSS.index(".test-doc .proc-mono", start) + 1)]
    assert "#" not in block.replace("/* About", "")
    assert "var(--c-text3)" in block
