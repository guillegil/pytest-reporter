"""Degraded HTML report template for sessionfinish failure fallback.

When the normal HTML build pipeline raises an unhandled exception, the reporter
calls ``build_degraded_report`` to produce a minimal but syntactically valid
``report.html``.  The degraded report is generated from a STATIC template —
never from the failed pipeline — so it is guaranteed not to re-raise.

M3 deferral note (reviewed 2026-06-18):
    SVG artifacts are classified as IMAGE and rendered via
    ``<img src=data_uri>`` (_js.py:745) — a passive context where scripts
    cannot execute.  HTML artifacts render via
    ``<iframe src=data_uri sandbox="allow-same-origin">`` (_js.py:726)
    WITHOUT ``allow-scripts``, so embedded scripts are inert.
    There is no active script execution surface in the current render paths,
    so no XSS hardening of artifact render is needed today.
    Revisit only if ``allow-scripts`` is ever added to the iframe sandbox.
"""

from __future__ import annotations

from pathlib import Path


def _esc(text: str) -> str:
    """Escape a string for safe embedding in HTML content."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


_DEGRADED_STYLE = """
body {
    font-family: system-ui, sans-serif;
    background: #111;
    color: #eee;
    margin: 0;
    padding: 2rem;
}
h1 { color: #ef4444; margin-bottom: 0.5rem; }
h2 { color: #f59e0b; margin-top: 2rem; }
pre {
    background: #1e1e1e;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 1rem;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    color: #fca5a5;
}
.meta { color: #9ca3af; font-size: 0.875rem; margin-top: 0.25rem; }
.note {
    background: #1c2333;
    border-left: 4px solid #f59e0b;
    padding: 0.75rem 1rem;
    margin-top: 1rem;
    border-radius: 0 4px 4px 0;
}
"""


def build_degraded_report(run_dir: Path, exc: BaseException) -> str:
    """Build a minimal self-contained HTML report describing a build failure.

    This function is pure (no I/O) and guaranteed not to raise.  All
    user-controlled values are HTML-escaped via ``_esc``.  The output contains
    no inline JavaScript, no template markers, and no embedded test data.

    Args:
        run_dir: The timestamped run directory where the report will be written.
        exc: The exception that caused the normal build pipeline to fail.

    Returns:
        A syntactically valid, self-contained HTML string.
    """
    exc_type = _esc(type(exc).__name__)
    exc_msg = _esc(str(exc))
    run_dir_escaped = _esc(str(run_dir))

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Report Generation Failed</title>\n"
        f"<style>{_DEGRADED_STYLE}</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>Report Generation Failed</h1>\n"
        f'<p class="meta">Run directory: {run_dir_escaped}</p>\n'
        '<div class="note">\n'
        "  The HTML report could not be built due to an unexpected error.\n"
        "  Raw artifacts (junit.xml, pytest.log, per-test JSON files) are\n"
        "  still available in the run directory.\n"
        "</div>\n"
        "<h2>Error</h2>\n"
        f"<pre>{exc_type}: {exc_msg}</pre>\n"
        "</body>\n"
        "</html>\n"
    )
