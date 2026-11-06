"""pytest-reporter: A pytest plugin for generating custom test reports.

Test procedures come from stepdoc (``from stepdoc import step``), verification
cards from pytest-verifier and strategy rows from pytest-strategies. All three
are optional: the reporter reads what they publish and never imports them.
"""

from __future__ import annotations

from ._logger import Logger, ReportLogger

__all__ = [
    "Logger",
    "ReportLogger",
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


def __getattr__(name: str) -> object:
    if name in _MOVED:
        raise ImportError(f"pytest_reporter.{name}: {_MOVED[name]} (pytest-reporter 0.3.0)")
    raise AttributeError(f"module 'pytest_reporter' has no attribute {name!r}")
