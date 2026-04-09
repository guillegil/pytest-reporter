"""Symlink management for latest run pointers."""

from __future__ import annotations

from pathlib import Path


def update_symlinks(reports_dir: Path, run_dir: Path) -> None:
    """Create or update 01_latest and 02_latest_failures symlinks."""
    latest = reports_dir / "01_latest"
    latest_failures = reports_dir / "02_latest_failures"

    # Use relative paths so the reports directory is portable
    rel_run = run_dir.relative_to(reports_dir)
    rel_failures = (run_dir / "failures").relative_to(reports_dir)

    for link, target in ((latest, rel_run), (latest_failures, rel_failures)):
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target)
