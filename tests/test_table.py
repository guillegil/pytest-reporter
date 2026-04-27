"""Tests for the log.table() feature."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from pytest_reporter._table import (
    INLINE_ROW_LIMIT,
    SERIALIZED_ROW_LIMIT,
    normalize_table,
    sanitize_filename,
)

if TYPE_CHECKING:
    from pytest import Pytester


# ---------------------------------------------------------------------------
# Unit tests for normalize_table
# ---------------------------------------------------------------------------


class TestNormalizeTable:
    def test_list_of_dicts(self) -> None:
        data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        cols, rows = normalize_table(data)
        assert cols == ["a", "b"]
        assert rows == [["1", "2"], ["3", "4"]]

    def test_dict_of_lists(self) -> None:
        data = {"x": [10, 20], "y": [30, 40]}
        cols, rows = normalize_table(data)
        assert cols == ["x", "y"]
        assert rows == [["10", "30"], ["20", "40"]]

    def test_dataframe_duck_typed(self) -> None:
        """Duck-typed object with .columns and .values works."""

        class FakeDF:
            columns = ["col1", "col2"]
            values = [[1, "hello"], [2, "world"]]

        cols, rows = normalize_table(FakeDF())
        assert cols == ["col1", "col2"]
        assert rows == [["1", "hello"], ["2", "world"]]

    def test_empty_list(self) -> None:
        cols, rows = normalize_table([])
        assert cols == []
        assert rows == []

    def test_none_and_nan_cells(self) -> None:
        data = [{"a": None, "b": float("nan")}, {"a": float("inf"), "b": 3.14}]
        cols, rows = normalize_table(data)
        assert rows[0] == ["", "NaN"]
        assert rows[1] == ["Inf", "3.14"]

    def test_mismatched_keys(self) -> None:
        data = [{"a": 1}, {"a": 2, "b": 3}]
        cols, rows = normalize_table(data)
        assert "a" in cols
        assert "b" in cols
        assert rows[0][cols.index("b")] == ""  # missing key → empty

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError, match="Cannot normalize"):
            normalize_table("not a table")

    def test_dict_of_uneven_lists(self) -> None:
        data = {"x": [1, 2, 3], "y": [4, 5]}
        cols, rows = normalize_table(data)
        assert len(rows) == 3
        assert rows[2] == ["3", ""]


class TestSanitizeFilename:
    def test_simple_name(self) -> None:
        assert sanitize_filename("my_table") == "my_table"

    def test_special_chars(self) -> None:
        assert sanitize_filename("My Table (v2)!") == "my_table__v2"

    def test_empty_fallback(self) -> None:
        assert sanitize_filename("!!!") == "table"


# ---------------------------------------------------------------------------
# Integration tests via pytester
# ---------------------------------------------------------------------------


def test_table_from_list_of_dicts(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_log_table(log):
            data = [{"ch": 1, "voltage": 3.3}, {"ch": 2, "voltage": 5.0}]
            log.table(data, name="readings")
            log.info("Done")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    call_log = (
        runs[0]
        / "tests"
        / "test_table_from_list_of_dicts.py"
        / "test_log_table"
        / "default"
        / "call.log.json"
    )
    data = json.loads(call_log.read_text())
    entries = data["entries"]

    # First entry is the table
    table_entry = entries[0]
    assert table_entry["msg"] == "Table: readings"
    assert table_entry["data"]["_type"] == "table"
    assert table_entry["data"]["name"] == "readings"
    assert table_entry["data"]["columns"] == ["ch", "voltage"]
    assert len(table_entry["data"]["rows"]) == 2
    assert table_entry["data"]["total_rows"] == 2
    assert table_entry["data"]["truncated"] is False
    assert table_entry["data"]["artifact_name"] == "readings.html"

    # Second entry is the regular log
    assert entries[1]["msg"] == "Done"


def test_table_from_dict_of_lists(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_dict_table(log):
            log.table({"x": [1, 2, 3], "y": [4, 5, 6]}, name="coords")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    call_log = (
        runs[0]
        / "tests"
        / "test_table_from_dict_of_lists.py"
        / "test_dict_table"
        / "default"
        / "call.log.json"
    )
    data = json.loads(call_log.read_text())
    entry = data["entries"][0]
    assert entry["data"]["columns"] == ["x", "y"]
    assert entry["data"]["total_rows"] == 3


def test_table_truncation(pytester: Pytester) -> None:
    pytester.makepyfile(f"""
        def test_big_table(log):
            rows = [{{"i": i, "v": i * 0.1}} for i in range({SERIALIZED_ROW_LIMIT + 50})]
            log.table(rows, name="big")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    call_log = (
        runs[0]
        / "tests"
        / "test_table_truncation.py"
        / "test_big_table"
        / "default"
        / "call.log.json"
    )
    data = json.loads(call_log.read_text())
    entry = data["entries"][0]
    assert entry["data"]["truncated"] is True
    assert entry["data"]["total_rows"] == SERIALIZED_ROW_LIMIT + 50
    assert len(entry["data"]["rows"]) == SERIALIZED_ROW_LIMIT


def test_table_artifact_written(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_artifact(log):
            log.table([{"a": 1}], name="my_artifact")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    artifact = (
        runs[0]
        / "tests"
        / "test_table_artifact_written.py"
        / "test_artifact"
        / "default"
        / "artifacts"
        / "my_artifact.html"
    )
    assert artifact.exists()
    content = artifact.read_text()
    assert "my_artifact" in content
    assert "<table>" in content
    assert "<th>" in content


def test_table_in_html_report(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_report(log):
            log.table([{"x": 42}], name="report_table")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    report_html = (runs[0] / "report.html").read_text()
    assert '"_type": "table"' in report_html or '"_type":"table"' in report_html


def test_table_name_sanitization(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_sanitize(log):
            log.table([{"a": 1}], name="My Table (v2)!")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    artifacts_dir = (
        runs[0]
        / "tests"
        / "test_table_name_sanitization.py"
        / "test_sanitize"
        / "default"
        / "artifacts"
    )
    # Should have a sanitized filename
    html_files = list(artifacts_dir.glob("*.html"))
    assert len(html_files) == 1
    assert "my_table" in html_files[0].name


def test_table_multiple_same_name(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_dedup(log):
            log.table([{"a": 1}], name="dup")
            log.table([{"b": 2}], name="dup")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    call_log = (
        runs[0]
        / "tests"
        / "test_table_multiple_same_name.py"
        / "test_dedup"
        / "default"
        / "call.log.json"
    )
    data = json.loads(call_log.read_text())
    names = [e["data"]["artifact_name"] for e in data["entries"]]
    assert names[0] == "dup.html"
    assert names[1] == "dup_2.html"

    # Both artifacts exist
    artifacts_dir = call_log.parent / "artifacts"
    assert (artifacts_dir / "dup.html").exists()
    assert (artifacts_dir / "dup_2.html").exists()


def test_table_without_report_dir(pytester: Pytester) -> None:
    """log.table() should not crash when --report-dir is not set."""
    pytester.makepyfile("""
        def test_no_dir(log):
            log.table([{"a": 1}], name="noop")
            log.info("Still works")
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_table_child_logger(pytester: Pytester) -> None:
    """Tables logged on child loggers have correct source path."""
    pytester.makepyfile("""
        def test_child_table(log):
            db = log.child("db")
            db.table([{"id": 1, "name": "Alice"}], name="users")
    """)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)

    runs = list((pytester.path / "reports" / "runs").iterdir())
    call_log = (
        runs[0]
        / "tests"
        / "test_table_child_logger.py"
        / "test_child_table"
        / "default"
        / "call.log.json"
    )
    data = json.loads(call_log.read_text())
    entry = data["entries"][0]
    assert entry["source"] == ["db"]
    assert entry["data"]["_type"] == "table"
