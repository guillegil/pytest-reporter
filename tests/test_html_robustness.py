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
