"""Unit tests for _dashboard_config.normalize_dashboard.

Covers schema validation, defaults, style fallback, and merge order.
All tests are pure-function unit tests (no pytester overhead).

PRE-CHANGE BASELINE captured before any implementation:
- 'All Tests' donut present in _js.py ~L223-230
- Hardcoded depth-1 feature loop at ~L252-272
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_reporter._types import DashboardConfig


# ---------------------------------------------------------------------------
# Lazy import so the module-not-found failure is a test failure, not import error.
# Tasks 1.1–1.7: module does not exist yet — these tests must be RED initially.
# ---------------------------------------------------------------------------


def _norm(
    hook_lists: list[list[object]],
    fixture_list: list[object],
) -> DashboardConfig:
    """Import and call normalize_dashboard — deferred so missing module = RED."""
    from pytest_reporter._dashboard_config import normalize_dashboard  # noqa: PLC0415

    return normalize_dashboard(hook_lists, fixture_list)


# ---------------------------------------------------------------------------
# Task 1.1 — default (empty) config returns DashboardConfig is_default=True
# ---------------------------------------------------------------------------


def test_empty_returns_default() -> None:
    """normalize_dashboard([], []) returns DashboardConfig with groups=[], is_default=True."""
    result = _norm([], [])
    assert result["groups"] == []
    assert result["is_default"] is True


# ---------------------------------------------------------------------------
# Task 1.2 — valid single-group normalization fills all defaults
# ---------------------------------------------------------------------------


def test_valid_single_group_defaults() -> None:
    """A path-only entry fills depth=1, include_self=False, label=last segment, style='auto'."""
    result = _norm([[{"path": "ctec"}]], [])
    assert result["is_default"] is False
    assert len(result["groups"]) == 1
    g = result["groups"][0]
    assert g["path"] == ["ctec"]
    assert g["depth"] == 1
    assert g["include_self"] is False
    assert g["label"] == "ctec"
    assert g["style"] == "auto"


def test_valid_group_with_all_fields() -> None:
    """A fully specified group passes through correctly."""
    result = _norm(
        [
            [
                {
                    "path": "tests/ctec",
                    "depth": 2,
                    "include_self": True,
                    "label": "CTEC Suite",
                    "style": "donut",
                }
            ]
        ],
        [],
    )
    assert result["is_default"] is False
    g = result["groups"][0]
    assert g["path"] == ["tests", "ctec"]
    assert g["depth"] == 2
    assert g["include_self"] is True
    assert g["label"] == "CTEC Suite"
    assert g["style"] == "donut"


def test_valid_group_style_bars() -> None:
    """style='bars' passes through unchanged."""
    result = _norm([[{"path": "integration", "style": "bars"}]], [])
    g = result["groups"][0]
    assert g["style"] == "bars"


# ---------------------------------------------------------------------------
# Task 1.3 — invalid input branches emit warnings and skip/clamp
# ---------------------------------------------------------------------------


def test_non_dict_entry_skipped_with_warning() -> None:
    """A non-dict entry in the list is skipped and warns with 'dashboard'."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([["not_a_dict"]], [])
    assert result["is_default"] is True
    assert result["groups"] == []


def test_missing_path_skipped_with_warning() -> None:
    """An entry without 'path' is skipped and warns."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([[{"depth": 1}]], [])
    assert result["is_default"] is True


def test_empty_path_skipped_with_warning() -> None:
    """An entry with empty string path is skipped and warns."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([[{"path": ""}]], [])
    assert result["is_default"] is True


def test_path_not_string_skipped_with_warning() -> None:
    """An entry with non-string path is skipped and warns."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([[{"path": 123}]], [])
    assert result["is_default"] is True


def test_depth_zero_clamped_with_warning() -> None:
    """depth=0 is clamped to 1 and warns with 'dashboard'."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([[{"path": "ctec", "depth": 0}]], [])
    assert result["groups"][0]["depth"] == 1


def test_depth_negative_clamped_with_warning() -> None:
    """depth=-1 is clamped to 1 and warns."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([[{"path": "ctec", "depth": -1}]], [])
    assert result["groups"][0]["depth"] == 1


def test_depth_over_max_clamped_with_warning() -> None:
    """depth>8 is clamped to 8 and warns."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([[{"path": "ctec", "depth": 99}]], [])
    assert result["groups"][0]["depth"] == 8


def test_depth_not_int_clamped_with_warning() -> None:
    """Non-integer depth is clamped to 1 and warns."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([[{"path": "ctec", "depth": "deep"}]], [])
    assert result["groups"][0]["depth"] == 1


def test_wrong_top_level_type_warning() -> None:
    """A hook returning a non-list value at top level warns and is skipped."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([["invalid_string"]], [])
    assert result["is_default"] is True


# ---------------------------------------------------------------------------
# Task 1.4 — style field validation: valid pass through, invalid → 'auto' + warn
# ---------------------------------------------------------------------------


def test_style_bars_passes_through() -> None:
    """style='bars' is valid and passes through unchanged."""
    result = _norm([[{"path": "ctec", "style": "bars"}]], [])
    assert result["groups"][0]["style"] == "bars"
    assert result["is_default"] is False


def test_style_donut_passes_through() -> None:
    """style='donut' is valid and passes through unchanged."""
    result = _norm([[{"path": "ctec", "style": "donut"}]], [])
    assert result["groups"][0]["style"] == "donut"


def test_style_invalid_string_fallback_warn() -> None:
    """Unknown style string falls back to 'auto' and warns with 'dashboard'+'style'.
    The group is KEPT — only its style resets."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([[{"path": "ctec", "style": "pie"}]], [])
    assert result["is_default"] is False
    assert len(result["groups"]) == 1
    assert result["groups"][0]["style"] == "auto"


def test_style_invalid_int_fallback_warn() -> None:
    """Integer style falls back to 'auto' and warns."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([[{"path": "ctec", "style": 123}]], [])
    assert result["groups"][0]["style"] == "auto"
    assert len(result["groups"]) == 1


def test_style_none_fallback_warn() -> None:
    """None style falls back to 'auto' and warns."""
    with pytest.warns(UserWarning, match="dashboard"):
        result = _norm([[{"path": "ctec", "style": None}]], [])
    assert result["groups"][0]["style"] == "auto"
    assert len(result["groups"]) == 1


def test_style_missing_defaults_to_auto() -> None:
    """Missing style key defaults to 'auto' silently."""
    result = _norm([[{"path": "ctec"}]], [])
    assert result["groups"][0]["style"] == "auto"


def test_style_warning_contains_style_keyword() -> None:
    """Warning for invalid style contains both 'dashboard' and 'style'."""
    with pytest.warns(UserWarning) as rec:
        _norm([[{"path": "ctec", "style": "invalid"}]], [])
    messages = [str(w.message) for w in rec]
    assert any("dashboard" in m for m in messages)
    assert any("style" in m for m in messages)


# ---------------------------------------------------------------------------
# Task 1.5 — merge order: hook lists concat, fixture appended last
# ---------------------------------------------------------------------------


def test_merge_order_hook_lists_concat() -> None:
    """Two hook lists are concatenated in order; fixture list appended last."""
    group_a = {"path": "a"}
    group_b = {"path": "b"}
    group_c = {"path": "c"}
    # hook_lists: two hookimpl results, each with one group
    result = _norm([[group_a], [group_b]], [group_c])
    paths = [g["path"] for g in result["groups"]]
    # hook results first (in order), fixture last
    assert paths == [["a"], ["b"], ["c"]]


def test_merge_order_fixture_wins_by_being_last() -> None:
    """Multiple groups from different sources are all present and ordered."""
    result = _norm([[{"path": "x"}], [{"path": "y"}]], [{"path": "z"}])
    assert len(result["groups"]) == 3
    assert result["groups"][2]["path"] == ["z"]


def test_merge_empty_hook_lists_with_fixture() -> None:
    """Empty hook lists + non-empty fixture list → groups from fixture."""
    result = _norm([], [{"path": "ctec"}])
    assert result["is_default"] is False
    assert len(result["groups"]) == 1
    assert result["groups"][0]["path"] == ["ctec"]


def test_merge_all_invalid_is_default() -> None:
    """When all entries are invalid, is_default=True."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = _norm([[{"depth": 1}], [{"path": ""}]], [{"path": 42}])
    assert result["is_default"] is True
    assert result["groups"] == []
