"""Composite verify checks: conditional/all_satisfy rendering + child dedup.

Two concerns:
  1. The reporter must render check_type 'conditional' and 'all_satisfy' as a
     branch/case chain (like 'guard'), not as an empty card.
  2. Some pytest-verify versions auto-record a composite's child checks as
     independent stash entries. Those children are already shown inside their
     parent, so the reporter must drop them — filtered by object identity at
     capture time (before JSON serialization).

The dedup is a pure Python function (executable, not a JS-source marker).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


# ── Dedup helper (pure Python, real behavior) ───────────────────────────


def test_strip_guard_children_and_default() -> None:
    from pytest_reporter._phase_capture import _strip_nested_check_children

    child = {"check_type": "approx", "name": "Vout", "description": "d", "passed": True}
    deflt = {"check_type": "fail", "name": "def", "description": "d", "passed": False}
    guard = {
        "check_type": "guard",
        "name": "g",
        "description": "d",
        "branches": [{"condition": True, "label": "b", "check": child}],
        "default": deflt,
        "matched_index": 0,
        "passed": True,
    }
    # child + default leaked as independent top-level entries alongside the guard
    assert _strip_nested_check_children([child, guard, deflt]) == [guard]


def test_strip_conditional_and_all_satisfy_children() -> None:
    from pytest_reporter._phase_capture import _strip_nested_check_children

    c1 = {"check_type": "equal", "name": "a", "description": "d", "passed": True}
    cond = {
        "check_type": "conditional",
        "name": "c",
        "description": "d",
        "switch_value": "x",
        "cases": {"x": c1},
        "default": None,
        "matched_case": "x",
    }
    c2 = {"check_type": "greater", "name": "b", "description": "d", "passed": True}
    alls = {"check_type": "all_satisfy", "name": "s", "description": "d", "child_checks": [c2]}
    assert _strip_nested_check_children([c1, cond, c2, alls]) == [cond, alls]


def test_strip_keeps_independent_checks() -> None:
    from pytest_reporter._phase_capture import _strip_nested_check_children

    a = {"check_type": "equal", "name": "a", "description": "d", "passed": True}
    b = {"check_type": "equal", "name": "b", "description": "d", "passed": True}
    assert _strip_nested_check_children([a, b]) == [a, b]


def test_strip_nested_composite_grandchildren() -> None:
    from pytest_reporter._phase_capture import _strip_nested_check_children

    leaf = {"check_type": "approx", "name": "leaf", "description": "d", "passed": True}
    inner = {
        "check_type": "guard",
        "name": "inner",
        "description": "d",
        "branches": [{"condition": True, "label": "b", "check": leaf}],
        "default": None,
        "matched_index": 0,
        "passed": True,
    }
    outer = {
        "check_type": "guard",
        "name": "outer",
        "description": "d",
        "branches": [{"condition": True, "label": "b", "check": inner}],
        "default": None,
        "matched_index": 0,
        "passed": True,
    }
    # Both inner (direct child) and leaf (grandchild) leaked at top level
    assert _strip_nested_check_children([leaf, inner, outer]) == [outer]


# ── Conditional / all_satisfy rendering (JS source markers) ──────────────


def _gen(pytester: Pytester) -> str:
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    pytester.runpytest("--report-dir=reports")
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return (runs[0] / "report.html").read_text(encoding="utf-8")


def test_conditional_render_present(pytester: Pytester) -> None:
    html = _gen(pytester)
    assert "renderConditionalBody" in html, "render must handle check_type 'conditional'"
    assert "matched_case" in html, "conditional render must mark the matched case"


def test_all_satisfy_render_present(pytester: Pytester) -> None:
    html = _gen(pytester)
    assert "renderAllSatisfyBody" in html, "render must handle check_type 'all_satisfy'"
