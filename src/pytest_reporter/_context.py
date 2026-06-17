"""RunContext — manages timestamps, paths, and directory creation for a run."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


class RunContext:
    """Encapsulates all path calculations for a single test run."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir.resolve()
        self._timestamp = datetime.now(UTC).strftime("%Y_%m_%d_%H_%M_%S")

    @property
    def reports_dir(self) -> Path:
        return self._base_dir

    @property
    def run_dir(self) -> Path:
        return self._base_dir / "runs" / self._timestamp

    @property
    def failures_dir(self) -> Path:
        return self.run_dir / "failures"

    @property
    def tests_dir(self) -> Path:
        return self.run_dir / "tests"

    @property
    def timestamp(self) -> str:
        return self._timestamp

    def test_function_dir(self, file_path: str, function_name: str) -> Path:
        """Return path: run_dir/tests/<module>/<test_file>.py/<function>/."""
        return self.tests_dir / file_path / function_name

    def run_subdir(self, file_path: str, function_name: str, run_id: str) -> Path:
        """Return path: test_function_dir/<run_id>/."""
        return self.test_function_dir(file_path, function_name) / run_id

    def ensure_dirs(self) -> None:
        """Create the top-level directory structure for this run."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.failures_dir.mkdir(exist_ok=True)
        self.tests_dir.mkdir(exist_ok=True)
