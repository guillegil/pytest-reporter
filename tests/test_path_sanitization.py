"""Tests for filesystem-safe path components derived from node IDs."""

from __future__ import annotations

from pathlib import Path

from pytest_reporter._context import RunContext, sanitize_path_component


def test_sanitize_replaces_double_colon() -> None:
    """Class-based node IDs contain '::' which is illegal on Windows."""
    assert sanitize_path_component("TestFoo::test_bar") == "TestFoo__test_bar"


def test_sanitize_replaces_windows_illegal_chars() -> None:
    """All Windows-reserved path characters map to underscore."""
    assert sanitize_path_component('a<b>c:d"e|f?g*h') == "a_b_c_d_e_f_g_h"


def test_sanitize_leaves_normal_names_untouched() -> None:
    assert sanitize_path_component("test_fox_width") == "test_fox_width"


def test_test_function_dir_sanitizes_class_nodeid(tmp_path: Path) -> None:
    ctx = RunContext(tmp_path)
    d = ctx.test_function_dir("tests/ctec/test_fox.py", "TestFoxWidthIm::test_fox_width")
    assert "::" not in str(d)
    assert d.name == "TestFoxWidthIm__test_fox_width"


def test_run_subdir_is_creatable_for_class_test(tmp_path: Path) -> None:
    """The sanitized run directory must be creatable (raised WinError 123 before)."""
    ctx = RunContext(tmp_path)
    d = ctx.run_subdir("tests/ctec/test_fox.py", "TestFoxWidthIm::test_fox_width", "01")
    d.mkdir(parents=True)
    assert d.exists()
