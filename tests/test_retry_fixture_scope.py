"""Retries must NOT recycle higher-scoped fixtures (session/module).

Before the fix, each retry ran ``runtestprotocol(item, nextitem=None)``, and
``nextitem=None`` told pytest to tear down everything — including session- and
module-scoped fixtures. A backend they own (threads, processes, instrument
connections) was killed and relaunched between every attempt. The fix runs
retries with ``nextitem=item`` (keep shared fixtures alive) and performs one
final ``teardown_exact(real_nextitem)`` after the loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Pytester


def test_session_fixture_not_recycled_across_retries(pytester: Pytester) -> None:
    pytester.makeconftest("""
        import pathlib
        import pytest

        _MARK = pathlib.Path(__file__).parent / "backend_setups.log"

        @pytest.fixture(scope="session")
        def backend():
            with _MARK.open("a") as f:
                f.write("setup\\n")
            yield {"conn": 1}
    """)
    # A trailing test keeps `backend` in scope, so the failing test is not the
    # last item (the realistic case: failures are mid-suite, not the final test).
    pytester.makepyfile("""
        def test_flaky(backend):
            assert False, "boom"

        def test_tail(backend):
            assert True
    """)
    pytester.runpytest("--report-dir=reports", "--report-retries=3")

    marker = pytester.path / "backend_setups.log"
    setups = marker.read_text().count("setup") if marker.exists() else 0
    assert setups == 1, (
        f"session-scoped backend must be set up exactly once across retries, "
        f"got {setups} setups (it is being recycled between attempts)"
    )


def test_next_test_runs_cleanly_after_a_retried_test(pytester: Pytester) -> None:
    """The final fixture-teardown transition must leave the next test runnable."""
    pytester.makeconftest("""
        import pytest

        @pytest.fixture(scope="session")
        def backend():
            yield {"conn": 1}

        @pytest.fixture
        def per_test():
            yield object()
    """)
    pytester.makepyfile("""
        def test_flaky(backend, per_test):
            assert False

        def test_after(backend, per_test):
            assert per_test is not None
    """)
    result = pytester.runpytest("--report-dir=reports", "--report-retries=2")
    # test_flaky fails after retries; test_after must still PASS (not error).
    result.assert_outcomes(failed=1, passed=1)
