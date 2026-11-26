"""pytest-reporter: A pytest plugin for generating custom test reports.

Logs are the standard Python ``logging`` records of each test phase. Test
procedures come from stepdoc (``from stepdoc import step``), verification
cards from pytest-verifier and strategy rows from pytest-strategies. All three
are optional: the reporter reads what they publish and never imports them.
"""

from __future__ import annotations

from ._tabs import ReportTabs

__all__ = [
    "ReportTabs",
]

# Names removed in 0.3.0, with where they went.
_MOVED = {
    "step": "step() moved to stepdoc: `pip install stepdoc`, then `from stepdoc import step`",
    "substep": (
        "substep() was removed: nest `with step(...)` blocks from stepdoc "
        "(`from stepdoc import step`)"
    ),
    "fmt": "fmt was removed with step(); stepdoc step titles are plain strings",
    "FormattedText": "FormattedText was removed with step(); stepdoc step titles are plain strings",
    "ProcedureError": "ProcedureError was removed with step(); see stepdoc",
    "ProcedureNestingError": "ProcedureNestingError was removed with step(); see stepdoc",
}

# Names removed in 0.4.0: the report shows Python logging records instead.
_LOGGING = (
    "the reporter's logger was removed: log with `logging.getLogger(__name__)` "
    "and the records appear in the report (pytest-reporter 0.4.0)"
)
_REMOVED_04 = {"Logger": _LOGGING, "ReportLogger": _LOGGING}


def __getattr__(name: str) -> object:
    if name in _REMOVED_04:
        raise ImportError(f"pytest_reporter.{name}: {_REMOVED_04[name]}")
    if name in _MOVED:
        raise ImportError(f"pytest_reporter.{name}: {_MOVED[name]} (pytest-reporter 0.3.0)")
    raise AttributeError(f"module 'pytest_reporter' has no attribute {name!r}")
