"""Register checks: values in hex or binary, the bits that differ, the fields.

pytest-verifier (0.11+) puts on a check that has a format (``radix=``,
``width=``, ``verify.bits``, a value with ``__verify_format__``) the text of
each value (``rendered``), the bits that differ (``bit_diff``) and the fields.
The cards show that text, a strip of one cell per bit and a table of the
fields; the Procedure tab shows stepdoc's ``actual_text`` and ``difference``.
An integer too large for a JavaScript number is shown exactly on every check.

The renderers run under Node with a minimal DOM (text only), as in
``test_operand_names.py``. The records below are copied from a run of
pytest-verifier 0.11; tests that run the plugins skip without that version.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from types import SimpleNamespace as NS
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter._html_builder._css import CSS
from pytest_reporter._html_builder._js import JS
from pytest_reporter._stepdoc import _check, with_values
from pytest_reporter._strategies import js_safe

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import Pytester

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
requires_verifier = pytest.mark.skipif(
    importlib.util.find_spec("pytest_verifier") is None, reason="pytest-verifier is not installed"
)


def _verifier_has_bits() -> bool:
    if importlib.util.find_spec("pytest_verifier") is None:
        return False
    from pytest_verifier import Verify

    return hasattr(Verify, "bits")


def _stepdoc_has_actual_text() -> bool:
    if importlib.util.find_spec("stepdoc") is None:
        return False
    import dataclasses

    import stepdoc

    check = getattr(stepdoc, "Check", None)
    return dataclasses.is_dataclass(check) and any(
        f.name == "actual_text" for f in dataclasses.fields(check)
    )


requires_bits = pytest.mark.skipif(
    not _verifier_has_bits(), reason="pytest-verifier with verify.bits is not installed"
)
requires_register_stepdoc = pytest.mark.skipif(
    not (_verifier_has_bits() and _stepdoc_has_actual_text()),
    reason="stepdoc with Check.actual_text and pytest-verifier with verify.bits are not installed",
)

FIELDS_DETAIL = "EN [0] is 0b0, expected 0b1; MODE [3:1] is 0b000, expected 0b001"
BIT_FIELDS = [
    {"name": "EN", "msb": 0, "lsb": 0, "actual": "0b0", "expected": "0b1"},
    {"name": "MODE", "msb": 3, "lsb": 1, "actual": "0b000", "expected": "0b001"},
]

EQUAL: dict[str, Any] = {
    "check_type": "equal",
    "name": "R",
    "description": "Verify 'R' == 0x00F3",
    "actual": 240,
    "expected": 243,
    "units": None,
    "radix": "hex",
    "width": 16,
    "rendered": {"actual": "0x00F0", "expected": "0x00F3"},
    "bit_diff": {"bits": [[1, 0]], "text": "bits [1:0] differ"},
    "passed": False,
    "detail": "expected 0x00F3, got 0x00F0; bits [1:0] differ",
    "phase": "call",
    "location": "test_rec.py:9",
}

BITS: dict[str, Any] = {
    "check_type": "bits",
    "name": "CTRL",
    "description": "Verify 'CTRL' & 0x00FF == 0x00F3",
    "actual": 4848,
    "expected": 44019,
    "mask": 255,
    "radix": "hex",
    "width": 16,
    "fields": {"EN": [0, 0], "MODE": [3, 1], "DIV": [15, 8]},
    "rendered": {"actual": "0x12F0", "expected": "0xABF3", "mask": "0x00FF"},
    "bit_diff": {"bits": [[1, 0]], "text": "bits [1:0] differ", "fields": BIT_FIELDS},
    "passed": False,
    "detail": f"expected 0x00F3, got 0x12F0 (mask 0x00FF); bits [1:0] differ: {FIELDS_DETAIL}",
    "phase": "call",
    "location": "test_rec.py:11",
}

BITS_PASSED: dict[str, Any] = {
    **{k: v for k, v in BITS.items() if k != "bit_diff"},
    "actual": 4851,
    "rendered": {"actual": "0x12F3", "expected": "0xABF3", "mask": "0x00FF"},
    "passed": True,
    "detail": "0x12F3 & 0x00FF == 0x00F3",
}

WIDE: dict[str, Any] = {
    "check_type": "equal",
    "name": "W",
    "description": "Verify 'W' == 0xFFFF_FFFF_FFFF_FFFE",
    "actual": 18446744073709551615,
    "expected": 18446744073709551614,
    "units": None,
    "radix": "hex",
    "width": 64,
    "rendered": {"actual": "0xFFFF_FFFF_FFFF_FFFF", "expected": "0xFFFF_FFFF_FFFF_FFFE"},
    "bit_diff": {"bits": [[0, 0]], "text": "bit 0 differs"},
    "passed": False,
    "detail": "expected 0xFFFF_FFFF_FFFF_FFFE, got 0xFFFF_FFFF_FFFF_FFFF; bit 0 differs",
    "phase": "call",
}

ORDERING: dict[str, Any] = {
    "check_type": "less",
    "name": "ADDR",
    "description": "Verify 'ADDR' < 0x100",
    "actual": 496,
    "threshold": 256,
    "units": "LSB",
    "radix": "hex",
    "rendered": {"actual": "0x1F0", "threshold": "0x100"},
    "passed": False,
    "detail": "expected < 0x100LSB, got 0x1F0LSB",
    "phase": "call",
}


# ---------------------------------------------------------------------------
# Integers a JavaScript number cannot hold
# ---------------------------------------------------------------------------


def test_big_integers_in_a_check_become_text_for_the_page() -> None:
    safe = js_safe([WIDE, {"check_type": "all_satisfy", "child_checks": [WIDE, EQUAL]}])
    assert safe[0]["actual"] == {"$repr": "18446744073709551615"}
    assert safe[0]["expected"] == {"$repr": "18446744073709551614"}
    assert safe[0]["width"] == 64
    assert safe[0]["rendered"] == WIDE["rendered"]
    assert safe[1]["child_checks"][0]["actual"] == {"$repr": "18446744073709551615"}
    assert safe[1]["child_checks"][1] == EQUAL  # a number JavaScript holds stays a number
    assert WIDE["actual"] == 18446744073709551615  # the record itself is not touched
    assert js_safe({"a": 2**53 - 1, "b": 2**53, "c": -(2**53), "d": True, "e": 1.5}) == {
        "a": 2**53 - 1,
        "b": {"$repr": "9007199254740992"},
        "c": {"$repr": "-9007199254740992"},
        "d": True,
        "e": 1.5,
    }


def _run_dir(pytester: Pytester) -> Path:
    return sorted((pytester.path / "reports" / "runs").iterdir())[-1]


def _data(run_dir: Path) -> dict[str, Any]:
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="report-data">(.*?)</script>', html, re.DOTALL
    )
    assert match
    data: dict[str, Any] = json.loads(match.group(1))
    return data


@requires_verifier
def test_plain_64_bit_values_are_exact_in_the_report(pytester: Pytester) -> None:
    """No format at all: the values still reach the page digit for digit."""
    pytester.makepyfile(
        """
        def test_reg64(verify):
            verify.equal(0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFE, name="reg64")
        """
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=1").assert_outcomes(failed=1)
    run_dir = _run_dir(pytester)
    (run,) = (r for t in _data(run_dir)["tests"] for r in t["runs"])
    (check,) = run["check_results"]
    assert check["actual"] == {"$repr": "18446744073709551615"}
    assert check["expected"] == {"$repr": "18446744073709551614"}
    (retry,) = run["retry_attempts"]
    assert retry["check_results"][0]["actual"] == {"$repr": "18446744073709551615"}
    # checks.json keeps the numbers
    (saved,) = json.loads(next(run_dir.rglob("checks.json")).read_text(encoding="utf-8"))["checks"]
    assert saved["actual"] == 18446744073709551615


# ---------------------------------------------------------------------------
# Procedure tab: stepdoc's actual_text and difference
# ---------------------------------------------------------------------------


def _stepdoc_check(**fields: object) -> NS:
    base: dict[str, Any] = {
        "text": "dev.CTRL & 0x00FF == 0x00F3",
        "passed": False,
        "actual": 4848,
        "symbolic_text": None,
        "detail": None,
        "children": [],
        "reads": [],
        "source": None,
    }
    base.update(fields)
    return NS(**base)


DIFFERENCE = f"bits [1:0] differ: {FIELDS_DETAIL}"


def test_result_uses_the_rendered_value_and_the_difference() -> None:
    node = _check(
        _stepdoc_check(actual_text="0x12F0", difference=DIFFERENCE, detail=BITS["detail"]),
        "1.2",
    )
    assert node["description"] == "Verify dev.CTRL & 0x00FF == 0x00F3"
    assert node["result"] == f"got 0x12F0, {DIFFERENCE}"
    assert node["outcome"] == "failed"
    # The detail would say it all again: expected, got, mask and the difference
    assert "detail" not in node


def test_a_passed_check_shows_the_value_without_a_difference() -> None:
    node = _check(_stepdoc_check(passed=True, actual_text="0x12F3", difference=DIFFERENCE), "1.1")
    assert node["result"] == "got 0x12F3"
    unjudged = _check(_stepdoc_check(passed=None, actual_text="0x12F3", difference="x"), "1.1")
    assert unjudged["result"] == "got 0x12F3"


def test_a_detail_that_says_more_than_the_difference_is_kept() -> None:
    detail = "expected < 0x100, got 0x1F0"
    node = _check(_stepdoc_check(actual=496, actual_text="0x1F0", detail=detail), "2.1")
    assert node["result"] == "got 0x1F0"
    assert node["detail"] == detail
    other = _check(
        _stepdoc_check(actual_text="0x12F0", difference="bit 0 differs", detail="bit 0 differs; x"),
        "2.2",
    )
    assert other["detail"] == "bit 0 differs; x"


def test_a_difference_without_a_value_is_the_result() -> None:
    node = _check(_stepdoc_check(actual=None, difference="bits [1:0] differ"), "1")
    assert node["result"] == "bits [1:0] differ"


def test_operand_names_keep_the_rendered_value() -> None:
    record = {
        "description": "Verify 'tb.reg3.F' == wdata (0x00F3)",
        "name": "tb.reg3.F",
        "auto_name": True,
        "actual_name": "tb.reg3.F",
        "actual_name_symbolic": "tb.reg<channel>.F",
        "expected_name": "wdata",
    }
    node = _check(
        _stepdoc_check(
            text="'tb.reg3.F' == wdata (0x00F3)",
            actual=240,
            actual_text="0x00F0",
            difference="bits [1:0] differ",
            source=record,
        ),
        "1.1",
    )
    assert node["description"] == "Verify tb.reg<channel>.F == wdata (0x00F3)"
    assert node["result"] == "got tb.reg3.F = 0x00F0, bits [1:0] differ"


def test_an_older_stepdoc_is_unchanged() -> None:
    """No actual_text, no difference: repr of the value, the detail kept."""
    node = _check(_stepdoc_check(detail="expected 243, got 4848"), "1")
    assert node["result"] == "got 4848"
    assert node["detail"] == "expected 243, got 4848"
    blank = _check(_stepdoc_check(actual_text="  ", difference=7), "1")
    assert blank["result"] == "got 4848"


def test_generic_view_has_no_run_value() -> None:
    node = _check(
        _stepdoc_check(
            symbolic_text="dev.CTRL & <MASK> == <wdata>",
            actual_text="0x12F0",
            difference=DIFFERENCE,
        ),
        "1.2",
    )
    assert node["generic"] == "Verify dev.CTRL & <MASK> == <wdata>"
    assert "0x12F0" not in node["generic"] and "differ" not in node["generic"]
    assert node["description"] == "Verify dev.CTRL & 0x00FF == <wdata> (0x00F3)"


def test_a_literal_in_another_radix_is_a_value_not_a_name() -> None:
    """bits shows the expected value under its mask: 0x00F0 where 0x12F0 was written."""
    assert with_values("dev.CTRL & <MASK> == 0x12F0", "dev.CTRL & 0x00FF == 0x00F0") == (
        "dev.CTRL & 0x00FF == 0x00F0"
    )
    assert with_values("'N' == 0b1000", "'N' == 0b0000_1000") == "'N' == 0b0000_1000"
    # Names are still followed by this run's value
    assert with_values("'R' == <wdata>", "'R' == 0x00F3") == "'R' == <wdata> (0x00F3)"
    assert with_values("'R' == wdata", "'R' == 243") == "'R' == wdata (243)"


def test_folded_items_show_their_rendered_values() -> None:
    child = _stepdoc_check(
        text="'r': x == 0x01", actual=2, actual_text="0x02", difference="bits [1:0] differ", index=1
    )
    parent = _stepdoc_check(
        text="'all': for each x in bank, x == 0x01",
        actual=None,
        children=[child],
        each=NS(
            count=3,
            failed=1,
            item="x",
            items="bank",
            values=[1, 2, 1],
            texts=["0x01", "0x02", None],
        ),
    )
    node = _check(parent, "1.1")
    assert node["each"]["values"] == ["0x01", "0x02", "1"]
    assert node["result"] == "1 of 3 failed"
    assert node["substeps"][0]["result"] == "got 0x02, bits [1:0] differ"
    # texts of another length are not this list's: ignored
    parent.each.texts = ["0x01"]
    assert _check(parent, "1.1")["each"]["values"] == ["1", "2", "1"]
    del parent.each.texts
    assert _check(parent, "1.1")["each"]["values"] == ["1", "2", "1"]


# ---------------------------------------------------------------------------
# Cards (Node)
# ---------------------------------------------------------------------------

_DOM = """
const window = {};
function Node(tag) { this.tag = tag; this.children = []; this.className = ''; this.attrs = {}; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
Node.prototype.addEventListener = function () {};
Object.defineProperty(Node.prototype, 'textContent', {
  get() { return this.text !== undefined ? this.text
                 : this.children.map(c => c.textContent).join(''); },
  set(v) { this.text = String(v); this.children = []; },
});
const document = {
  createElement: tag => new Node(tag),
  createElementNS: (ns, tag) => new Node(tag),
  createTextNode: text => { const n = new Node('#text'); n.text = String(text); return n; },
  querySelector: () => null,
};
function findAll(node, cls, out) {
  out = out || [];
  if ((' ' + node.className + ' ').includes(' ' + cls + ' ')) out.push(node);
  node.children.forEach(c => findAll(c, cls, out));
  return out;
}
function byTag(node, tag, out) {
  out = out || [];
  if (node.tag === tag) out.push(node);
  node.children.forEach(c => byTag(c, tag, out));
  return out;
}
const texts = (node, cls) => findAll(node, cls).map(n => n.textContent);
// The grid's rows: [label, value]; the bit view is a child without a label
function rows(detail) {
  const out = {};
  detail.children.forEach((c, i) => {
    if (c.className === 'label') out[c.textContent] = detail.children[i + 1].textContent;
  });
  return out;
}
"""

_FUNCTIONS = (
    "el",
    "svgEl",
    "chevronSvg",
    "isBad",
    "failedPhase",
    "failedChecks",
    "failureReason",
    "renderFailureStrip",
    "renderCheckResults",
    "checkNote",
    "checkOperand",
    "operandNameEl",
    "checkLabel",
    "renderCheckDetail",
    "checkValue",
    "renderedText",
    "checkValueEl",
    "bitsOf",
    "operandBits",
    "bitLength",
    "fieldSpans",
    "bitStripModel",
    "fieldText",
    "fieldRows",
    "renderBitStrip",
    "renderFieldsTable",
    "renderBitView",
    "renderCheckBody",
    "renderGuardCheck",
    "renderAllSatisfyBody",
    "renderConditionalBody",
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


def _js(record: object) -> str:
    """A record as the page gets it: big integers as ``{"$repr": text}``."""
    return json.dumps(js_safe(record))


@requires_node
def test_value_rows_show_the_rendered_text_then_the_number() -> None:
    out = _node(
        f"""
        const all = [{_js(EQUAL)}, {_js(BITS)}, {_js(ORDERING)}, {_js(WIDE)}]
          .map(c => rows(renderCheckDetail(c)));
        console.log(JSON.stringify(all));
        """
    )
    equal, bits, ordering, wide = out
    assert equal["Actual"] == "0x00F0(240)"
    assert equal["Expected"] == "0x00F3(243)"
    assert equal["Result"] == EQUAL["detail"]
    assert bits["Actual"] == "0x12F0(4848)"
    assert bits["Expected"] == "0xABF3(44019)"  # the whole value; the mask has its own row
    assert bits["Mask"] == "0x00FF(255)"
    assert ordering["Actual"] == "0x1F0(496)"
    assert ordering["Threshold"] == "0x100(256)"
    assert ordering["Units"] == "LSB"
    # 64 bits: the text is exact, and no rounded number beside it
    assert wide["Actual"] == "0xFFFF_FFFF_FFFF_FFFF"
    assert wide["Expected"] == "0xFFFF_FFFF_FFFF_FFFE"


@requires_node
def test_value_rows_without_a_format_are_as_before() -> None:
    plain = {"check_type": "equal", "actual": 240, "expected": 243, "passed": False}
    dec = {**EQUAL, "radix": "dec", "rendered": {"actual": "240", "expected": "243"}}
    big = {"check_type": "equal", "actual": 2**64 - 1, "expected": [1, 2**64], "passed": False}
    junk = {**plain, "rendered": "0x00F0", "radix": "hex"}
    broken = {**plain, "format_error": "Bad.__verify_format__: ValueError: no bus"}
    out = _node(
        f"""
        const all = [{_js(plain)}, {_js(dec)}, {_js(big)}, {_js(junk)}, {_js(broken)}];
        console.log(JSON.stringify({{
          rows: all.map(c => rows(renderCheckDetail(c))),
          decimals: all.map(c => findAll(renderCheckDetail(c), 'value-dec').length),
          views: all.map(c => findAll(renderCheckDetail(c), 'bit-view').length),
          value: [null, 3, 'a', {{a: 1}}, true].map(checkValue),
        }}));
        """
    )
    plain_rows, dec_rows, big_rows, junk_rows, broken_rows = out["rows"]
    assert (plain_rows["Actual"], plain_rows["Expected"]) == ("240", "243")
    assert (dec_rows["Actual"], dec_rows["Expected"]) == ("240", "243")
    assert big_rows["Actual"] == "18446744073709551615"
    assert big_rows["Expected"] == '[1,"18446744073709551616"]'
    assert junk_rows["Actual"] == "240"
    assert broken_rows["Format error"] == "Bad.__verify_format__: ValueError: no bus"
    assert out["decimals"] == [0, 0, 0, 0, 0]
    # dec has a bit_diff in this record, so it has a strip; the others have none
    assert out["views"] == [0, 1, 0, 0, 0]
    assert out["value"] == ["", "3", "a", '{"a":1}', "true"]


@requires_node
def test_bits_are_read_from_the_text_digit_by_digit() -> None:
    out = _node(
        """
        const s = v => v === null ? null : v.toString();
        console.log(JSON.stringify({
          parsed: ['0x00F3', '0xFFFF_FFFF_FFFF_FFFE', '0b0000_1111', '0o363', '243', '-0x01',
                   '0x', 'F3', '0x12G0', '', null, 12].map(t => s(bitsOf(t))),
          operand: [
            operandBits({rendered: {actual: '0xDEAD_BEEF_0000_00F0'}, actual: 1}, 'actual'),
            operandBits({actual: 240}, 'actual'),
            operandBits({actual: {$repr: '18446744073709551615'}}, 'actual'),
            operandBits({actual: -1}, 'actual'),
            operandBits({actual: 1.5}, 'actual'),
            operandBits({actual: '0x10'}, 'actual'),
            operandBits({actual: true}, 'actual'),
            operandBits({}, 'actual'),
          ].map(s),
          length: [0n, 1n, 255n, 256n, (1n << 64n) - 1n].map(bitLength),
          field: [fieldText(0n, 1), fieldText(5n, 3), fieldText(9n, 4), fieldText(18n, 8),
                  fieldText(0xABCDn, 16), fieldText(0xDEADBEEFn, 32), fieldText(1n, 5),
                  fieldText(0x1FFn, 9)],
        }));
        """
    )
    assert out["parsed"] == [
        "243",
        "18446744073709551614",
        "15",
        "243",
        "243",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    ]
    assert out["operand"] == [
        str(0xDEAD_BEEF_0000_00F0),
        "240",
        "18446744073709551615",
        None,
        None,
        None,
        None,
        None,
    ]
    assert out["length"] == [0, 1, 8, 9, 64]
    # As pytest-verifier writes a field: binary up to four bits, hex above
    assert out["field"] == [
        "0b0",
        "0b101",
        "0b1001",
        "0x12",
        "0xABCD",
        "0xDEAD_BEEF",
        "0x01",
        "0x1FF",
    ]


@requires_node
def test_bit_strip_model() -> None:
    no_width = {**EQUAL, "width": None, "rendered": {"actual": "0x1F0", "expected": "0x1F3"}}
    wider = {**EQUAL, "width": 4}  # values wider than the width given: every bit shown
    negative = {**EQUAL, "actual": -1, "rendered": {"expected": "0x00F3"}}
    floating = {**BITS, "actual": 1.5, "rendered": {"expected": "0xABF3", "mask": "0x00FF"}}
    too_wide = {**EQUAL, "width": 128}
    passed_equal = {k: v for k, v in EQUAL.items() if k != "bit_diff"} | {"passed": True}
    out = _node(
        f"""
        const m = c => {{ const x = bitStripModel(c); return x && {{
          width: x.width, masked: x.masked, mask: x.mask, differs: x.differs, text: x.text,
          actual: x.cells.map(c => c.actual).join(''),
          expected: x.cells.map(c => c.expected).join(''),
          compared: x.cells.map(c => c.compared ? '1' : '0').join(''),
          diff: x.cells.filter(c => c.differs).map(c => c.bit),
          first: x.cells[0].bit, last: x.cells[x.cells.length - 1].bit}}; }};
        console.log(JSON.stringify([{_js(EQUAL)}, {_js(BITS)}, {_js(BITS_PASSED)}, {_js(WIDE)},
          {_js(no_width)}, {_js(wider)}, {_js(negative)}, {_js(floating)}, {_js(too_wide)},
          {_js(passed_equal)}, {_js(ORDERING)}, null].map(m)));
        """
    )
    equal, bits, passed, wide, no_width_m, wider_m, *none = out
    assert equal == {
        "width": 16,
        "masked": False,
        "mask": "",
        "differs": True,
        "text": "bits [1:0] differ",
        "actual": "0000000011110000",
        "expected": "0000000011110011",
        "compared": "1" * 16,
        "diff": [1, 0],
        "first": 15,
        "last": 0,
    }
    assert bits["actual"] == "0001001011110000"
    assert bits["expected"] == "1010101111110011"
    assert bits["compared"] == "0000000011111111"
    assert bits["diff"] == [1, 0]  # bits 15, 13..11 and 8 differ too, outside the mask
    assert (bits["masked"], bits["mask"]) == (True, "0x00FF")
    assert (passed["differs"], passed["diff"], passed["text"]) == (False, [], "")
    assert wide["width"] == 64
    assert wide["actual"] == "1" * 64
    assert wide["expected"] == "1" * 63 + "0"
    assert wide["diff"] == [0]
    assert (no_width_m["width"], no_width_m["first"]) == (12, 11)  # whole nibbles
    assert wider_m["width"] == 8
    assert none == [None, None, None, None, None, None]


@requires_node
def test_bit_strip_is_a_table_with_the_difference_in_words() -> None:
    out = _node(
        f"""
        const strip = c => {{
          const s = renderBitStrip(c);
          const tables = byTag(s, 'table');
          return {{
            tables: tables.map(t => ({{
              label: t.attrs['aria-label'],
              rows: byTag(t, 'tr').map(r => [r.className, r.children[0].textContent,
                r.children.slice(1).map(c => c.textContent)
                  .join(r.className === 'bit-index' ? ' ' : '')]),
              headers: byTag(t, 'th').filter(h => h.attrs.scope === 'col').length,
            }})),
            differs: findAll(s, 'differs').filter(n => n.tag === 'td').length,
            masked: findAll(s, 'masked').filter(n => n.tag === 'td').length,
            nibbles: findAll(tables[0], 'nib').filter(n => n.tag === 'th').map(n => n.textContent),
            scroll: findAll(s, 'bit-strip-scroll')
              .map(n => [n.attrs.role, n.attrs.tabindex, n.attrs['aria-label']]),
            labels: findAll(s, 'bit-strip-labels')
              .map(n => [n.attrs['aria-hidden'], n.textContent]),
            key: texts(s, 'bit-key'),
          }};
        }};
        console.log(JSON.stringify([{_js(BITS)}, {_js(BITS_PASSED)}, {_js(WIDE)}].map(strip)));
        """
    )
    bits, passed, wide = out
    (table,) = bits["tables"]
    assert table["label"] == (
        "Bits 15 to 0, expected above actual. Bits [1:0] differ. "
        "Bits outside the mask 0x00FF are not compared."
    )
    assert table["rows"] == [
        ["bit-index", "Bit", "15 14 13 12 11 10 9 8 7 6 5 4 3 2 1 0"],
        ["bit-expected", "Expected", "1010101111110011"],
        ["bit-actual", "Actual", "0001001011110000"],
    ]
    assert table["headers"] == 16
    assert bits["differs"] == 4  # bits 1 and 0, in both value rows
    assert bits["masked"] == 16  # bits 15..8, in both value rows
    assert bits["nibbles"] == ["11", "7", "3"]
    assert bits["scroll"] == [["group", "0", "Bits 15 to 0"]]
    assert bits["labels"] == [["true", "BitExpectedActual"]]
    assert bits["key"] == ["1differs from expected", "1outside the mask, not compared"]
    assert passed["tables"][0]["label"] == (
        "Bits 15 to 0, expected above actual. No compared bit differs. "
        "Bits outside the mask 0x00FF are not compared."
    )
    assert passed["differs"] == 0
    assert passed["key"] == ["1outside the mask, not compared"]
    # 64 bits: a table per 32, the low word under the high one
    assert [t["label"] for t in wide["tables"]] == [
        "Bits 63 to 32, expected above actual. Bit 0 differs.",
        "Bits 31 to 0, continued.",
    ]
    assert wide["tables"][1]["rows"][2] == ["bit-actual", "Actual", "1" * 32]
    assert wide["tables"][1]["rows"][1] == ["bit-expected", "Expected", "1" * 31 + "0"]
    assert wide["labels"] == [["true", "BitExpectedActualBitExpectedActual"]]
    assert wide["differs"] == 2


@requires_node
def test_fields_table() -> None:
    no_values = {**BITS, "actual": 1.5, "rendered": {"expected": "0xABF3", "mask": "0x00FF"}}
    junk = {**EQUAL, "fields": {"A": [3], "B": "x", "C": [1.5, 0], "D": [2, -1], "E": [0, 7]}}
    out = _node(
        f"""
        const table = c => {{ const t = renderFieldsTable(c);
          return t && byTag(t, 'tr')
            .map(r => [r.className, ...r.children.map(c => c.textContent)]); }};
        console.log(JSON.stringify({{
          rows: fieldRows({_js(BITS)}), table: table({_js(BITS)}),
          passed: fieldRows({_js(BITS_PASSED)}).map(r => r.differs),
          none: [table({_js(EQUAL)}), table({_js(ORDERING)})],
          noValues: fieldRows({_js(no_values)}),
          junk: fieldRows({_js(junk)}),
          array: fieldRows({{fields: [[1, 0]]}}),
        }}));
        """
    )
    assert out["rows"] == [
        {"name": "EN", "bits": "[0]", "actual": "0b0", "expected": "0b1", "differs": True},
        {"name": "MODE", "bits": "[3:1]", "actual": "0b000", "expected": "0b001", "differs": True},
        # DIV differs in the values, but lies outside the mask: not compared
        {"name": "DIV", "bits": "[15:8]", "actual": "0x12", "expected": "0xAB", "differs": False},
    ]
    # The differing fields read as pytest-verifier's bit_diff has them
    for row, field in zip(out["rows"], BIT_FIELDS, strict=False):
        assert (row["actual"], row["expected"]) == (field["actual"], field["expected"])
    assert out["table"] == [
        ["", "Field", "Bits", "Actual", "Expected"],
        ["differs", "EN", "[0]", "0b0differs", "0b1"],
        ["differs", "MODE", "[3:1]", "0b000differs", "0b001"],
        ["", "DIV", "[15:8]", "0x12", "0xAB"],
    ]
    assert out["passed"] == [False, False, False]
    assert out["none"] == [None, None]
    # An operand that is not an integer: what pytest-verifier said, where it said it
    assert [(r["name"], r["actual"], r["expected"], r["differs"]) for r in out["noValues"]] == [
        ("EN", "0b0", "0b1", True),
        ("MODE", "0b000", "0b001", True),
        ("DIV", "", "0xAB", False),
    ]
    assert [(r["name"], r["bits"]) for r in out["junk"]] == [("E", "[7:0]")]
    assert out["array"] == []


@requires_node
def test_register_cards_end_to_end() -> None:
    """The cards of a run: strip and fields where the record has them, nowhere else."""
    plain = {"check_type": "equal", "name": "n", "actual": 1, "expected": 2, "passed": False}
    composite = {
        "check_type": "all_satisfy",
        "name": "all",
        "passed": False,
        "child_checks": [
            {
                **EQUAL,
                "check_type": "bits",
                "passed": True,
                "actual": 243,
                "bit_diff": None,
                "rendered": {"actual": "0x00F3", "expected": "0x00F3"},
            },
            {**EQUAL, "check_type": "bits"},
        ],
    }
    checks = [EQUAL, BITS, BITS_PASSED, WIDE, ORDERING, plain, composite]
    out = _node(
        f"""
        const root = renderCheckResults({_js(checks)});
        const cards = findAll(root, 'check-card');
        console.log(JSON.stringify(cards.map(c => ({{
          cls: c.className, badge: texts(c, 'check-type-badge')[0], desc: texts(c, 'check-desc')[0],
          strips: findAll(c, 'bit-strip').length, tables: findAll(c, 'bit-fields').length,
          views: findAll(c, 'bit-view').length,
        }}))));
        """
    )
    assert [(c["badge"], c["strips"], c["tables"]) for c in out] == [
        ("equal", 1, 0),
        ("bits", 1, 1),
        ("bits", 1, 1),  # a passed bits check still shows its bits and fields
        ("equal", 1, 0),
        ("less", 0, 0),
        ("equal", 0, 0),
        ("all_satisfy", 1, 0),  # only the failed child is opened
    ]
    assert out[0]["cls"] == "check-card failed expanded"
    assert out[1]["desc"] == "Verify 'CTRL' & 0x00FF == 0x00F3"
    assert out[2]["cls"] == "check-card passed"


@requires_node
def test_failure_strip_and_reason_carry_the_bit_clause() -> None:
    run = {
        "outcome": "failed",
        "phases": {"call": {"outcome": "failed", "longrepr": ""}},
        "check_results": [BITS],
    }
    out = _node(
        f"""
        const run = {_js(run)};
        const strip = renderFailureStrip(run, () => {{}});
        console.log(JSON.stringify({{reason: failureReason(run),
          detail: texts(strip, 'failure-strip-check-detail'),
          name: texts(strip, 'failure-strip-check-name')}}));
        """
    )
    assert out["reason"] == f"CTRL — {BITS['detail']}"
    assert out["detail"] == [BITS["detail"]]
    assert out["name"] == ["Verify 'CTRL' & 0x00FF == 0x00F3"]


def test_cards_never_format_a_number_themselves() -> None:
    """Values come as text from pytest-verifier; bits are read with BigInt."""
    for name in ("checkValueEl", "bitStripModel", "fieldRows", "operandBits"):
        body = _function(name)
        assert ".toString(16)" not in body and "toFixed" not in body, name
        assert "parseInt" not in body and "Number(" not in body, name
    assert "BigInt(" in _function("bitsOf")


def test_strip_styles_cover_phone_print_and_forced_colors() -> None:
    assert ".bit-strip-scroll { overflow-x: auto;" in CSS
    assert ".bit-view {\n  grid-column: 1 / -1;" in CSS
    print_rules = CSS[CSS.index("@media print {\n  .bit-strip-scroll") :]
    assert ".bit-strip-scroll, .bit-fields-wrap { overflow: visible; }" in print_rules
    forced = CSS[CSS.index("@media (forced-colors: active) {\n  .bit-table") :]
    assert "Highlight" in forced[: forced.index("}\n\n")]
    assert "GrayText" in forced[: forced.index("}\n\n")]
    # Not colour alone: a differing bit is also heavier and framed
    differs = CSS[CSS.index(".bit-table .bit-actual .differs .bit") :]
    assert "font-weight: 700" in differs[: differs.index("}")]
    assert "border-color: var(--c-failed)" in differs[: differs.index("}")]


# ---------------------------------------------------------------------------
# With the plugins (pytest-verifier 0.11+, stepdoc with actual_text)
# ---------------------------------------------------------------------------

SUITE = """
from stepdoc import step

MASK = 0x00FF
FIELDS = {"EN": 0, "MODE": (3, 1)}


class Reg:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.value == other

    def __hash__(self):
        return hash(self.value)

    def __verify_format__(self):
        return {"radix": "hex", "width": 16, "fields": FIELDS, "value": self.value}


class Dev:
    CTRL = 0x12F0


def test_registers(verify):
    dev, wdata = Dev(), 0xABF3
    with step("Read back"):
        verify.bits(dev.CTRL, wdata, mask=MASK, fields=FIELDS, width=16, name="Low byte")
        verify.equal(Reg(0x00F0), 0x00F3, name="CTRL")
        verify.equal(2**64 - 1, 2**64 - 2, radix="hex", width=64, name="COUNT")
        verify.bits(dev.CTRL, 0x12F0, mask=MASK, width=16, name="Same")
"""


@requires_bits
def test_records_reach_checks_json_and_the_page(pytester: Pytester) -> None:
    pytest.importorskip("stepdoc")
    pytester.makepyfile(test_reg=SUITE)
    pytester.runpytest("--report-dir=reports").assert_outcomes(failed=1)
    run_dir = _run_dir(pytester)
    saved = json.loads(next(run_dir.rglob("checks.json")).read_text(encoding="utf-8"))["checks"]
    low, ctrl, count, same = saved
    assert low["check_type"] == "bits"
    assert low["rendered"] == {"actual": "0x12F0", "expected": "0xABF3", "mask": "0x00FF"}
    assert low["bit_diff"]["text"] == "bits [1:0] differ"
    assert low["fields"] == {"EN": [0, 0], "MODE": [3, 1]}
    assert ctrl["actual"] == 0x00F0 and ctrl["rendered"]["actual"] == "0x00F0"
    assert count["actual"] == 2**64 - 1
    assert same["passed"] is True
    (run,) = (r for t in _data(run_dir)["tests"] for r in t["runs"])
    page = run["check_results"]
    assert page[0] == low
    assert page[2]["actual"] == {"$repr": "18446744073709551615"}
    assert page[2]["rendered"] == {
        "actual": "0xFFFF_FFFF_FFFF_FFFF",
        "expected": "0xFFFF_FFFF_FFFF_FFFE",
    }


@requires_node
@requires_bits
def test_real_records_render(pytester: Pytester) -> None:
    """The reporter's field texts are pytest-verifier's own, record by record."""
    pytest.importorskip("stepdoc")
    pytester.makepyfile(test_reg=SUITE)
    pytester.runpytest("--report-dir=reports").assert_outcomes(failed=1)
    (run,) = (r for t in _data(_run_dir(pytester))["tests"] for r in t["runs"])
    out = _node(
        f"""
        const checks = {json.dumps(run["check_results"])};
        console.log(JSON.stringify(checks.map(c => ({{
          model: (m => m && [m.width, m.cells.filter(c => c.differs).map(c => c.bit)])(
            bitStripModel(c)),
          fields: fieldRows(c).filter(r => r.differs).map(r => [r.name, r.actual, r.expected]),
          rows: rows(renderCheckDetail(c)),
        }}))));
        """
    )
    for shown, record in zip(out, run["check_results"], strict=True):
        told = [
            [f["name"], f["actual"], f["expected"]]
            for f in (record.get("bit_diff") or {}).get("fields", [])
        ]
        assert shown["fields"] == told
        assert shown["rows"]["Result"] == record["detail"]
    assert [o["model"] for o in out] == [[16, [1, 0]], [16, [1, 0]], [64, [0]], [16, []]]
    assert out[1]["rows"]["Actual"] == "0x00F0(240)"
    assert out[2]["rows"]["Actual"] == "0xFFFF_FFFF_FFFF_FFFF"


@requires_register_stepdoc
def test_procedure_lines_of_register_checks(pytester: Pytester) -> None:
    pytester.makepyfile(test_reg=SUITE)
    pytester.runpytest("--report-dir=reports").assert_outcomes(failed=1)
    procedure = json.loads(
        next(_run_dir(pytester).rglob("procedure.json")).read_text(encoding="utf-8")
    )
    (step,) = procedure["steps"]
    low, ctrl, count, same = step["substeps"]
    assert low["description"] == "Verify 'Low byte': dev.CTRL & 0x00FF == <wdata> (0x00F3)"
    assert low["generic"] == "Verify 'Low byte': dev.CTRL & <MASK> == <wdata>"
    assert low["result"] == f"got 0x12F0, bits [1:0] differ: {FIELDS_DETAIL}"
    assert low["outcome"] == "failed"
    assert "detail" not in low
    assert ctrl["result"] == f"got 0x00F0, bits [1:0] differ: {FIELDS_DETAIL}"
    assert count["result"] == "got 0xFFFF_FFFF_FFFF_FFFF, bit 0 differs"
    assert same["description"] == "Verify 'Same': dev.CTRL & 0x00FF == 0x00F0"
    assert same["result"] == "got 0x12F0"
    assert same["outcome"] == "passed"
    # The Generic view holds no value of this run
    assert "0x12F0" not in low["generic"] and "0x00F3" not in low["generic"]
    assert all("differ" not in node["generic"] for node in step["substeps"])


@requires_node
def test_a_mask_of_every_bit_says_nothing_about_bits_outside_it() -> None:
    """No cell is dimmed: no legend entry and no sentence about bits not compared."""
    whole = {**BITS, "mask": 0xFFFF, "rendered": {**BITS["rendered"], "mask": "0xFFFF"}}
    out = _node(
        f"""
        const strip = c => {{ const s = renderBitStrip(c); return {{
          label: byTag(s, 'table')[0].attrs['aria-label'], key: texts(s, 'bit-key'),
          masked: findAll(s, 'masked').length, outside: bitStripModel(c).outside}}; }};
        console.log(JSON.stringify([{_js(whole)}, {_js(BITS)}, {_js(EQUAL)}].map(strip)));
        """
    )
    whole_out, partial, equal = out
    assert whole_out["outside"] is False
    assert whole_out["masked"] == 0
    assert "outside the mask" not in whole_out["label"]
    assert whole_out["label"].startswith("Bits 15 to 0, expected above actual. ")
    assert all("outside the mask" not in key for key in whole_out["key"])
    assert partial["outside"] is True
    assert partial["key"][-1] == "1outside the mask, not compared"
    assert equal["outside"] is False


@requires_node
def test_fields_table_scroller_is_reachable_and_named() -> None:
    """On a phone the table scrolls sideways: from the keyboard too, as the strip does."""
    out = _node(
        f"""
        const t = renderFieldsTable({_js(BITS)});
        console.log(JSON.stringify([t.className, t.attrs.role, t.attrs.tabindex,
          t.attrs['aria-label']]));
        """
    )
    assert out == ["bit-fields-wrap", "group", "0", "Fields: actual and expected"]
    assert ".bit-fields-wrap:focus-visible { outline: 2px solid var(--c-accent);" in CSS


def test_bit_numbers_outside_the_mask_keep_their_contrast() -> None:
    """The muted colour is enough: a lower opacity on top put 11px text under 4.5:1."""
    assert ".bit-table .masked .bit, .bit-key-swatch.masked {" in CSS
    for line in CSS.splitlines():
        if "masked" in line and line.lstrip().startswith(".bit-"):
            assert "opacity" not in line, line


def test_a_check_result_never_squeezes_its_text() -> None:
    """Procedure tab: the text keeps a width; on a phone the result has its own line."""
    assert ".procedure-step-header {\n  display: flex;\n  flex-wrap: wrap;" in CSS
    assert ".procedure-step-desc { color: var(--c-text); flex: 1 1 9em; min-width: 0; }" in CSS
    phone = CSS[CSS.index("@media (max-width: 640px) {\n  .bench-change-at") :]
    phone = phone[: phone.index("\n}\n")]
    assert ".procedure-step-header > .procedure-result { flex-basis: 100%;" in phone
