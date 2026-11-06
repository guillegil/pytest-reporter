"""Composite pytest-verifier checks: conditional/all_satisfy rendering.

The reporter must render check_type 'conditional' and 'all_satisfy' as a
branch/case chain (like 'guard'), not as an empty card. pytest-verifier keeps
a composite's children inside it, so no child shows up as a card of its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


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
