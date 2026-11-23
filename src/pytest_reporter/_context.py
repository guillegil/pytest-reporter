"""RunContext — manages timestamps, paths, and directory creation for a run."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

# Characters that are illegal in file/directory names on Windows (and best
# avoided everywhere). Test node IDs routinely contain ':' via the '::'
# class/function separator, which raises WinError 123 when used as a path.
_ILLEGAL_PATH_CHARS = '<>:"/\\|?*'
_SANITIZE_TABLE = {ord(ch): "_" for ch in _ILLEGAL_PATH_CHARS} | {code: "_" for code in range(32)}


def sanitize_path_component(name: str) -> str:
    """Return a filesystem-safe version of a single path segment.

    Maps every Windows-reserved character and ASCII control character to an
    underscore so that node-id-derived directory and file names (e.g.
    ``TestFoo::test_bar`` from class-based tests) are valid on all platforms.

    Args:
        name: A single path segment (not a full path — separators are escaped).

    Returns:
        The segment with illegal characters replaced by ``_``.
    """
    return name.translate(_SANITIZE_TABLE)


class RunContext:
    """Encapsulates all path calculations for a single test run."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir.resolve()
        self._timestamp = datetime.now(UTC).strftime("%Y_%m_%d_%H_%M_%S")
        self._run_dir = self._base_dir / "runs" / self._timestamp
        self._tests_dir = self._run_dir / "tests"
        # (file_path, function_name) -> test function folder: every phase, log
        # line and finish file of a test asks for it, so it is built once.
        self._function_dirs: dict[tuple[str, str], Path] = {}

    @property
    def reports_dir(self) -> Path:
        return self._base_dir

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    @property
    def failures_dir(self) -> Path:
        return self.run_dir / "failures"

    @property
    def tests_dir(self) -> Path:
        return self._tests_dir

    @property
    def timestamp(self) -> str:
        return self._timestamp

    def test_function_dir(self, file_path: str, function_name: str) -> Path:
        """Return path: run_dir/tests/<module>/<test_file>.py/<function>/.

        Each path segment is sanitized so node-id-derived names (notably the
        ``::`` separator in class-based tests) cannot produce paths that are
        invalid on Windows.
        """
        key = (file_path, function_name)
        path = self._function_dirs.get(key)
        if path is None:
            segments = [sanitize_path_component(s) for s in file_path.split("/") if s]
            path = self._tests_dir.joinpath(*segments, sanitize_path_component(function_name))
            self._function_dirs[key] = path
        return path

    def run_subdir(self, file_path: str, function_name: str, run_id: str) -> Path:
        """Return path: test_function_dir/<run_id>/."""
        return self.test_function_dir(file_path, function_name) / run_id

    def ensure_dirs(self) -> None:
        """Create the top-level directory structure for this run."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.failures_dir.mkdir(exist_ok=True)
        self.tests_dir.mkdir(exist_ok=True)
