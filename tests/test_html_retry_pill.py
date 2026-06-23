"""Tree-level retry pill: a test that retried shows a ↻ badge in the Tests tree.

With 100% green, a passed-on-retry test looks identical to a clean pass in the
tree. This adds a per-test ↻ pill so flaky passes are visible at a glance,
without drilling into the run pills or the Retries sub-tab.

JS is not executed by the suite, so these assert on the embedded render source.
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


def test_tree_retry_pill_render_present(pytester: Pytester) -> None:
    html = _gen(pytester)
    assert "anyRetried" in html, "renderTestLeaf must detect whether any run retried"
    assert "tree-badge retried" in html, "a retried test must render a tree-badge retried pill"


def test_tree_retry_pill_css_defined(pytester: Pytester) -> None:
    html = _gen(pytester)
    assert ".tree-badge.retried" in html, "CSS must define .tree-badge.retried"
