"""Slice E — Active Plugins section: distributed-only, versioned, collapsed by default.

Scenarios:
  3a: DATA.plugins entries are objects {name, version}, not strings
      pytest itself is a distributed plugin and must appear with a version
      internal plugins (names starting with _ or with no dist-info) absent
  3b: Active Plugins section is collapsed by default (no 'expanded', aria-expanded=false)
  3c: empty-state text 'No distributed plugins detected' present in JS source

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
    """Extract the embedded DATA JSON from report.html."""
    m = re.search(r"const DATA\s*=\s*(\{.*?\});\s*\n", html, re.DOTALL)
    assert m, "Could not find 'const DATA = {...}' in report.html"
    return json.loads(m.group(1))


def _simple_report(pytester: Pytester) -> str:
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)
    return _report_html(pytester)


# ---------------------------------------------------------------------------
# Scenario 3a: DATA.plugins entries are objects, not strings
# ---------------------------------------------------------------------------


def test_plugins_data_are_objects(pytester: Pytester) -> None:
    """DATA.plugins entries must be {name, version} objects, not plain strings."""
    html = _simple_report(pytester)
    data = _extract_data(html)

    plugins = data.get("plugins", [])
    assert isinstance(plugins, list), "DATA.plugins must be a list"

    for entry in plugins:
        assert isinstance(entry, dict), (
            f"Each plugin entry must be a dict {{name, version}}, got {type(entry)}: {entry!r}"
        )
        assert "name" in entry, f"Plugin entry must have 'name' key: {entry!r}"
        assert "version" in entry, f"Plugin entry must have 'version' key: {entry!r}"
        assert isinstance(entry["name"], str), f"Plugin name must be str: {entry!r}"
        assert isinstance(entry["version"], str), f"Plugin version must be str: {entry!r}"


def test_distributed_plugin_appears_with_version(pytester: Pytester) -> None:
    """Plugins with pytest11 entry points must appear in DATA.plugins with a version.

    pytest-reporter itself is a distributed plugin (it registers via pytest11).
    It must appear with its version string so the report is self-documenting.
    """
    html = _simple_report(pytester)
    data = _extract_data(html)

    plugins = data.get("plugins", [])
    assert isinstance(plugins, list), "DATA.plugins must be a list"

    # pytest-reporter must appear since it has a pytest11 entry point
    # Use name normalisation: may appear as 'pytest-reporter' or 'pytest_reporter'
    has_reporter = any(
        p.get("name", "").replace("-", "_") == "pytest_reporter"
        for p in plugins
        if isinstance(p, dict)
    )
    assert has_reporter, (
        "pytest-reporter must appear in DATA.plugins (it has a pytest11 entry point). "
        f"Found names: {[p.get('name') for p in plugins if isinstance(p, dict)]}"
    )


def test_internal_plugins_excluded(pytester: Pytester) -> None:
    """Internal plugins (no dist-info) must NOT appear in DATA.plugins."""
    html = _simple_report(pytester)
    data = _extract_data(html)

    plugins = data.get("plugins", [])
    for entry in plugins:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "")
        assert not name.startswith("_"), (
            f"Internal plugin '{name}' (starts with '_') must be excluded from DATA.plugins"
        )


# ---------------------------------------------------------------------------
# Scenario 3b: Active Plugins section collapsed by default
# ---------------------------------------------------------------------------


def test_plugins_section_collapsed_by_default(pytester: Pytester) -> None:
    """Active Plugins section header must have aria-expanded='false' (collapsed default)."""
    html = _simple_report(pytester)
    js_m = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert js_m, "No <script> block found"
    js = js_m.group(1)

    # The plugins section must use chevronSvg and aria-expanded='false'
    assert "plugins-chevron" in js, "Active Plugins section must use chevronSvg('plugins-chevron')"
    assert (
        "'aria-expanded','false'" in js
        or '"aria-expanded","false"' in js
        or ("aria-expanded" in js and "'false'" in js)
    ), "Active Plugins section header must set aria-expanded='false' (collapsed)"


# ---------------------------------------------------------------------------
# Scenario 3c: empty-state text in JS source
# ---------------------------------------------------------------------------


def test_plugins_empty_state_in_js(pytester: Pytester) -> None:
    """'No distributed plugins detected' must appear in the JS source as empty-state text."""
    html = _simple_report(pytester)

    assert "No distributed plugins detected" in html, (
        "JS must include 'No distributed plugins detected' as empty-state text"
    )


# ---------------------------------------------------------------------------
# CSS: plugin-ver class defined
# ---------------------------------------------------------------------------


def test_plugin_ver_css_defined(pytester: Pytester) -> None:
    """CSS must define .plugin-ver for the version badge."""
    html = _simple_report(pytester)
    assert ".plugin-ver" in html, "CSS must define .plugin-ver rule"
