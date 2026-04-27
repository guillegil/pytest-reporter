"""Latest-copy management: keep ``01_latest/`` as a hard copy of the most recent run."""

from __future__ import annotations

import shutil
from pathlib import Path


def update_latest_copy(reports_dir: Path, run_dir: Path) -> None:
    """Replace ``reports_dir/01_latest/`` with a fresh copy of ``run_dir``.

    The previous ``01_latest`` (whether a directory, file, or symlink left over
    from older versions) is removed before the new copy is created.
    """
    latest = reports_dir / "01_latest"

    # Clean up any previous latest entry (directory, file, or stale symlink)
    if latest.is_symlink() or latest.is_file():
        latest.unlink()
    elif latest.is_dir():
        shutil.rmtree(latest)

    # Copy the entire run directory (preserves nested structure and permissions)
    shutil.copytree(run_dir, latest, symlinks=False)
