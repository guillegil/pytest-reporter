"""01_latest/ holds the most recent run's files: hard links where possible, else copies."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pytest_reporter._symlinks import update_latest_copy


def _run(tmp_path: Path) -> Path:
    run = tmp_path / "runs" / "2026_01_01_00_00_00"
    (run / "tests" / "t" / "default").mkdir(parents=True)
    (run / "report.html").write_text("<html></html>", encoding="utf-8")
    (run / "tests" / "t" / "default" / "call.log.json").write_text("{}", encoding="utf-8")
    return run


def test_latest_files_are_hard_links(tmp_path: Path) -> None:
    run = _run(tmp_path)
    update_latest_copy(tmp_path, run)
    latest = tmp_path / "01_latest"
    for rel in ("report.html", "tests/t/default/call.log.json"):
        assert (latest / rel).read_text(encoding="utf-8") == (run / rel).read_text(encoding="utf-8")
        assert os.path.samefile(latest / rel, run / rel)


def test_latest_falls_back_to_copies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_links(src: str, dst: str) -> None:
        raise OSError("hard links not supported")

    monkeypatch.setattr(os, "link", no_links)
    run = _run(tmp_path)
    update_latest_copy(tmp_path, run)
    copied = tmp_path / "01_latest" / "report.html"
    assert copied.read_text(encoding="utf-8") == "<html></html>"
    assert not os.path.samefile(copied, run / "report.html")


def test_latest_replaces_previous_run(tmp_path: Path) -> None:
    first = _run(tmp_path)
    update_latest_copy(tmp_path, first)
    second = tmp_path / "runs" / "2026_01_02_00_00_00"
    second.mkdir(parents=True)
    (second / "report.html").write_text("second", encoding="utf-8")
    update_latest_copy(tmp_path, second)
    latest = tmp_path / "01_latest"
    assert (latest / "report.html").read_text(encoding="utf-8") == "second"
    assert not (latest / "tests").exists()
    # The earlier run keeps its own files.
    assert (first / "report.html").read_text(encoding="utf-8") == "<html></html>"
