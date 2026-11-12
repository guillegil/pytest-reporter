"""Run retention: delete old run folders under ``<report-dir>/runs/``.

Two ini settings (``[tool.pytest.ini_options]`` in pyproject.toml), both off by
default; a run is deleted when either rule says so:

- ``report_keep_runs = N`` keeps the N most recent runs (this run included).
- ``report_max_age_days = D`` deletes runs that started more than D days ago.

Only folders whose name is a run timestamp (``YYYY_MM_DD_HH_MM_SS``) are
considered, so anything else a user keeps in ``runs/`` is left alone, and the
current run is never deleted.
"""

from __future__ import annotations

import re
import shutil
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import Config

KEEP_RUNS = "report_keep_runs"
MAX_AGE_DAYS = "report_max_age_days"

# pytest 8.4 added the int and float ini types.
NUMERIC_INI = pytest.version_tuple[:2] >= (8, 4)

_TIMESTAMP = re.compile(r"\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}")
_FORMAT = "%Y_%m_%d_%H_%M_%S"


@dataclass(frozen=True)
class RetentionPolicy:
    """What to keep; ``None`` turns a rule off."""

    keep_runs: int | None = None
    max_age_days: float | None = None

    @property
    def enabled(self) -> bool:
        return self.keep_runs is not None or self.max_age_days is not None


def _read(config: Config, name: str, kind: str) -> str:
    try:
        value = config.getini(name)
    except (ValueError, TypeError, pytest.UsageError) as exc:
        # An ini value pytest cannot convert: a UsageError on pytest 9.2+,
        # ValueError/TypeError before. Name the setting in our own words.
        raise pytest.UsageError(f"{name} must be {kind}: {exc}") from None
    if value is None or isinstance(value, bool):
        return "" if value is None else repr(value)
    return str(value).strip()


def read_policy(config: Config) -> RetentionPolicy:
    """Read and validate the retention ini settings.

    Args:
        config: The pytest config.

    Returns:
        The policy; an empty value or ``0`` turns a rule off.

    Raises:
        pytest.UsageError: A value is not a number, or is negative.
    """
    keep_text = _read(config, KEEP_RUNS, "a whole number of runs")
    keep: int | None = None
    if keep_text:
        try:
            keep = int(keep_text)
        except ValueError:
            raise pytest.UsageError(
                f"{KEEP_RUNS} must be a whole number of runs: {keep_text!r}"
            ) from None
        if keep < 0:
            raise pytest.UsageError(f"{KEEP_RUNS} must be 0 (off) or more: {keep}")
    age_text = _read(config, MAX_AGE_DAYS, "a number of days")
    age: float | None = None
    if age_text:
        try:
            age = float(age_text)
        except ValueError:
            raise pytest.UsageError(
                f"{MAX_AGE_DAYS} must be a number of days: {age_text!r}"
            ) from None
        if not age >= 0:  # also rejects NaN
            raise pytest.UsageError(f"{MAX_AGE_DAYS} must be 0 (off) or more: {age_text}")
    return RetentionPolicy(keep_runs=keep or None, max_age_days=age or None)


def _started(path: Path) -> datetime | None:
    if not path.is_dir() or path.is_symlink() or not _TIMESTAMP.fullmatch(path.name):
        return None
    try:
        return datetime.strptime(path.name, _FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def runs_to_delete(
    runs_dir: Path,
    current: Path,
    policy: RetentionPolicy,
    *,
    now: datetime | None = None,
) -> list[Path]:
    """Return the run folders the policy deletes, oldest first.

    Args:
        runs_dir: The ``runs/`` folder.
        current: This run's folder, which is never deleted.
        policy: The retention rules.
        now: The time ages are measured from (default: now, UTC).

    Returns:
        Run folders to delete; empty when the policy is off.
    """
    if not policy.enabled or not runs_dir.is_dir():
        return []
    runs: list[tuple[datetime, Path]] = []
    for path in runs_dir.iterdir():
        started = _started(path)
        if started is not None:
            runs.append((started, path))
    runs.sort(key=lambda run: run[0], reverse=True)  # newest first
    now = now or datetime.now(UTC)
    doomed: list[Path] = []
    for index, (started, path) in enumerate(runs):
        if path.name == current.name:
            continue
        too_many = policy.keep_runs is not None and index >= policy.keep_runs
        too_old = policy.max_age_days is not None and now - started > timedelta(
            days=policy.max_age_days
        )
        if too_many or too_old:
            doomed.append(path)
    doomed.reverse()
    return doomed


def prune_runs(runs_dir: Path, current: Path, policy: RetentionPolicy) -> list[Path]:
    """Delete the run folders the policy rules out.

    A folder that cannot be deleted gives a warning and is skipped.

    Returns:
        The folders deleted.
    """
    deleted: list[Path] = []
    for path in runs_to_delete(runs_dir, current, policy):
        try:
            shutil.rmtree(path)
        except OSError as exc:
            warnings.warn(
                f"pytest-reporter: could not delete old run {path.name}: {exc}",
                stacklevel=2,
            )
        else:
            deleted.append(path)
    return deleted
