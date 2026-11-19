"""How the report reads: one size floor, one duration format, values with their units.

The small functions run under Node; layout rules are pinned in the CSS text.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from types import SimpleNamespace as NS
from typing import Any

import pytest

from pytest_reporter._html_builder import _js_safe
from pytest_reporter._html_builder._css import CSS
from pytest_reporter._html_builder._js import JS
from pytest_reporter._stepdoc import _check_result

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    end = JS.index("\nfunction ", start + 1)
    return JS[start:end]


def _node(script: str, *names: str) -> Any:  # noqa: ANN401
    source = "\n".join([*(_function(n) for n in names), script])
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


# ---------------------------------------------------------------------------
# Durations
# ---------------------------------------------------------------------------


@requires_node
def test_one_duration_format_from_microseconds_to_minutes() -> None:
    values = [None, 0, 0.00001, 0.0003, 0.0094, 0.02, 0.85, 1.254, 59.4, 75]
    got = _node(
        f"console.log(JSON.stringify({json.dumps(values)}.map(formatSeconds)));",
        "formatSeconds",
        "formatDuration",
    )
    assert got[:9] == ["—", "0s", "<0.1ms", "0.3ms", "9.4ms", "20ms", "850ms", "1.25s", "59.40s"]
    assert got[9] == "1m 15s"


# ---------------------------------------------------------------------------
# Check values: units on the number, and how far it was from the limit
# ---------------------------------------------------------------------------

_CHECK_FUNCTIONS = ("isCheckNumber", "checkUnits", "checkDistanceLabel", "checkDistance")


@requires_node
@pytest.mark.parametrize(
    ("check", "label", "distance"),
    [
        (
            {"check_type": "greater", "actual": 86.59, "threshold": 90, "units": "%"},
            "Margin",
            "3.41% below the limit",
        ),
        (
            {"check_type": "less_equal", "actual": 5, "threshold": 5},
            "Margin",
            "at the limit",
        ),
        (
            {"check_type": "approx", "actual": 3.35, "expected": 3.3, "units": "V"},
            "Deviation",
            "0.05V above the expected value",
        ),
        (
            {"check_type": "between", "actual": 0.45, "low": 0.1, "high": 0.5, "units": "A"},
            "Margin",
            "0.05A below the high limit",
        ),
        (
            {"check_type": "between", "actual": 0.6, "low": 0.1, "high": 0.5},
            "Margin",
            "0.1 above the high limit",
        ),
        ({"check_type": "equal", "actual": 1, "expected": 2}, "Margin", ""),
        ({"check_type": "greater", "actual": "12", "threshold": 3}, "Margin", ""),
    ],
)
def test_distance_from_the_limit(check: dict[str, Any], label: str, distance: str) -> None:
    """Arithmetic on the record's own numbers: the verdict stays pytest-verifier's."""
    got = _node(
        f"const c = {json.dumps(check)};\n"
        "console.log(JSON.stringify([checkDistanceLabel(c), checkDistance(c)]));",
        *_CHECK_FUNCTIONS,
    )
    assert got == [label, distance]


def test_card_rows_carry_units_on_the_numbers() -> None:
    """A Units row of its own stays only for a check with no number to put it on."""
    body = _function("renderCheckDetail")
    assert "CHECK_QUANTITIES" in body
    assert "unitsShown" in body


def test_procedure_result_has_the_units_of_the_record() -> None:
    check = NS(actual=86.59, source={"units": "%"}, reads=[])
    assert _check_result(check) == "got 86.59%"
    assert _check_result(NS(actual=86.59, source=None, reads=[])) == "got 86.59"
    # Units belong to a measured number, not to text or a flag
    assert _check_result(NS(actual="OK", source={"units": "V"}, reads=[])) == "got 'OK'"
    assert _check_result(NS(actual=True, source={"units": "V"}, reads=[])) == "got True"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def test_integers_past_2_53_keep_every_digit() -> None:
    seed = 1795083645477594127
    data = {"seed": seed, "rows": [{"seed": seed, "n": 3, "ok": True}], "small": 2**53 - 1}
    assert _js_safe(data) == {
        "seed": str(seed),
        "rows": [{"seed": str(seed), "n": 3, "ok": True}],
        "small": 2**53 - 1,
    }


@requires_node
def test_skip_reason_is_read_from_pytests_tuple() -> None:
    longrepr = "('/repo/tests/test_psu.py', 225, 'Skipped: needs the interlock')"
    got = _node(
        f"console.log(JSON.stringify([skipParts({json.dumps(longrepr)}), skipParts('boom')]));",
        "skipParts",
    )
    assert got == [
        {"file": "/repo/tests/test_psu.py", "line": "225", "reason": "needs the interlock"},
        None,
    ]


# ---------------------------------------------------------------------------
# Layout and navigation
# ---------------------------------------------------------------------------


def test_tests_tab_is_one_screen_with_two_scrolling_panes() -> None:
    shell = CSS[CSS.index('body[data-tab="tests"]') :]
    shell = shell[: shell.index("}\n}") + 3]
    assert "height: 100dvh" in shell
    assert "overflow: hidden" in shell
    assert "document.body.dataset.tab = " in JS
    # Each test opens at its top
    assert "panel.scrollTop = 0" in _function("showTestDetail")


def test_no_match_message_takes_the_place_of_the_list() -> None:
    assert ".tree-panel.is-empty .tree-content { display: none; }" in CSS
    assert "classList.toggle('is-empty'" in JS


def test_phase_logs_scroll_with_the_page_not_inside_a_box() -> None:
    rule = CSS[CSS.index(".phase-tab-panel {") :]
    rule = rule[: rule.index("}")]
    assert "max-height" not in rule


def test_report_can_be_linked_to_a_test_and_stepped_with_keys() -> None:
    assert "'#test=' + encodeURIComponent(selectedRun.nodeid)" in _function("writeLocation")
    assert "hashchange" in JS
    assert "function stepTest(" in JS
    # The hints are for a keyboard: not on a phone or a touch screen
    hidden = "{ .tree-keys, .search-key { display: none; } }"
    assert "@media (max-width: 768px), (pointer: coarse) " + hidden in CSS


def test_feature_bars_show_what_did_not_pass() -> None:
    for part in ("failed", "error", "skipped"):
        assert f".pass-rate-bar-part.{part}" in CSS


def test_print_shows_what_a_click_would() -> None:
    printed = CSS[CSS.rindex("@media print {") :]
    assert ".failures-list li[hidden] { display: list-item; }" in printed
    assert ".phase-tab-panel { display: block; border: none; }" in printed
    assert ".sub-tabs" in printed  # controls that do nothing on paper are left out


def test_retry_badge_keeps_its_full_contrast() -> None:
    rule = CSS[CSS.index(".retry-badge {") :]
    assert "opacity" not in rule[: rule.index("}")]


def test_smooth_scroll_respects_reduced_motion() -> None:
    assert "behavior: prefersReducedMotion() ? 'auto' : 'smooth'" in JS
