"""Integration tests for pytest-reporter's interaction with pytest-verify.

Covers:
- Scenario 5: clean run when verify absent (get_check_results monkeypatched to None)
- Scenario 6: verification cards rendered when verify present
- Scenario 7: private stash import removed (static source check)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import MonkeyPatch, Pytester


def test_reporter_runs_cleanly_when_verify_absent(
    pytester: Pytester, monkeypatch: MonkeyPatch
) -> None:
    """Scenario 5: reporter produces all outputs even when get_check_results is None.

    Simulates verify being absent by patching get_check_results to None at the
    module level in reporter.  The run must complete without exception and all
    expected outputs must be present.
    """
    import pytest_reporter.reporter as reporter_mod

    monkeypatch.setattr(reporter_mod, "get_check_results", None)

    pytester.makepyfile("""
        def test_simple_pass():
            assert True

        def test_simple_fail():
            assert False
    """)
    result = pytester.runpytest("--report-dir=reports")
    # One pass, one fail — must NOT crash due to missing verify
    result.assert_outcomes(passed=1, failed=1)

    reports_dir = pytester.path / "reports"
    assert reports_dir.exists(), "reports/ dir must be created"

    runs = list((reports_dir / "runs").iterdir())
    assert len(runs) == 1
    run_dir = runs[0]

    assert (run_dir / "report.html").exists(), "report.html must be produced"
    assert (run_dir / "junit.xml").exists(), "junit.xml must be produced"
    assert (run_dir / "session.log.json").exists(), "session.log.json must be produced"
    assert (reports_dir / "01_latest").is_dir(), "01_latest hard copy must exist"


def test_verification_cards_rendered_when_verify_present(pytester: Pytester) -> None:
    """Scenario 6: reporter renders verification card data when verify is installed.

    Uses the real pytest-verify (already installed in the venv) and confirms
    the check_results field in the HTML data is non-empty.
    """
    pytester.makepyfile("""
        def test_with_verify(verify):
            verify.equal(1, 1, name="Passes")
            verify.equal(1, 2, name="Fails")
    """)
    result = pytester.runpytest("--report-dir=reports")
    # test fails because verify has a failing check
    result.assert_outcomes(failed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    assert runs, "run directory must exist"
    run_dir = runs[0]

    html_path = run_dir / "report.html"
    assert html_path.exists(), "report.html must exist"
    html_content = html_path.read_text(encoding="utf-8")

    # The HTML embeds JSON data. Verification checks should appear in check_results.
    # The key "check_results" must exist with non-empty data for this test.
    assert '"check_results"' in html_content, "HTML report must contain check_results key"
    # Ensure check results have at least one entry (not just an empty list "[]")
    # We look for check-type-specific content
    assert '"check_type"' in html_content, (
        "HTML report must contain check_type data from verification checks"
    )


def test_private_stash_import_removed() -> None:
    """Scenario 7: reporter.py must NOT import from pytest_verify._stash.

    Static source inspection — no test environment needed.
    """
    reporter_source = Path(__file__).parent.parent / "src" / "pytest_reporter" / "reporter.py"
    assert reporter_source.exists(), f"reporter.py not found at {reporter_source}"

    source_text = reporter_source.read_text(encoding="utf-8")

    assert "pytest_verify._stash" not in source_text, (
        "reporter.py must NOT import from pytest_verify._stash"
    )
    assert "from pytest_verify import get_check_results" in source_text, (
        "reporter.py must import get_check_results from pytest_verify (inside ImportError guard)"
    )
