"""Hookspec declarations for the pytest-reporter plugin."""

from __future__ import annotations

import pytest


class ReporterSpec:
    """Hookspecs defined by pytest-reporter for external contribution."""

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
