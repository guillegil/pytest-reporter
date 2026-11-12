"""Run retention: report_keep_runs and report_max_age_days."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pytest_reporter._retention import RetentionPolicy, runs_to_delete

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import Pytester

_FORMAT = "%Y_%m_%d_%H_%M_%S"


def _make_runs(runs_dir: Path, ages_days: list[float], now: datetime) -> list[Path]:
    paths = []
    for age in ages_days:
        path = runs_dir / (now - timedelta(days=age)).strftime(_FORMAT)
        (path / "tests").mkdir(parents=True)
        paths.append(path)
    return paths


def _ini(pytester: Pytester, **settings: str) -> None:
    lines = "\n".join(f"{k} = {v}" for k, v in settings.items())
    pytester.makeini(f"[pytest]\n{lines}\n")


def _test_file(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_pass():
            assert True
    """)


# --- runs_to_delete (unit) ----------------------------------------------------------


def test_policy_off_deletes_nothing(tmp_path: Path) -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    runs = _make_runs(tmp_path, [0, 1, 50, 400], now)
    assert runs_to_delete(tmp_path, runs[0], RetentionPolicy(), now=now) == []


def test_keep_runs_keeps_newest_including_current(tmp_path: Path) -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    runs = _make_runs(tmp_path, [0, 1, 2, 3, 4], now)
    doomed = runs_to_delete(tmp_path, runs[0], RetentionPolicy(keep_runs=2), now=now)
    assert doomed == [runs[4], runs[3], runs[2]]  # oldest first


def test_max_age_deletes_older_runs(tmp_path: Path) -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    runs = _make_runs(tmp_path, [0, 6.9, 7.1, 30], now)
    doomed = runs_to_delete(tmp_path, runs[0], RetentionPolicy(max_age_days=7), now=now)
    assert doomed == [runs[3], runs[2]]


def test_either_rule_deletes(tmp_path: Path) -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    runs = _make_runs(tmp_path, [0, 1, 2, 20], now)
    policy = RetentionPolicy(keep_runs=3, max_age_days=10)
    assert runs_to_delete(tmp_path, runs[0], policy, now=now) == [runs[3]]
    policy = RetentionPolicy(keep_runs=2, max_age_days=10)
    assert runs_to_delete(tmp_path, runs[0], policy, now=now) == [runs[3], runs[2]]


def test_current_run_is_never_deleted(tmp_path: Path) -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    runs = _make_runs(tmp_path, [0, 100, 200], now)
    # The current run is an old one (a clock that went back): still kept.
    policy = RetentionPolicy(keep_runs=1, max_age_days=1)
    assert runs_to_delete(tmp_path, runs[1], policy, now=now) == [runs[2]]


def test_only_timestamp_folders_are_considered(tmp_path: Path) -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    runs = _make_runs(tmp_path, [0, 1], now)
    (tmp_path / "keep_me").mkdir()
    (tmp_path / "2020_01_01_00_00_00.txt").write_text("not a run")
    (tmp_path / "2020_13_45_00_00_00").mkdir()  # not a real date
    doomed = runs_to_delete(tmp_path, runs[0], RetentionPolicy(keep_runs=1), now=now)
    assert doomed == [runs[1]]


def test_missing_runs_dir(tmp_path: Path) -> None:
    missing = tmp_path / "runs"
    assert runs_to_delete(missing, missing / "x", RetentionPolicy(keep_runs=1)) == []


# --- plugin (pytester) ----------------------------------------------------------------


def test_off_by_default(pytester: Pytester) -> None:
    _test_file(pytester)
    runs_dir = pytester.path / "reports" / "runs"
    old = _make_runs(runs_dir, [100, 200], datetime.now(UTC))
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)
    assert all(p.exists() for p in old)
    assert len(list(runs_dir.iterdir())) == 3
    assert "old run" not in result.stdout.str()


def test_keep_runs_from_ini(pytester: Pytester) -> None:
    _test_file(pytester)
    _ini(pytester, report_keep_runs="2")
    runs_dir = pytester.path / "reports" / "runs"
    old = _make_runs(runs_dir, [1, 2, 3], datetime.now(UTC))
    (runs_dir / "notes").mkdir()
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)
    remaining = sorted(p.name for p in runs_dir.iterdir())
    assert old[0].name in remaining
    assert not old[1].exists() and not old[2].exists()
    assert "notes" in remaining
    assert len(remaining) == 3  # this run, the newest old one, notes/
    result.stdout.fnmatch_lines(["*Deleted 2 old runs (retention rule)*"])
    assert (pytester.path / "reports" / "01_latest" / "report.html").exists()


def test_max_age_from_pyproject(pytester: Pytester) -> None:
    _test_file(pytester)
    pytester.makepyprojecttoml("""
        [tool.pytest.ini_options]
        report_max_age_days = "7"
    """)
    runs_dir = pytester.path / "reports" / "runs"
    young, old = _make_runs(runs_dir, [1, 30], datetime.now(UTC))
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)
    assert young.exists()
    assert not old.exists()
    result.stdout.fnmatch_lines(["*Deleted 1 old run (retention rule)*"])


def test_zero_means_off(pytester: Pytester) -> None:
    _test_file(pytester)
    _ini(pytester, report_keep_runs="0", report_max_age_days="0")
    runs_dir = pytester.path / "reports" / "runs"
    old = _make_runs(runs_dir, [100], datetime.now(UTC))
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    assert old[0].exists()


def test_without_report_dir_nothing_happens(pytester: Pytester) -> None:
    _test_file(pytester)
    _ini(pytester, report_keep_runs="1")
    runs_dir = pytester.path / "reports" / "runs"
    old = _make_runs(runs_dir, [1], datetime.now(UTC))
    pytester.runpytest().assert_outcomes(passed=1)
    assert old[0].exists()


def test_bad_values_are_usage_errors(pytester: Pytester) -> None:
    _test_file(pytester)
    for name, value, message in [
        ("report_keep_runs", "many", "*report_keep_runs must be a whole number*"),
        ("report_keep_runs", "-1", "*report_keep_runs must be 0 (off) or more*"),
        ("report_max_age_days", "week", "*report_max_age_days must be a number*"),
        ("report_max_age_days", "-2", "*report_max_age_days must be 0 (off) or more*"),
    ]:
        _ini(pytester, **{name: value})
        result = pytester.runpytest("--report-dir=reports")
        assert result.ret == 4, (name, value)
        result.stderr.fnmatch_lines([message])
