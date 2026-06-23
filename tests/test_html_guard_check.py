"""Render support for the pytest-verify ``guard`` check type (if/elif/else).

A guard descriptor carries ``branches`` ([{condition, label, check}]),
``default`` (CheckDescriptor | null) and ``matched_index`` (int | null) — none
of the flat leaf fields (actual/expected/...). The reporter must render the
branch chain, mark the evaluated branch (matched_index, or default when null),
and recurse into the chosen branch's nested check. Presentation only — the
reporter never evaluates; pass/fail comes from the descriptor's ``passed``.

JS is not executed by the suite, so these assert on the embedded render source
(consistent with the rest of the HTML tests).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def _gen(pytester: Pytester) -> str:
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    pytester.runpytest("--report-dir=reports")
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return (runs[0] / "report.html").read_text(encoding="utf-8")


def test_guard_dispatch_present(pytester: Pytester) -> None:
    html = _gen(pytester)
    assert "renderGuardBody" in html, "guard checks must dispatch to renderGuardBody"
    assert "'guard'" in html, "render must branch on check_type === 'guard'"


def test_guard_branch_rendering_present(pytester: Pytester) -> None:
    html = _gen(pytester)
    # Branch chain markers and the matched-branch logic must be in the render.
    assert "guard-branch" in html, "guard branches must render with a guard-branch element"
    assert "matched_index" in html, "render must use matched_index to mark the evaluated branch"


def test_guard_css_defined(pytester: Pytester) -> None:
    html = _gen(pytester)
    assert ".guard-branch" in html, "CSS must define .guard-branch"
    assert ".guard-branch.chosen" in html, "CSS must style the evaluated (chosen) branch"
