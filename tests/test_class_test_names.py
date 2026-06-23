"""Slice D — readable class-based test names in Tests tab.

Scenarios:
  1f: folder path unchanged for class-based tests (function_name FROZEN)
  1b: DATA fields class_name='TestPowerSupply', display_name='test_voltage_ok'
  1a: plain function -> class_name=null, display_name='test_simple'
  1d/1e: tree search matches class name AND bare function name

Note: pytest.warns does NOT cross the pytester subprocess boundary.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_dir(pytester: Pytester) -> pathlib.Path:
    runs_dir = pytester.path / "reports" / "runs"
    runs = sorted(runs_dir.iterdir())
    assert len(runs) == 1, f"Expected 1 run dir, got {len(runs)}"
    return runs[0]


def _report_html(pytester: Pytester) -> str:
    return (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")


def _extract_data(html: str) -> dict:  # type: ignore[type-arg]
    """Extract the embedded DATA JSON from a report.html.

    The template marker /*__REPORT_DATA__*/ is replaced at build time with
    the actual JSON object, so the HTML contains: ``const DATA = {...};``
    """
    m = re.search(r"const DATA\s*=\s*(\{.*?\});\s*\n", html, re.DOTALL)
    assert m, "Could not find 'const DATA = {...}' in report.html"
    return json.loads(m.group(1))


def _run_class_test(pytester: Pytester) -> tuple[pathlib.Path, dict]:  # type: ignore[type-arg]
    """Run a class-based test and return (run_dir, DATA)."""
    pytester.makepyfile("""
        class TestPowerSupply:
            def test_voltage_ok(self):
                assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)
    run_dir = _run_dir(pytester)
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    data = _extract_data(html)
    return run_dir, data


# ---------------------------------------------------------------------------
# Scenario 1f: folder path unchanged (function_name FROZEN as Class::method)
# ---------------------------------------------------------------------------


def test_folder_path_unchanged_for_class_test(pytester: Pytester) -> None:
    """On-disk folder path must use sanitized TestPowerSupply__test_voltage_ok/default/.

    function_name is frozen as 'TestPowerSupply::test_voltage_ok'; the path
    sanitizer maps '::' to '__', producing 'TestPowerSupply__test_voltage_ok'.
    This byte-identical behavior must be unchanged by Slice D.
    """
    run_dir, _ = _run_class_test(pytester)

    # Walk the tests directory and find the test folder
    tests_dir = run_dir / "tests"
    assert tests_dir.exists(), "tests/ dir must exist"

    # Find the function folder — '::' is sanitized to '__' on disk
    found = list(tests_dir.rglob("TestPowerSupply__test_voltage_ok"))
    assert found, (
        "On-disk folder must use 'TestPowerSupply__test_voltage_ok' as the "
        "function folder name (byte-identical to pre-change; '::' sanitized to '__')"
    )
    # The default/ subfolder must exist inside it
    func_dir = found[0]
    assert (func_dir / "default").exists(), (
        "default/ subfolder must exist inside TestPowerSupply__test_voltage_ok/"
    )


# ---------------------------------------------------------------------------
# Scenario 1b: DATA fields class_name and display_name
# ---------------------------------------------------------------------------


def test_class_name_and_display_name_in_data(pytester: Pytester) -> None:
    """DATA.tests[].aggregate must have class_name and display_name for class tests."""
    _, data = _run_class_test(pytester)

    tests = data["tests"]
    assert len(tests) == 1, "Expected exactly 1 test in DATA"

    agg = tests[0]["aggregate"]
    assert agg.get("class_name") == "TestPowerSupply", (
        f"aggregate.class_name must be 'TestPowerSupply', got {agg.get('class_name')!r}"
    )
    assert agg.get("display_name") == "test_voltage_ok", (
        f"aggregate.display_name must be 'test_voltage_ok', got {agg.get('display_name')!r}"
    )
    # function_name must be the full Class::method (frozen)
    assert agg.get("function_name") == "TestPowerSupply::test_voltage_ok", (
        f"aggregate.function_name must be frozen as 'TestPowerSupply::test_voltage_ok', "
        f"got {agg.get('function_name')!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 1a: plain function -> class_name null, display_name equals function_name
# ---------------------------------------------------------------------------


def test_plain_function_has_null_class_name(pytester: Pytester) -> None:
    """Plain function tests must have class_name=null and display_name=function_name."""
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    data = _extract_data(html)

    tests = data["tests"]
    assert len(tests) == 1
    agg = tests[0]["aggregate"]

    assert agg.get("class_name") is None, (
        f"class_name must be null for plain function test, got {agg.get('class_name')!r}"
    )
    assert agg.get("display_name") == "test_simple", (
        f"display_name must be 'test_simple', got {agg.get('display_name')!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 1d/1e: JS search matches both class name and bare function name
# ---------------------------------------------------------------------------


def test_js_search_includes_class_name(pytester: Pytester) -> None:
    """filterTree JS must include class_name in search matching."""
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _report_html(pytester)
    # The filterTree function must reference class_name in its match condition
    assert "class_name" in html, "JS must reference class_name in filterTree for search matching"


# ---------------------------------------------------------------------------
# JS render: testDisplayName helper + eyebrow elements
# ---------------------------------------------------------------------------


def test_js_render_helpers_present(pytester: Pytester) -> None:
    """JS must define testDisplayName helper and render eyebrow elements."""
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _report_html(pytester)

    assert "testDisplayName" in html, "JS must define testDisplayName helper"
    assert "tree-class" in html, "JS must render class grouping node (tree-class)"
    assert "detail-eyebrow" in html, "JS must render detail-eyebrow element"


# ---------------------------------------------------------------------------
# CSS: eyebrow classes defined
# ---------------------------------------------------------------------------


def test_css_eyebrow_classes_defined(pytester: Pytester) -> None:
    """CSS must define .tree-eyebrow and .detail-eyebrow."""
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    html = _report_html(pytester)

    assert ".tree-class" in html, "CSS must define .tree-class"
    assert ".detail-eyebrow" in html, "CSS must define .detail-eyebrow"
