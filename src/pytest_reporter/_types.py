"""Shared type aliases and TypedDicts."""

from __future__ import annotations

from typing import Any, TypedDict


class TestResult(TypedDict):
    nodeid: str
    outcome: str
    duration: float
    longrepr: str | None
