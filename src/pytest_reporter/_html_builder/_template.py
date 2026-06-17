"""HTML skeleton builder for the self-contained report template."""

from __future__ import annotations

_SKELETON = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test Report</title>
<style>
/*__CSS__*/
</style>
</head>
<body>
<div class="header">
  <div class="header-logo">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
    <h1>Test Report</h1>
  </div>
  <div class="meta" id="header-meta"></div>
</div>
<div class="tabs" role="tablist">
  <button class="tab-btn active" data-tab="summary" role="tab" aria-selected="true">Summary</button>
  <button class="tab-btn" data-tab="tests" role="tab" aria-selected="false">Tests</button>
  <button class="tab-btn" data-tab="session-logs" role="tab" aria-selected="false">Session Logs</button>
  <button class="tab-btn" data-tab="report" role="tab" aria-selected="false">Report</button>
</div>
<div id="tab-summary" class="tab-panel active" role="tabpanel"></div>
<div id="tab-tests" class="tab-panel" role="tabpanel"></div>
<div id="tab-session-logs" class="tab-panel" role="tabpanel"></div>
<div id="tab-report" class="tab-panel" role="tabpanel"></div>
<script>
/*__JS__*/
</script>
</body>
</html>
"""


def build_skeleton(css: str, js: str) -> str:
    """Assemble the full HTML document skeleton with CSS and JS substituted in.

    The ``/*__CSS__*/`` and ``/*__JS__*/`` markers in ``_SKELETON`` are replaced
    with the provided ``css`` and ``js`` strings respectively.  The two data
    markers (``/*__REPORT_DATA__*/`` and ``/*__SYSTEM_METADATA_JSON__*/``) are
    kept intact inside ``js`` for the assembler to substitute at report-build
    time.

    Args:
        css: The raw CSS body to embed between ``<style>`` tags.
        js: The raw JavaScript body to embed between ``<script>`` tags.
            Must contain the two report-data markers.

    Returns:
        A complete HTML document string ready for data injection.
    """
    return _SKELETON.replace("/*__CSS__*/", css).replace("/*__JS__*/", js)
