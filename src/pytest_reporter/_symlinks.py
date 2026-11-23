"""Latest-copy management: keep ``01_latest/`` as a hard copy of the most recent run."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _link_or_copy(src: str, dst: str) -> None:
    """Hard-link ``dst`` to ``src``, or copy it where links are not possible.

    A finished run's files are never written again, so a link gives the same
    files as a copy without reading and writing every byte of the run again.
    File systems without hard links, or ``01_latest`` on another device, get
    a copy.
    """
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


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

    # Copy the entire run directory (preserves nested structure); files are
    # hard links where the file system allows them.
    shutil.copytree(run_dir, latest, symlinks=False, copy_function=_link_or_copy)
