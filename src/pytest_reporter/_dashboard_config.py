"""Dashboard grouping config — validation and normalization.

Pure module: no pytest imports, no side effects, no I/O.
Called from _report_builder.build_html_data() inside a try/except.
"""

from __future__ import annotations

import warnings
from typing import Literal

from ._types import DashboardConfig, NormalizedGroup

# Valid style literals — kept as a frozenset for O(1) lookup.
_VALID_STYLES = frozenset({"auto", "donut", "bars"})
_MAX_DEPTH = 8


def _validate_style(
    raw: object, path_label: str
) -> Literal["auto", "donut", "bars"]:
    """Validate and return style; falls back to 'auto' with a warning on bad input.

    Args:
        raw: Raw style value from the user-supplied spec.
        path_label: Human-readable group identifier for warning messages.

    Returns:
        A valid style literal: one of 'auto', 'donut', 'bars'.
    """
    if raw not in _VALID_STYLES:
        warnings.warn(
            f"pytest-reporter dashboard: group '{path_label}' has invalid style "
            f"{raw!r} — falling back to 'auto'. "
            "Valid values are: 'auto', 'donut', 'bars'.",
            UserWarning,
            stacklevel=4,
        )
        return "auto"
    # raw is guaranteed to be one of the valid literals at this point
    return raw  # type: ignore[return-value]


def _validate_depth(raw: object, path_label: str) -> int:
    """Validate depth; clamps to [1, _MAX_DEPTH] with a warning on bad input.

    Args:
        raw: Raw depth value from the user-supplied spec.
        path_label: Human-readable group identifier for warning messages.

    Returns:
        A valid depth integer in range [1, _MAX_DEPTH].
    """
    if not isinstance(raw, int) or isinstance(raw, bool):
        warnings.warn(
            f"pytest-reporter dashboard: group '{path_label}' has non-integer "
            f"depth {raw!r} — clamping to 1.",
            UserWarning,
            stacklevel=4,
        )
        return 1

    if raw < 1:
        warnings.warn(
            f"pytest-reporter dashboard: group '{path_label}' has depth {raw} "
            f"which is < 1 — clamping to 1.",
            UserWarning,
            stacklevel=4,
        )
        return 1

    if raw > _MAX_DEPTH:
        warnings.warn(
            f"pytest-reporter dashboard: group '{path_label}' has depth {raw} "
            f"which exceeds maximum {_MAX_DEPTH} — clamping to {_MAX_DEPTH}.",
            UserWarning,
            stacklevel=4,
        )
        return _MAX_DEPTH

    return raw


def _normalize_entry(entry: object) -> NormalizedGroup | None:
    """Validate and normalize a single raw group spec entry.

    Args:
        entry: Raw entry from a hook or fixture list.

    Returns:
        A fully-defaulted ``NormalizedGroup`` dict, or ``None`` if the entry
        is wholly invalid and should be skipped.
    """
    if not isinstance(entry, dict):
        warnings.warn(
            "pytest-reporter dashboard: group entry is not a dict — skipping.",
            UserWarning,
            stacklevel=3,
        )
        return None

    # --- path (required) ---
    raw_path = entry.get("path")
    if not isinstance(raw_path, str):
        warnings.warn(
            f"pytest-reporter dashboard: group entry has missing or non-string 'path' "
            f"({raw_path!r}) — skipping.",
            UserWarning,
            stacklevel=3,
        )
        return None

    if not raw_path:
        warnings.warn(
            "pytest-reporter dashboard: group entry has empty 'path' — skipping.",
            UserWarning,
            stacklevel=3,
        )
        return None

    path_parts = [p for p in raw_path.split("/") if p]
    path_label = raw_path  # for warning messages

    # --- depth (optional, default 1) ---
    raw_depth = entry.get("depth", 1)
    depth = _validate_depth(raw_depth, path_label)

    # --- include_self (optional, default False) — coerce silently ---
    raw_include_self = entry.get("include_self", False)
    include_self = bool(raw_include_self)

    # --- label (optional, default: last path segment) — coerce silently ---
    raw_label = entry.get("label", path_parts[-1] if path_parts else raw_path)
    label = str(raw_label)

    # --- style (optional, default 'auto') ---
    raw_style = entry.get("style", "auto")
    style = _validate_style(raw_style, path_label)

    return NormalizedGroup(
        path=path_parts,
        depth=depth,
        include_self=include_self,
        label=label,
        style=style,
    )


def normalize_dashboard(
    hook_lists: list[list[object]],
    fixture_list: list[object],
) -> DashboardConfig:
    """Validate and normalize dashboard grouping config from hooks + fixture.

    Hook lists are processed in order (matching hook-registration order — the
    caller passes them in LIFO-reversed order so index 0 = first-registered).
    The fixture list is appended last so fixture groups appear after hook groups.

    All validation errors emit ``warnings.warn(UserWarning)`` and degrade
    gracefully — they never raise. A wholly invalid config returns
    ``is_default=True`` so the renderer falls back to the built-in default.

    Args:
        hook_lists: List of hook result lists. Each element is the ``list``
            returned by one hookimpl (``pytest_reporter_dashboard`` result).
            May be empty or contain ``None`` entries.
        fixture_list: List of raw group specs from the ``report_dashboard``
            fixture. Applied after hook results.

    Returns:
        A :class:`DashboardConfig` with normalized groups and ``is_default``
        flag.  ``is_default`` is ``True`` iff no valid group was produced.
    """
    groups: list[NormalizedGroup] = []

    for hook_result in hook_lists:
        if not hook_result:
            continue
        if not isinstance(hook_result, list):
            warnings.warn(
                f"pytest-reporter dashboard: hook result is not a list "
                f"({type(hook_result).__name__}) — skipping.",
                UserWarning,
                stacklevel=2,
            )
            continue
        for entry in hook_result:
            normalized = _normalize_entry(entry)
            if normalized is not None:
                groups.append(normalized)

    for entry in fixture_list:
        normalized = _normalize_entry(entry)
        if normalized is not None:
            groups.append(normalized)

    is_default = len(groups) == 0
    return DashboardConfig(groups=groups, is_default=is_default)
