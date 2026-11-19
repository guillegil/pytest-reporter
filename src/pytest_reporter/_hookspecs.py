"""Hookspec declarations for the pytest-reporter plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from ._bench import BenchInfo
    from ._tabs import ReportTabs
    from ._types import DashboardGroupSpec


class ReporterSpec:
    """Hookspecs defined by pytest-reporter for external contribution."""

    @pytest.hookspec(firstresult=False)
    def pytest_reporter_test_tabs(self, item: pytest.Item, tabs: ReportTabs) -> None:
        """Add custom HTML tabs to a test's detail in the HTML report.

        Called once per test attempt (retries included) with ``--report-dir``,
        when the test body has ended and before its fixtures are torn down, so
        ``item.funcargs`` still holds live fixture values. Each tab added with
        ``tabs.add(title, html)`` is shown after the report's own tabs. Each
        implementation is called on its own: an exception raised in one
        (``pytest.skip()`` and ``pytest.fail()`` included) becomes a warning,
        costs only its own tabs and never changes the test's outcome. Not
        called in pytest-xdist workers, where the reporter is not active.

        Example (conftest.py)::

            def pytest_reporter_test_tabs(item, tabs):
                bench = item.funcargs.get("bench")
                if bench is not None:
                    tabs.add("Bench log", bench.log_html())

        Args:
            item: The test.
            tabs: The attempt's tabs: see :class:`pytest_reporter.ReportTabs`.
        """

    @pytest.hookspec(firstresult=False)
    def pytest_reporter_bench(self, config: pytest.Config, bench: BenchInfo) -> None:
        """Record what is on the bench: devices, instruments, other facts.

        Called once, at session start, with ``--report-dir``. It runs on the
        pytest-xdist controller, where fixtures cannot reach the report, so it
        is the way to record the bench in a distributed run. Each
        implementation is called on its own: an exception raised in one
        becomes a warning (with warnings as errors, a line of the terminal
        summary) and costs only what it had not recorded yet. Only
        the plugins and conftest files loaded by then are asked (the ones
        pytest loads at startup, not a conftest of a folder collected later).

        The ``report_bench`` fixture gives the same object to fixtures and
        tests.

        Example (conftest.py)::

            def pytest_reporter_bench(config, bench):
                bench.device("DUT", serial="SN-0042", firmware="2.3.1")
                bench.instrument("DMM", idn=DMM_IDN, cal_due="2027-03-02")
                bench.set("Site", "Lab 2")

        Args:
            config: The pytest config.
            bench: The session's :class:`pytest_reporter.BenchInfo`.
        """

    @pytest.hookspec(firstresult=True)
    def pytest_reporter_seed(self) -> int | str | None:
        """Return the active RNG seed for this test session.

        The first non-None return value from any registered implementation wins
        (``firstresult=True``).  The ``report_seed`` fixture overrides all hook
        contributions: setting ``report_seed["value"]`` bypasses the hook entirely.

        Return ``None`` to pass control to the next registered implementation.
        When all implementations return ``None``, the seed of the
        pytest-strategies rows that ran is shown, and ``\"Not Provided\"``
        when no strategy row ran.

        Example (conftest.py)::

            def pytest_reporter_seed():
                return 12345

        Returns:
            An int or str seed value, or ``None`` to pass control downstream.
        """
        ...

    @pytest.hookspec(firstresult=False)
    def pytest_reporter_metadata(self) -> dict[str, dict[str, object]]:  # type: ignore[empty-body]
        """Return session-level metadata sections for the HTML Report tab.

        Return a mapping of section name to a dict of ``{label: value}`` pairs.
        Multiple implementations are collected (``firstresult=False``); on label
        collision within the same section the last registered implementation wins.
        The ``report_metadata`` fixture overrides all hook contributions on
        collision.  Return ``{}`` to contribute nothing.

        Example::

            def pytest_reporter_metadata():
                return {
                    "DUT": {"Serial": "SN-001", "Firmware": "2.3.1"},
                    "CI": {"Build": "42", "Branch": "main"},
                }

        Returns:
            A dict mapping section names to ``{label: value}`` dicts.
            Values are stringified via ``str()`` before embedding in the report.
        """
        ...

    @pytest.hookspec(firstresult=False)
    def pytest_reporter_dashboard(
        self,
    ) -> list[DashboardGroupSpec] | None:
        """Return a list of dashboard group specs for the Summary tab.

        Multiple implementations are collected (``firstresult=False``); results
        are concatenated in hook-registration order.  The ``report_dashboard``
        fixture list is appended last (fixture wins by being most-specific).

        Each entry is a :class:`~pytest_reporter._types.DashboardGroupSpec` dict
        with ``path`` (required) and optional ``depth``, ``include_self``,
        ``label``, and ``style`` fields.  Invalid entries are silently skipped
        with a ``UserWarning``; the reporter never crashes on bad input.

        Return ``[]`` or ``None`` to contribute nothing from this hookimpl.

        Example::

            def pytest_reporter_dashboard():
                return [
                    {"path": "tests/ctec", "depth": 1, "label": "CTEC Suite"},
                    {"path": "tests/integration", "depth": 2, "style": "bars"},
                ]

        Returns:
            A list of ``DashboardGroupSpec`` dicts, or ``None`` / ``[]`` to
            contribute nothing.
        """
        ...
