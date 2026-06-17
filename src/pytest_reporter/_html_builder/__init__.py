"""Self-contained HTML report builder."""

from __future__ import annotations

import json
from typing import Any

from ._css import CSS
from ._js import JS
from ._template import build_skeleton


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
    """Build a complete self-contained HTML report from collected data."""
    data_json = json.dumps(data, indent=None, default=str)
    # Escape for safe embedding in <script> tag
    safe_json = data_json.replace("</", "<\\/")

    system_metadata: dict[str, dict[str, str]] = data.get("system_metadata", {})
    sys_html = _build_system_metadata_html(system_metadata)
    # JSON-encode the HTML fragment so it embeds safely as a JS string literal.
    # When empty the JS variable is "" (falsy) and nothing is inserted.
    sys_json = json.dumps(sys_html)

    template = build_skeleton(CSS, JS)
    return template.replace("/*__REPORT_DATA__*/", f"const DATA = {safe_json};").replace(
        "/*__SYSTEM_METADATA_JSON__*/", sys_json
    )
