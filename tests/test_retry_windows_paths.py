"""Retry path safety on Windows: failure-log filenames must be sanitized.

A class-based test's ``function_name`` is ``TestClass::test_method`` (with
``::``). The retry path wrote the failure log using the raw name, which is a
legal filename on Linux but ILLEGAL on Windows — so on Windows the write raised
OSError, the crash-safety guard swallowed it, and the retry was silently
skipped. The non-retry path already sanitizes via ``sanitize_path_component``;
the retry path must match.

Asserting the filename is sanitized is cross-platform and runs on Linux.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def test_retry_failure_log_filename_is_sanitized(pytester: Pytester) -> None:
    pytester.makepyfile("""
        class TestThing:
            def test_method_fails(self):
                assert False, "boom"
    """)
    pytester.runpytest("--report-dir=reports", "--report-retries=2")

    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    failures_dir = runs[0] / "failures"
    assert failures_dir.is_dir(), "failures/ dir must exist for the failed test"

    names = [p.name for p in failures_dir.iterdir()]
    assert names, "a failure log must be written"
    # No filename may contain ':' — illegal on Windows, breaks the retry write.
    for name in names:
        assert ":" not in name, f"failure log name must be sanitized, got {name!r}"
    # The sanitized class::method name uses '__'
    assert any("TestThing__test_method_fails" in n for n in names), (
        f"expected sanitized 'TestThing__test_method_fails' in {names}"
    )
