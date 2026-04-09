"""Shared type aliases and TypedDicts for the reporter plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

# --- Log entry schema (§5.2) ---


class ExcInfo(TypedDict, total=False):
    type: str
    msg: str
    tb: str


class LogEntryDict(TypedDict, total=False):
    seq: int
    t: str
    level: str
    source: list[str]
    msg: str
    data: dict[str, Any] | None
    exc: dict[str, str] | None


# --- Phase log schema (§5.4) ---


class PhaseLog(TypedDict):
    phase: str
    outcome: str
    start_time: str
    end_time: str
    duration_seconds: float
    longrepr: str | None
    entries: list[LogEntryDict]


# --- Session log schema (§5.8.2) ---


class SessionLog(TypedDict):
    phase: str  # always "session"
    start_time: str
    end_time: str
    duration_seconds: float
    entries: list[LogEntryDict]


# --- Retries schema (§3.2) ---


class RetriesInfo(TypedDict):
    attempts: int
    original_outcome: str
    history: list[str]


# --- Run entry schema (§3.1) ---


class RunEntry(TypedDict, total=False):
    run_id: str
    outcome: str
    duration_seconds: float
    retries: RetriesInfo


# --- test.log.json schema (§3) ---


class TestLogJson(TypedDict):
    test_id: str
    function_name: str
    file: str
    total_runs: int
    passed: int
    failed: int
    skipped: int
    errors: int
    total_duration_seconds: float
    runs: list[RunEntry]


# --- parameters.json schema (§4) ---


class ParamEntry(TypedDict):
    type: str
    value: str


class ParametersJson(TypedDict):
    parametrize_id: str | None
    params: dict[str, ParamEntry]


# --- procedure.json schema (§6.7) ---


class SubstepJson(TypedDict, total=False):
    number: str
    description: str
    outcome: str
    start_time: str
    end_time: str
    duration_seconds: float
    exc: dict[str, str] | None
    check: dict[str, Any] | None


class StepJson(TypedDict, total=False):
    number: str
    description: str
    outcome: str
    start_time: str
    end_time: str
    duration_seconds: float
    exc: dict[str, str] | None
    substeps: list[SubstepJson]
    check: dict[str, Any] | None


class ProcedureJson(TypedDict):
    steps: list[StepJson]


# --- Internal data structures ---


@dataclass
class RunInfo:
    """Metadata about a single test run (one parametrize variant or default)."""

    run_id: str  # "01", "02", or "default"
    base_nodeid: str  # nodeid without [params]
    parametrize_id: str | None
    params: dict[str, Any]
    function_name: str
    file_path: str
    module_parts: list[str]
    docstring: str | None = None
    markers: list[str] = field(default_factory=list)


@dataclass
class PhaseData:
    """Collected data from one phase of a test run."""

    when: str
    outcome: str
    duration: float
    longrepr: str | None
    start_time: str = ""
    end_time: str = ""
    entries: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RetryData:
    """Tracks retry state for a single test run."""

    max_retries: int = 0
    attempts: int = 0
    original_outcome: str = ""
    history: list[str] = field(default_factory=list)
    retry_dirs: list[str] = field(default_factory=list)
