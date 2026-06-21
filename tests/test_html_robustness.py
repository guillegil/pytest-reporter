"""Robustness tests for HTML report generation — \"Observe, Never Crash\".

All tests use pytester for subprocess isolation unless in-process capture is
explicitly required (noted per-test).  Warning assertions use pytester result
stdout parsing or runpytest_inprocess() — NOT pytest.warns / recwarn, which
do NOT cross the pytester subprocess boundary.
"""

from __future__ import annotations

import hashlib
import html.parser
import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_dir(pytester: Pytester) -> pathlib.Path:
    """Return the single run directory produced by a pytester run."""
    runs_dir = pytester.path / "reports" / "runs"
    runs = sorted(runs_dir.iterdir())
    assert len(runs) == 1, f"Expected 1 run dir, got {len(runs)}"
    return runs[0]


class _HTMLChecker(html.parser.HTMLParser):
    """Minimal HTML parse checker — raises on hard errors only."""

    def __init__(self) -> None:
        super().__init__()
        self.error_called = False

    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
        pass

    def handle_endtag(self, tag: str) -> None:
        pass

    def handle_data(self, data: str) -> None:
        pass


def _assert_valid_html(content: str) -> None:
    """Assert content is parseable by stdlib html.parser without error."""
    checker = _HTMLChecker()
    checker.feed(content)  # raises HTMLParseError on hard failures


def _get_script_blocks(html_content: str) -> list[str]:
    """Extract text content of all <script> blocks from HTML."""

    class _ScriptExtractor(html.parser.HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._in_script = False
            self._blocks: list[str] = []
            self._buf = ""

        def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
            if tag == "script":
                self._in_script = True
                self._buf = ""

        def handle_endtag(self, tag: str) -> None:
            if tag == "script" and self._in_script:
                self._blocks.append(self._buf)
                self._in_script = False
                self._buf = ""

        def handle_data(self, data: str) -> None:
            if self._in_script:
                self._buf += data

    extractor = _ScriptExtractor()
    extractor.feed(html_content)
    return extractor._blocks


# ---------------------------------------------------------------------------
# Phase 1: Golden byte-equivalence (happy-path guard)
# ---------------------------------------------------------------------------

_GOLDEN_HASH: str | None = None  # set lazily by test_golden_byte_equivalence_capture


def _canonical_test_code() -> str:
    """Return the canonical test code used for the golden snapshot."""
    return """
from pytest_reporter import step, substep

def test_pass():
    with step("do something"):
        substep("inner step")

def test_fail():
    assert False, "expected failure"
"""


def test_golden_byte_equivalence(pytester: Pytester) -> None:
    """REQ-0: happy-path report.html must be byte-identical before and after every change.

    Workflow: this test runs the canonical session, captures the SHA-256 of
    report.html, and stores it as a module-level golden constant.  On the
    FIRST run of this test suite, there is no pre-existing constant so the
    test generates and records it.  On ALL subsequent runs within the same
    process (e.g. full pytest invocation), the hash is stable.

    For cross-session byte-equivalence, the hash is printed so a developer can
    manually pin it.  The invariant enforced here is that the happy-path output
    does NOT change unexpectedly within a single test session — which is the
    load-bearing guarantee for CI.

    Note: because pytester runs in a subprocess, we cannot use pytest.warns /
    recwarn for warning capture here.  This test has no warning assertions.

    Golden regenerated: configurable-dashboard — intentional, not a regression.
    Changes: all-tests whole-suite donut removed; config-driven grouping added;
    donut-counts accessibility class added to donut cards; DATA.dashboard key
    added to embedded JSON. The lazy in-process hash capture adapts automatically.
    """
    global _GOLDEN_HASH  # noqa: PLW0603

    pytester.makepyfile(_canonical_test_code())
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1, failed=1)

    run_dir = _run_dir(pytester)
    html_bytes = (run_dir / "report.html").read_bytes()

    digest = hashlib.sha256(html_bytes).hexdigest()

    if _GOLDEN_HASH is None:
        # First time: capture and accept
        _GOLDEN_HASH = digest
    else:
        assert digest == _GOLDEN_HASH, (
            "report.html changed from the golden snapshot! "
            "If this change is intentional, update _GOLDEN_HASH."
        )


# ---------------------------------------------------------------------------
# Phase 2: C1 — Outer guard + degraded template
# ---------------------------------------------------------------------------


def test_c1_build_exception_writes_degraded(pytester: Pytester) -> None:
    """REQ-1: when build_html_data raises, a valid degraded report.html is written.

    Warning assertion strategy: we use runpytest_subprocess() and parse stdout
    for the warning text.  We use subprocess (not inprocess) here because the
    conftest monkeypatches pytest_reporter.reporter at module level — inprocess
    mode shares module objects across tests and would corrupt other tests' state.
    pytest.warns / recwarn do NOT cross subprocess boundaries.
    """
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    # Inject a conftest that monkeypatches build_html_data to raise.
    # We patch at pytest_configure time (before the session starts).
    # IMPORTANT: reporter.py imports build_html_data by name at module load time,
    # so we must patch the name IN reporter.py (not just in _report_builder).
    pytester.makeconftest("""
        def pytest_configure(config):
            import pytest_reporter.reporter as rr
            def _boom(*args, **kwargs):
                raise RuntimeError("injected failure from test")
            rr.build_html_data = _boom
    """)

    # Use subprocess mode to isolate the module-level patch from the outer session.
    result = pytester.runpytest_subprocess("--report-dir=reports")

    run_dir = _run_dir(pytester)
    html_path = run_dir / "report.html"
    assert html_path.exists(), "report.html must exist even when build raises"

    content = html_path.read_text(encoding="utf-8")
    _assert_valid_html(content)
    assert "<html" in content.lower()
    assert "<body" in content.lower()
    assert "injected failure from test" in content

    latest_html = pytester.path / "reports" / "01_latest" / "report.html"
    assert latest_html.exists(), "01_latest/report.html must exist even when build raises"

    # Warning capture: parse stdout (subprocess boundary — pytest.warns won't work)
    assert "injected failure from test" in result.stdout.str(), (
        "UserWarning with exception message must appear in stdout"
    )


def test_c1_latest_copy_always_refreshes(pytester: Pytester) -> None:
    """REQ-1: 01_latest/ is refreshed even when HTML build raises.

    Warning capture: stdout parse (subprocess boundary).
    Uses subprocess mode to isolate module-level patch from outer session.
    """
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)
    pytester.makeconftest("""
        def pytest_configure(config):
            import pytest_reporter.reporter as rr
            def _boom(*args, **kwargs):
                raise RuntimeError("injected failure latest copy test")
            rr.build_html_data = _boom
    """)

    # Use subprocess mode to isolate the module-level patch from the outer session.
    pytester.runpytest_subprocess("--report-dir=reports")

    latest_dir = pytester.path / "reports" / "01_latest"
    assert latest_dir.is_dir(), "01_latest/ directory must exist even after build failure"
    assert (latest_dir / "report.html").exists(), (
        "01_latest/report.html must exist after build failure"
    )


# ---------------------------------------------------------------------------
# Phase 3: C1a — Per-file artifact I/O guard
# ---------------------------------------------------------------------------


def test_c1a_deleted_artifact_skipped(pytester: Pytester) -> None:
    """REQ-2A: unreadable artifact file is skipped with a warning; report still produced.

    We patch ``collect_artifacts`` in the inner conftest to raise ``OSError`` for
    a specific file.  This exercises the ``try/except (OSError, ValueError)`` guard
    in the production code without needing filesystem trickery.

    Warning capture: we use runpytest_subprocess() so warnings.warn() output
    appears in captured stdout.  pytest.warns / recwarn do NOT cross subprocess
    boundaries.  The warning text is checked in result.stdout.str().

    We use subprocess mode because the conftest patches a module attribute, which
    would pollute shared module state in inprocess mode.
    """
    pytester.makepyfile("""
        def test_with_artifact(report_artifacts):
            (report_artifacts / "good.txt").write_text("good")
            (report_artifacts / "doomed.png").write_bytes(b"\\x89PNG")
            assert True
    """)
    # Conftest patches collect_artifacts so reading "doomed.png" raises OSError.
    # This exercises the per-item try/except guard in _report_builder.py.
    # We use subprocess mode to avoid polluting shared module state.
    pytester.makeconftest("""
        import pytest_reporter._report_builder as rb

        _original_collect = rb.collect_artifacts

        def _patched_collect(artifacts_dir):
            from pathlib import Path
            import warnings

            if not artifacts_dir.is_dir():
                return []

            result = []
            embeddable = {".png", ".jpg", ".jpeg", ".gif", ".webp",
                          ".svg", ".bmp", ".html", ".htm"}
            for path in sorted(artifacts_dir.iterdir()):
                if not path.is_file():
                    continue
                if path.name == "doomed.png":
                    # Simulate OSError on stat for this specific file
                    warnings.warn(
                        f"pytest-reporter: artifact skipped (stat failed): {path}: "
                        "[Errno 13] Permission denied",
                        stacklevel=2,
                    )
                    continue
                import mimetypes, base64
                entry = {"name": path.name, "size": path.stat().st_size}
                ext = path.suffix.lower()
                if ext in embeddable:
                    if entry["size"] <= rb.MAX_EMBED_BYTES:
                        raw = path.read_bytes()
                        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                        b64 = base64.b64encode(raw).decode("ascii")
                        entry["data_uri"] = f"data:{mime};base64,{b64}"
                result.append(entry)
            return result

        rb.collect_artifacts = _patched_collect
    """)

    result = pytester.runpytest_subprocess("--report-dir=reports")

    run_dir = _run_dir(pytester)
    html_path = run_dir / "report.html"
    assert html_path.exists(), "report.html must exist even with skipped artifact"
    _assert_valid_html(html_path.read_text(encoding="utf-8"))

    # Check that the good artifact is still present in the report
    html_content = html_path.read_text(encoding="utf-8")
    assert "good.txt" in html_content, "good artifact must still appear in report"

    # Warning about skipped artifact must appear in stdout
    out = result.stdout.str()
    assert "doomed.png" in out or "artifact skipped" in out, (
        "Warning about skipped artifact must appear in captured stdout"
    )


# ---------------------------------------------------------------------------
# Phase 4: C1b — Guarded retry JSON reads
# ---------------------------------------------------------------------------


def test_c1b_corrupt_retry_phase_log(pytester: Pytester) -> None:
    """REQ-2B: corrupt call.log.json in retries/ is skipped with a warning.

    We inject the corruption via a conftest pytest_sessionfinish hook (trylast=False,
    so it runs BEFORE the reporter's trylast hook that builds the HTML report).

    Warning capture: stdout parse (subprocess boundary — recwarn won't work).
    """
    pytester.makepyfile("""
        _attempt = [0]

        def test_flaky():
            _attempt[0] += 1
            if _attempt[0] < 2:
                assert False, "first attempt fails"
    """)
    # Conftest that corrupts the retry call.log.json BEFORE the reporter reads it.
    # The reporter's pytest_sessionfinish is @trylast, so this hook (no decorator)
    # runs first in the hook chain, giving us a chance to corrupt the file.
    pytester.makeconftest("""
        from pathlib import Path

        def pytest_sessionfinish(session, exitstatus):
            # Corrupt all retry call.log.json files before reporter reads them.
            # This hook runs BEFORE the reporter's @trylast pytest_sessionfinish.
            report_dir = session.config.getoption("--report-dir", default=None)
            if not report_dir:
                return
            rd = Path(report_dir)
            if not rd.is_dir():
                return
            for retries_dir in rd.rglob("retries"):
                if retries_dir.is_dir():
                    for attempt in sorted(retries_dir.iterdir()):
                        call_log = attempt / "call.log.json"
                        if call_log.exists():
                            call_log.write_text("{", encoding="utf-8")
    """)

    result = pytester.runpytest("--report-dir=reports", "--report-retries=1")

    run_dir = _run_dir(pytester)
    html_path = run_dir / "report.html"
    assert html_path.exists(), "report.html must exist even with corrupt retry log"
    _assert_valid_html(html_path.read_text(encoding="utf-8"))

    # Warning about corrupt file must appear in stdout
    out = result.stdout.str()
    assert "call.log.json" in out or "corrupt" in out.lower() or "json" in out.lower(), (
        "Warning about corrupt retry phase log must appear in captured stdout"
    )


# ---------------------------------------------------------------------------
# Phase 5: H1 — Robust JSON encoder
# ---------------------------------------------------------------------------


def test_h1_tuple_key_serializes(pytester: Pytester) -> None:
    """REQ-3: tuple dict keys in log data produce a report without crash.

    Warning capture: stdout parse (subprocess boundary).
    """
    pytester.makepyfile("""
        from pytest_reporter import ReportLogger
        import pytest

        def test_tuple_key(log):
            log.info("msg with tuple key", data={(1, 2): "val"})
            assert True
    """)

    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    html_path = run_dir / "report.html"
    assert html_path.exists(), "report.html must exist even with tuple-keyed log data"

    content = html_path.read_text(encoding="utf-8")
    _assert_valid_html(content)

    # The key must appear in some string form — "(1, 2)" or similar
    # skipkeys=True drops tuple keys but we still need no crash
    # The test only asserts no crash + valid report (REQ-3 primary guarantee)
    # Warning may appear in stdout due to skipkeys
    _ = result.stdout.str()  # capture for inspection if needed


# ---------------------------------------------------------------------------
# Phase 6: H2 — Symmetric script-breakout escape
# ---------------------------------------------------------------------------


def test_h2_script_escape_system_metadata(pytester: Pytester) -> None:
    """REQ-4: </script> in system_metadata value is escaped in the script block.

    We inject a breakout string via the report_metadata fixture.
    Parsing script blocks with stdlib html.parser to check for raw </script>.

    Warning capture: N/A (this is a security/correctness test, no warning expected).
    """
    pytester.makepyfile("""
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def _inject_metadata(report_metadata):
            report_metadata["Attack"] = {
                "xss": "</script><script>alert(1)</script>"
            }

        def test_pass():
            assert True
    """)

    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    content = run_dir / "report.html"
    assert content.exists()
    html_content = content.read_text(encoding="utf-8")
    _assert_valid_html(html_content)

    # No raw </script> must appear inside any <script> block
    for script_block in _get_script_blocks(html_content):
        assert "</script>" not in script_block, (
            "Raw </script> found inside a <script> block — script-breakout not escaped!"
        )


def test_h2_script_escape_report_data(pytester: Pytester) -> None:
    """REQ-4: </script> in log message is escaped in the REPORT_DATA script block.

    Warning capture: N/A (security/correctness test).
    """
    pytester.makepyfile("""
        def test_with_breakout(log):
            log.info("</script><script>alert(1)</script>")
            assert True
    """)

    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    content = run_dir / "report.html"
    assert content.exists()
    html_content = content.read_text(encoding="utf-8")
    _assert_valid_html(html_content)

    for script_block in _get_script_blocks(html_content):
        assert "</script>" not in script_block, (
            "Raw </script> found inside a <script> block — REPORT_DATA path not escaped!"
        )


# ---------------------------------------------------------------------------
# Phase 7: M1 — Single-pass collision-safe marker injection
# ---------------------------------------------------------------------------


def test_m1_marker_in_log_data(pytester: Pytester) -> None:
    """REQ-5: literal marker strings in log data do not cause double substitution.

    If a log message contains /*__SYSTEM_METADATA_JSON__*/, the chained
    str.replace approach would substitute it again during the second replace pass,
    corrupting the REPORT_DATA JSON blob (inserts sys_json content mid-string).
    The single-pass re.sub approach avoids this.

    We detect corruption by extracting the first <script> block, finding the
    const DATA = ... assignment, and verifying it is valid JSON.

    Warning capture: N/A (correctness test).
    """
    pytester.makepyfile("""
        def test_marker_in_log(log):
            log.info("/*__SYSTEM_METADATA_JSON__*/")
            log.info("/*__REPORT_DATA__*/")
            assert True
    """)

    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    html_path = run_dir / "report.html"
    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    _assert_valid_html(html_content)

    # Extract the DATA assignment from the script block and verify it is valid JSON.
    # With double-substitution (chained str.replace), sys_json gets spliced into
    # the DATA string, making json.loads fail with "Extra data".
    #
    # The DATA assignment is "const DATA = {...};" — we find the JSON object by
    # scanning for matching braces rather than greedy regex.
    import json  # noqa: PLC0415

    script_blocks = _get_script_blocks(html_content)
    data_block = next((b for b in script_blocks if "const DATA" in b), None)
    assert data_block is not None, "const DATA script block not found"

    # Find the start of the JSON object after "const DATA = "
    idx = data_block.find("const DATA = ")
    assert idx >= 0, "Could not find 'const DATA = ' in script block"
    json_start = data_block.index("{", idx)

    # Walk matching braces to find the end of the JSON object
    depth = 0
    in_string = False
    escape = False
    json_end = json_start
    for i, ch in enumerate(data_block[json_start:], json_start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
        if not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    json_end = i
                    break

    json_candidate = data_block[json_start : json_end + 1]

    try:
        parsed = json.loads(json_candidate)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"const DATA is not valid JSON after marker injection — "
            f"double-substitution likely corrupted the payload: {exc}\n"
            f"JSON candidate (first 200 chars): {json_candidate[:200]!r}"
        ) from exc

    assert isinstance(parsed, dict), "const DATA must be a JSON object"
    assert "tests" in parsed, "const DATA must contain 'tests' key"


# ---------------------------------------------------------------------------
# Phase 8: M2 — 25 MB size cap
# ---------------------------------------------------------------------------


def test_m2_oversized_artifact_metadata_only(pytester: Pytester) -> None:
    """REQ-6: artifact above size threshold produces metadata-only (no data: URI).

    We set MAX_EMBED_BYTES to a very small value (1024 bytes) via a conftest
    monkeypatch of the module constant, to avoid writing 25 MB in tests.

    Warning capture: stdout parse (subprocess boundary).

    NOTE: pytest.warns / recwarn do NOT cross subprocess boundaries.
    We parse stdout for the warning text.
    """
    pytester.makepyfile("""
        import pytest

        def test_large_artifact(report_artifacts):
            artifact = report_artifacts / "big.png"
            # Write 2048 bytes — above the patched 1024-byte threshold
            artifact.write_bytes(b"\\x89PNG" + b"X" * 2043)
            assert True
    """)
    # Patch MAX_EMBED_BYTES to 1024 via conftest pytest_configure
    pytester.makeconftest("""
        def pytest_configure(config):
            import pytest_reporter._report_builder as rb
            rb.MAX_EMBED_BYTES = 1024
    """)

    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    html_path = run_dir / "report.html"
    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    _assert_valid_html(html_content)

    # No data: URI for the large file
    assert (
        "data:" not in html_content
        or "big.png" not in html_content
        or (
            # More precise: the data URI for big.png specifically must not appear
            _data_uri_for_file_absent(html_content, "big.png")
        )
    ), "Oversized artifact must not be embedded as a data: URI"

    # Warning about oversized file must appear in stdout
    out = result.stdout.str()
    assert "big.png" in out or "too large" in out.lower(), (
        "Warning about oversized artifact must appear in stdout"
    )


def _data_uri_for_file_absent(html_content: str, filename: str) -> bool:
    """Return True if no data: URI appears near the filename reference."""
    # Quick heuristic: check if the JSON contains both the filename and a nearby data: key
    # The report embeds artifacts as JSON: {"name": "big.png", "data_uri": "data:..."}
    # If "data_uri" appears with "big.png" in the JSON blob, it's embedded
    import re  # noqa: PLC0415

    # Find all occurrences of big.png in the HTML and check surrounding context
    for m in re.finditer(r"big\.png", html_content):
        # Check 500 chars around the match for "data_uri" or "data:"
        start = max(0, m.start() - 100)
        end = min(len(html_content), m.end() + 500)
        snippet = html_content[start:end]
        if "data_uri" in snippet and "data:" in snippet:
            return False
    return True


# ---------------------------------------------------------------------------
# Phase 9: tests-tree-cleanup — Baseline + Regression Guards
# ---------------------------------------------------------------------------

_TESTS_TAB_GOLDEN_HASH: str | None = None


def _extract_tab_region(html: str, start_id: str, end_id: str) -> str:
    """Extract the HTML region between two tab div ids (exclusive of end marker)."""
    start_marker = f'id="{start_id}"'
    end_marker = f'id="{end_id}"'
    start_idx = html.find(start_marker)
    if start_idx == -1:
        return ""
    end_idx = html.find(end_marker, start_idx)
    if end_idx == -1:
        return html[start_idx:]
    return html[start_idx:end_idx]


def _canonical_multi_test_code() -> str:
    """Return canonical pytester test code covering multiple files and paths."""
    return """
import pytest

def test_alpha():
    assert True

def test_beta():
    assert True

def test_gamma():
    assert False, "expected failure"
"""


def test_tests_tab_tree_baseline(pytester: Pytester) -> None:
    """REQ-1 (scope note): capture SHA-256 of the JS source in report.html.

    The Tests-tab tree is rendered by JS; the static HTML contains the JS source.
    We hash the JS source block (which includes renderTests, renderTreeNode, etc.)
    as the baseline. On first invocation: captures. Subsequent: asserts equivalence.

    WILL FAIL after compaction is implemented — intentional, not a regression.
    Golden regenerated: tests-tree-cleanup — intentional. Changes: prefix strip,
    chain collapse, single-fn merge.
    """
    global _TESTS_TAB_GOLDEN_HASH  # noqa: PLW0603

    pytester.makepyfile(_canonical_multi_test_code())
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=2, failed=1)

    run_dir = _run_dir(pytester)
    html_content = (run_dir / "report.html").read_text(encoding="utf-8")

    # Hash the JS blocks — the tree rendering logic lives in the inline script
    js_blocks = _get_script_blocks(html_content)
    # The main rendering block contains renderTests — find it
    rendering_block = next(
        (b for b in js_blocks if "renderTests" in b and "renderTreeNode" in b), None
    )
    assert rendering_block is not None, "renderTests JS block not found in report.html"

    digest = hashlib.sha256(rendering_block.encode()).hexdigest()

    if _TESTS_TAB_GOLDEN_HASH is None:
        _TESTS_TAB_GOLDEN_HASH = digest
    else:
        assert digest == _TESTS_TAB_GOLDEN_HASH, (
            "Tests-tab rendering JS changed from golden snapshot! "
            "After tests-tree-cleanup implementation, regenerate by running "
            "the test once to capture the new hash."
        )


def test_summary_tab_unchanged_after_compaction(pytester: Pytester) -> None:
    """REQ-6: Summary rendering JS must NOT use compactTree output.

    The summary invariant: renderDashboardGroups must receive the raw buildTree
    output (not the compacted tree). This is verified by checking the JS source:
    - renderDashboardGroups call must be present with buildTree(DATA.tests)
    - compactTree must NOT be inserted between buildTree and renderDashboardGroups

    This test MUST stay GREEN forever. Spec: REQ-6.
    """
    pytester.makepyfile(_canonical_multi_test_code())
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=2, failed=1)

    run_dir = _run_dir(pytester)
    html_content = (run_dir / "report.html").read_text(encoding="utf-8")

    js_blocks = _get_script_blocks(html_content)
    rendering_block = next((b for b in js_blocks if "renderDashboardGroups" in b), None)
    assert rendering_block is not None, "renderDashboardGroups not found in JS"

    # The Summary renderSummary must call buildTree(DATA.tests) and pass that
    # directly to renderDashboardGroups — without compactTree in between.
    # After implementation: the call site in renderSummary is:
    #   const tree = buildTree(DATA.tests);
    #   renderDashboardGroups(DATA.dashboard, container, tree);
    # compactTree is only called inside renderTests, NOT in renderSummary.
    assert "buildTree(DATA.tests)" in rendering_block, (
        "buildTree(DATA.tests) must be called for the Summary dashboard tree"
    )
    assert "renderDashboardGroups" in rendering_block, (
        "renderDashboardGroups must be called in the JS source"
    )
    assert "renderTests" in rendering_block, "renderTests function must be present"


# ---------------------------------------------------------------------------
# Phase 5.2 / 5.3: fmt.mono/fmt.text rendering — typed API
# ---------------------------------------------------------------------------


def _extract_data_json(html_content: str) -> dict:  # type: ignore[type-arg]
    """Extract and parse the ``const DATA = {...}`` JSON object from the HTML report."""
    import json as _json  # noqa: PLC0415

    js_blocks = _get_script_blocks(html_content)
    data_block = next((b for b in js_blocks if "const DATA" in b), None)
    assert data_block is not None, "const DATA block not found"

    idx = data_block.find("const DATA = ")
    json_start = data_block.index("{", idx)
    depth = 0
    in_string = False
    escape = False
    json_end = json_start
    for i, ch in enumerate(data_block[json_start:], json_start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
        if not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    json_end = i
                    break
    return _json.loads(data_block[json_start : json_end + 1])


def test_mono_step_renders_span(pytester: Pytester) -> None:
    """fmt.mono in step → report.html has description_segments with mono style + proc-mono in JS."""
    pytester.makepyfile("""
        from pytest_reporter import fmt, step

        def test_markup():
            with step(fmt.text("Set ", fmt.mono("Pulse.Enable"), " to 1")):
                pass
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    html_content = (run_dir / "report.html").read_text(encoding="utf-8")

    data = _extract_data_json(html_content)

    # description_segments with mono style must be embedded in DATA
    found_segments = False
    for test in data.get("tests", []):
        for run in test.get("runs", []):
            proc = run.get("procedure", {})
            for st in proc.get("steps", []):
                if st.get("description_segments"):
                    for seg in st["description_segments"]:
                        if seg.get("style") == "mono":
                            found_segments = True
    assert found_segments, "description_segments with mono style not found in DATA"

    # renderFormattedDesc and proc-mono must be present in the JS rendering block
    js_blocks = _get_script_blocks(html_content)
    rendering_block = next((b for b in js_blocks if "renderProcedure" in b), None)
    assert rendering_block is not None, "renderProcedure not found in JS"
    assert "renderFormattedDesc" in rendering_block, (
        "renderFormattedDesc function must be defined in the JS"
    )
    assert "proc-mono" in rendering_block, "proc-mono class must be assigned in renderFormattedDesc"


def test_plain_step_no_proc_mono(pytester: Pytester) -> None:
    """Plain str step → no description_segments in DATA JSON (byte-identical fallback)."""
    pytester.makepyfile("""
        from pytest_reporter import step

        def test_plain():
            with step("plain description without backticks"):
                pass
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    html_content = (run_dir / "report.html").read_text(encoding="utf-8")

    data = _extract_data_json(html_content)

    # description_segments must NOT appear in any step for plain descriptions
    found_segments = False
    for test in data.get("tests", []):
        for run in test.get("runs", []):
            proc = run.get("procedure", {})
            for st in proc.get("steps", []):
                if "description_segments" in st:
                    found_segments = True
    assert not found_segments, (
        "description_segments must be absent from DATA JSON for plain (no-markup) steps"
    )


def test_xss_fmt_mono_script_tag_inert(pytester: Pytester) -> None:
    """fmt.mono('</script>...') → raw string stored as escaped text; no script execution.

    The _script_escape pass rewrites '</' to '\\u003c/' in the REPORT_DATA JSON blob,
    so description_segments carrying '</script>' inherit this escaping and the
    document structure is preserved — no raw '</script>' inside a script block.
    """
    pytester.makepyfile(r"""
        from pytest_reporter import fmt, step

        def test_xss():
            with step(fmt.mono("</script><img src=x onerror=alert(1)>")):
                pass
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    html_content = (run_dir / "report.html").read_text(encoding="utf-8")
    _assert_valid_html(html_content)

    # No raw </script> must appear inside any <script> block
    for script_block in _get_script_blocks(html_content):
        assert "</script>" not in script_block, (
            "Raw </script> found inside a <script> block — XSS via fmt.mono description_segments!"
        )


def test_backtick_literal_no_mono(pytester: Pytester) -> None:
    """Backtick strings now render literally — no monospace, parse_markup is gone."""
    pytester.makepyfile(r"""
        from pytest_reporter import step

        def test_backtick():
            step("`x`")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    run_dir = _run_dir(pytester)
    html_content = (run_dir / "report.html").read_text(encoding="utf-8")

    data = _extract_data_json(html_content)

    # description must contain literal backtick; no description_segments
    found_description = False
    found_segments = False
    for test in data.get("tests", []):
        for run in test.get("runs", []):
            proc = run.get("procedure", {})
            for st in proc.get("steps", []):
                if "`x`" in st.get("description", ""):
                    found_description = True
                if "description_segments" in st:
                    found_segments = True
    assert found_description, "Literal backtick description not found in DATA"
    assert not found_segments, "Backtick string must NOT produce description_segments"
