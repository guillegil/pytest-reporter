"""Self-contained HTML report builder."""

from __future__ import annotations

import json
import re
import warnings
from typing import Any

from ._css import CSS
from ._degraded import build_degraded_report as build_degraded_report
from ._js import JS
from ._template import build_skeleton


def _safe_default(o: object) -> str:
    """JSON encoder default: convert non-serializable values to a string fallback.

    Called by ``json.dumps`` when a value cannot be serialized natively.
    If ``str(o)`` itself raises (e.g. a ``__str__`` that throws), falls back to
    ``<unserializable TypeName>`` and emits a ``UserWarning``.

    Args:
        o: The non-serializable object.

    Returns:
        A string representation of ``o``.
    """
    try:
        return str(o)
    except Exception as exc:  # noqa: BLE001
        type_name = type(o).__name__
        warnings.warn(
            f"pytest-reporter: non-serializable value of type {type_name!r} "
            f"could not be converted to string: {exc}",
            stacklevel=4,
        )
        return f"<unserializable {type_name}>"


def _script_escape(s: str) -> str:
    """Escape ``</`` to prevent script-tag breakout in an inline ``<script>`` block.

    Replaces every occurrence of ``</`` with ``<\\/`` so that a user-controlled
    string such as ``</script><script>alert(1)</script>`` cannot terminate the
    enclosing ``<script>`` element.  Applied to the final JSON string BEFORE
    template injection (REQ-4, H2).

    Args:
        s: The JSON string to escape.

    Returns:
        The escaped string with all ``</`` replaced by ``<\\/``.
    """
    return s.replace("</", "<\\/")


def _build_system_metadata_html(system_metadata: dict[str, dict[str, str]]) -> str:
    """Build the HTML fragment for the System Data panel in the Report tab.

    Returns an empty string when ``system_metadata`` is empty so the panel
    is completely absent from the raw HTML output.

    Args:
        system_metadata: Stringified ``{section: {label: value}}`` dict from
            ``_merge_metadata``.

    Returns:
        An HTML string for one ``report-section`` block, or ``""`` when empty.
    """
    if not system_metadata:
        return ""

    rows_html = "".join(
        f'<div class="report-info-row">'
        f'<span class="report-info-label">{_esc(section)} / {_esc(label)}</span>'
        f'<span class="report-info-value">{_esc(value)}</span>'
        f"</div>"
        for section, rows in system_metadata.items()
        for label, value in rows.items()
    )
    return (
        '<div class="report-section">'
        '<div class="report-section-header">'
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"'
        ' stroke="currentColor" stroke-width="2" stroke-linecap="round">'
        '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<path d="M3 9h18M9 21V9"/>'
        "</svg>"
        " System Data"
        "</div>"
        f'<div class="report-section-body">{rows_html}</div>'
        "</div>"
    )


def _esc(text: str) -> str:
    """Escape a string for safe embedding in HTML content."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def build_html_report(data: dict[str, Any]) -> str:
    """Build a complete self-contained HTML report from collected data.

    Robustness guarantees applied here:
    - H1: ``json.dumps`` uses ``skipkeys=True`` + ``_safe_default`` to handle
      non-serializable keys/values.  An outer ``try/except`` falls back to a
      minimal safe dict if ``dumps`` still fails (e.g. circular reference).
    - H2: ``_script_escape`` is applied to BOTH ``safe_json`` (REPORT_DATA) AND
      ``sys_json`` (SYSTEM_METADATA) before template injection.
    - M1: single-pass ``re.sub`` replaces both markers in one scan so user data
      containing a marker literal is never double-substituted.
    """
    # H1: robust serialisation with skipkeys + fallback default
    try:
        data_json = json.dumps(
            data, indent=None, ensure_ascii=True, skipkeys=True, default=_safe_default
        )
    except Exception as exc:  # noqa: BLE001
        warnings.warn(
            f"pytest-reporter: REPORT_DATA serialisation failed, using minimal fallback: {exc}",
            stacklevel=2,
        )
        data_json = json.dumps({"error": "report data not serializable", "tests": []})

    # H2: escape </  to prevent script-tag breakout in REPORT_DATA
    safe_json = _script_escape(data_json)

    system_metadata: dict[str, dict[str, str]] = data.get("system_metadata", {})
    sys_html = _build_system_metadata_html(system_metadata)
    # JSON-encode the HTML fragment so it embeds safely as a JS string literal.
    # When empty the JS variable is "" (falsy) and nothing is inserted.
    # H2: escape </  in SYSTEM_METADATA payload for defence in depth.
    sys_json = _script_escape(json.dumps(sys_html))

    template = build_skeleton(CSS, JS)

    # M1: single-pass substitution — re.sub processes each marker exactly once
    # and never re-scans injected payloads.  Chained str.replace would allow
    # a marker literal inside user data to be substituted a second time,
    # corrupting the REPORT_DATA JSON.
    _payloads: dict[str, str] = {
        "/*__REPORT_DATA__*/": f"const DATA = {safe_json};",
        "/*__SYSTEM_METADATA_JSON__*/": sys_json,
    }
    # Warn if either marker is missing from the template (unexpected template change)
    for marker in _payloads:
        count = template.count(marker)
        if count != 1:
            warnings.warn(
                f"pytest-reporter: template marker {marker!r} appears {count} times "
                f"(expected exactly 1); substitution may be incorrect",
                stacklevel=2,
            )

    pattern = re.compile(r"/\*__REPORT_DATA__\*/|/\*__SYSTEM_METADATA_JSON__\*/")
    return pattern.sub(lambda m: _payloads[m.group(0)], template)
