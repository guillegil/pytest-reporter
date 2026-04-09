"""Self-contained HTML report builder."""

from __future__ import annotations

import json
from typing import Any


def build_html_report(data: dict[str, Any]) -> str:
    """Build a complete self-contained HTML report from collected data."""
    data_json = json.dumps(data, indent=None, default=str)
    # Escape for safe embedding in <script> tag
    safe_json = data_json.replace("</", "<\\/")
    return _HTML_TEMPLATE.replace("/*__REPORT_DATA__*/", f"const DATA = {safe_json};")


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test Report</title>
<style>
/* ================================================================
   Design tokens
   ================================================================ */
:root {
  --c-passed: #22C55E;
  --c-failed: #EF4444;
  --c-skipped: #F59E0B;
  --c-error: #F97316;

  --c-passed-dim: rgba(34,197,94,0.12);
  --c-failed-dim: rgba(239,68,68,0.12);
  --c-skipped-dim: rgba(245,158,11,0.12);
  --c-error-dim: rgba(249,115,22,0.12);

  --c-bg: #0B1120;
  --c-surface: #131C2E;
  --c-surface2: #1B2740;
  --c-surface3: #243352;
  --c-text: #E8ECF4;
  --c-text2: #8292AA;
  --c-text3: #5A6B84;
  --c-border: #1E2D45;
  --c-border2: #2A3D5A;
  --c-accent: #3B82F6;
  --c-accent-dim: rgba(59,130,246,0.12);

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 18px;

  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.25);
  --shadow-lg: 0 8px 30px rgba(0,0,0,0.35);
  --shadow-glow: 0 0 20px rgba(59,130,246,0.08);

  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-mono: 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace;

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* ================================================================
   Reset & base
   ================================================================ */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { -webkit-text-size-adjust: 100%; }
body {
  font-family: var(--font-sans);
  background: var(--c-bg);
  color: var(--c-text);
  line-height: 1.55;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
a { color: var(--c-accent); text-decoration: none; }
button { font-family: inherit; }
:focus-visible {
  outline: 2px solid var(--c-accent);
  outline-offset: 2px;
  border-radius: 2px;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* ================================================================
   Scrollbar
   ================================================================ */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--c-border2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--c-text3); }

/* ================================================================
   Header
   ================================================================ */
.header {
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  padding: 0 28px;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 16px;
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(12px);
  background: rgba(19,28,46,0.92);
}
.header-logo {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-logo svg { flex-shrink: 0; }
.header h1 {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.header .meta {
  color: var(--c-text2);
  font-size: 12px;
  margin-left: auto;
  font-family: var(--font-mono);
  display: flex;
  align-items: center;
  gap: 16px;
}
.header .meta-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.meta-badge.pass { background: var(--c-passed-dim); color: var(--c-passed); }
.meta-badge.fail { background: var(--c-failed-dim); color: var(--c-failed); }
.meta-badge.mix { background: var(--c-accent-dim); color: var(--c-accent); }

/* ================================================================
   Tabs
   ================================================================ */
.tabs {
  display: flex;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  padding: 0 28px;
  gap: 2px;
  position: sticky;
  top: 56px;
  z-index: 99;
  backdrop-filter: blur(12px);
  background: rgba(19,28,46,0.92);
}
.tab-btn {
  padding: 12px 20px;
  background: none;
  border: none;
  color: var(--c-text3);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s var(--ease-out), border-color 0.2s var(--ease-out);
  position: relative;
}
.tab-btn:hover { color: var(--c-text2); }
.tab-btn.active {
  color: var(--c-text);
  border-bottom-color: var(--c-accent);
}
.tab-panel { display: none; }
.tab-panel.active { display: block; }

/* ================================================================
   Summary Tab
   ================================================================ */
.summary-container { padding: 28px; max-width: 1400px; margin: 0 auto; }

.counters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 32px;
}
.counter-card {
  background: var(--c-surface);
  border-radius: var(--radius-lg);
  padding: 20px;
  text-align: center;
  border: 1px solid var(--c-border);
  transition: transform 0.25s var(--ease-out), border-color 0.25s var(--ease-out), box-shadow 0.25s var(--ease-out);
  cursor: default;
  position: relative;
  overflow: hidden;
}
.counter-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  opacity: 0.8;
}
.counter-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.counter-card .value {
  font-size: 36px;
  font-weight: 700;
  font-family: var(--font-mono);
  letter-spacing: -0.03em;
  line-height: 1.1;
}
.counter-card .label {
  font-size: 11px;
  color: var(--c-text3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  margin-top: 6px;
}
.counter-card.passed { border-color: rgba(34,197,94,0.2); }
.counter-card.passed::before { background: var(--c-passed); }
.counter-card.passed .value { color: var(--c-passed); }
.counter-card.passed:hover { border-color: rgba(34,197,94,0.35); box-shadow: 0 4px 20px rgba(34,197,94,0.1); }

.counter-card.failed { border-color: rgba(239,68,68,0.2); }
.counter-card.failed::before { background: var(--c-failed); }
.counter-card.failed .value { color: var(--c-failed); }
.counter-card.failed:hover { border-color: rgba(239,68,68,0.35); box-shadow: 0 4px 20px rgba(239,68,68,0.1); }

.counter-card.skipped { border-color: rgba(245,158,11,0.2); }
.counter-card.skipped::before { background: var(--c-skipped); }
.counter-card.skipped .value { color: var(--c-skipped); }
.counter-card.skipped:hover { border-color: rgba(245,158,11,0.35); box-shadow: 0 4px 20px rgba(245,158,11,0.1); }

.counter-card.error { border-color: rgba(249,115,22,0.2); }
.counter-card.error::before { background: var(--c-error); }
.counter-card.retried { border-color: rgba(59,130,246,0.2); }
.counter-card.retried::before { background: var(--c-accent); }
.counter-card.retried .value { color: var(--c-accent); }
.counter-card.retried:hover { border-color: rgba(59,130,246,0.35); box-shadow: 0 4px 20px rgba(59,130,246,0.1); }
.counter-card.error .value { color: var(--c-error); }
.counter-card.error:hover { border-color: rgba(249,115,22,0.35); box-shadow: 0 4px 20px rgba(249,115,22,0.1); }

.counter-card.total { border-color: rgba(59,130,246,0.2); }
.counter-card.total::before { background: var(--c-accent); }
.counter-card.total .value { color: var(--c-accent); }
.counter-card.total:hover { border-color: rgba(59,130,246,0.35); box-shadow: 0 4px 20px rgba(59,130,246,0.1); }

/* Charts */
.charts-section { margin-bottom: 32px; }
.charts-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text2);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.charts-section-title::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--c-border);
}
.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.chart-card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  padding: 24px 20px;
  text-align: center;
  cursor: pointer;
  transition: transform 0.25s var(--ease-out), border-color 0.25s var(--ease-out), box-shadow 0.25s var(--ease-out);
}
.chart-card:hover {
  transform: translateY(-2px);
  border-color: var(--c-border2);
  box-shadow: var(--shadow-md);
}
.chart-card h3 {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--c-text);
}
.chart-card svg { display: block; margin: 0 auto; }
.chart-legend {
  display: flex;
  gap: 14px;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 14px;
  font-size: 11px;
  color: var(--c-text2);
}
.chart-legend span {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: 500;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

/* ================================================================
   Tests Tab
   ================================================================ */
.tests-layout {
  display: flex;
  gap: 0;
  height: calc(100vh - 112px);
}
.tree-panel {
  width: 380px;
  min-width: 300px;
  background: var(--c-surface);
  border-right: 1px solid var(--c-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.detail-panel {
  flex: 1;
  overflow-y: auto;
  background: var(--c-bg);
  padding: 28px 32px;
}

/* Search & Filters */
.tree-controls {
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--c-border);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.search-box {
  position: relative;
}
.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--c-text3);
  pointer-events: none;
}
.search-input {
  width: 100%;
  padding: 7px 12px 7px 34px;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  color: var(--c-text);
  font-size: 12px;
  transition: border-color 0.2s var(--ease-out), box-shadow 0.2s var(--ease-out);
}
.search-input::placeholder { color: var(--c-text3); }
.search-input:focus {
  outline: none;
  border-color: var(--c-accent);
  box-shadow: 0 0 0 3px var(--c-accent-dim);
}
.tree-controls-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.filter-toggles { display: flex; gap: 4px; flex-wrap: wrap; flex: 1; }
.filter-btn {
  padding: 3px 10px;
  border-radius: 20px;
  border: 1px solid var(--c-border);
  background: none;
  color: var(--c-text3);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
  user-select: none;
}
.filter-btn:hover { border-color: var(--c-border2); color: var(--c-text2); }
.filter-btn.active { border-color: currentColor; }
.filter-btn.passed.active { color: var(--c-passed); background: var(--c-passed-dim); }
.filter-btn.failed.active { color: var(--c-failed); background: var(--c-failed-dim); }
.filter-btn.skipped.active { color: var(--c-skipped); background: var(--c-skipped-dim); }
.filter-btn.error.active { color: var(--c-error); background: var(--c-error-dim); }
.tree-expand-btn {
  padding: 3px 6px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--c-border);
  background: none;
  color: var(--c-text3);
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.tree-expand-btn:hover { background: var(--c-surface2); color: var(--c-text2); border-color: var(--c-border2); }

/* Tree */
.tree-content {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
}
.tree-node { user-select: none; }
.tree-row {
  display: flex;
  align-items: center;
  padding: 5px 16px;
  cursor: pointer;
  font-size: 13px;
  gap: 8px;
  transition: background 0.12s var(--ease-out);
  border-left: 2px solid transparent;
}
.tree-row:hover { background: var(--c-surface2); }
.tree-row.selected {
  background: var(--c-accent-dim);
  border-left-color: var(--c-accent);
}
.tree-icon {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--c-text3);
  transition: transform 0.2s var(--ease-out);
}
.tree-node.expanded > .tree-row > .tree-icon { transform: rotate(90deg); }
.tree-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 400;
}
.tree-badges {
  display: flex;
  gap: 3px;
  flex-shrink: 0;
  align-items: center;
}
.tree-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 0px 5px;
  border-radius: 8px;
  font-family: var(--font-mono);
  line-height: 16px;
}
.tree-badge.passed { background: var(--c-passed-dim); color: var(--c-passed); }
.tree-badge.failed { background: var(--c-failed-dim); color: var(--c-failed); }
.tree-badge.skipped { background: var(--c-skipped-dim); color: var(--c-skipped); }
.tree-badge.error { background: var(--c-error-dim); color: var(--c-error); }
.tree-badge.count {
  background: var(--c-surface3);
  color: var(--c-text3);
}
.tree-children { display: none; }
.tree-node.expanded > .tree-children { display: block; }
@media (prefers-reduced-motion: reduce) {
  .tree-icon { transition: none; }
}

/* Outcome indicators */
.status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
.status-dot.passed { background: var(--c-passed); }
.status-dot.failed { background: var(--c-failed); }
.status-dot.skipped { background: var(--c-skipped); }
.status-dot.error { background: var(--c-error); }

/* ================================================================
   Detail Panel
   ================================================================ */
.detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--c-text3);
  gap: 16px;
}
.detail-empty svg { opacity: 0.2; }
.detail-empty span { font-size: 14px; }
.detail-header {
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--c-border);
}
.detail-header-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.detail-header-outcome {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
  margin-top: 2px;
}
.detail-header-outcome.passed { background: var(--c-passed-dim); color: var(--c-passed); }
.detail-header-outcome.failed { background: var(--c-failed-dim); color: var(--c-failed); }
.detail-header-outcome.skipped { background: var(--c-skipped-dim); color: var(--c-skipped); }
.detail-header-outcome.error { background: var(--c-error-dim); color: var(--c-error); }
.detail-header h2 {
  font-size: 17px;
  font-weight: 700;
  word-break: break-all;
  letter-spacing: -0.02em;
  line-height: 1.3;
}
.detail-header .file-path {
  font-size: 12px;
  color: var(--c-text3);
  font-family: var(--font-mono);
  margin-top: 6px;
}
.detail-header-stats {
  display: flex;
  gap: 16px;
  margin-top: 12px;
  font-size: 12px;
  color: var(--c-text2);
}
.detail-header-stat {
  display: flex;
  align-items: center;
  gap: 5px;
}
.detail-header-stat strong {
  color: var(--c-text);
  font-weight: 600;
}

/* Section labels */
.detail-section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--c-text3);
  margin-bottom: 8px;
}

/* Run pills */
.run-filters { margin-bottom: 10px; }
.run-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 24px;
}
.run-pill {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 11px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.15s var(--ease-out);
  font-weight: 600;
  font-family: var(--font-mono);
  letter-spacing: -0.01em;
}
.run-pill.passed { background: var(--c-passed-dim); color: var(--c-passed); }
.run-pill.failed { background: var(--c-failed-dim); color: var(--c-failed); }
.run-pill.skipped { background: var(--c-skipped-dim); color: var(--c-skipped); }
.run-pill.error { background: var(--c-error-dim); color: var(--c-error); }
.run-pill:hover { filter: brightness(1.2); }
.run-pill.selected { border-color: currentColor; box-shadow: 0 0 0 1px currentColor; }
.show-more-btn {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 11px;
  cursor: pointer;
  border: 1px dashed var(--c-border2);
  background: none;
  color: var(--c-text3);
  font-weight: 500;
  transition: all 0.15s var(--ease-out);
}
.show-more-btn:hover { border-color: var(--c-text3); color: var(--c-text2); }

/* Sub-tabs */
.sub-tabs {
  display: flex;
  gap: 2px;
  margin-bottom: 20px;
  background: var(--c-surface);
  border-radius: var(--radius-md);
  padding: 3px;
  border: 1px solid var(--c-border);
}
.sub-tab-btn {
  padding: 7px 16px;
  background: none;
  border: none;
  color: var(--c-text3);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all 0.15s var(--ease-out);
}
.sub-tab-btn:hover { color: var(--c-text2); background: var(--c-surface2); }
.sub-tab-btn.active {
  color: var(--c-text);
  background: var(--c-surface3);
  box-shadow: var(--shadow-sm);
}

/* Run detail content */
.run-detail-content {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  padding: 20px;
}
.info-grid {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 8px 16px;
  font-size: 13px;
  margin-bottom: 20px;
}
.info-label {
  color: var(--c-text3);
  font-weight: 500;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.info-value { color: var(--c-text); }
.params-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-bottom: 20px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.params-table th {
  text-align: left;
  padding: 8px 14px;
  background: var(--c-surface2);
  color: var(--c-text3);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.params-table td {
  padding: 8px 14px;
  border-bottom: 1px solid var(--c-border);
  font-family: var(--font-mono);
  font-size: 12px;
}
.params-table tr:last-child td { border-bottom: none; }
/* Phase tabs (horizontal Setup / Call / Teardown) */
.phase-tabs-bar {
  display: flex;
  gap: 0;
  border: 1px solid var(--c-border);
  border-bottom: none;
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  overflow: hidden;
  background: var(--c-surface2);
}
.phase-tab-btn {
  flex: 1;
  padding: 9px 14px;
  background: none;
  border: none;
  border-right: 1px solid var(--c-border);
  color: var(--c-text3);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  transition: background 0.15s var(--ease-out), color 0.15s var(--ease-out);
}
.phase-tab-btn:last-child { border-right: none; }
.phase-tab-btn:hover { background: var(--c-surface3); color: var(--c-text2); }
.phase-tab-btn.active {
  background: var(--c-bg);
  color: var(--c-text);
  box-shadow: inset 0 -2px 0 var(--c-accent);
}
.phase-tab-btn .phase-meta {
  font-size: 10px;
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0;
  color: var(--c-text3);
}
.phase-tab-panel {
  display: none;
  border: 1px solid var(--c-border);
  border-top: none;
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  background: var(--c-bg);
  max-height: 400px;
  overflow-y: auto;
}
.phase-tab-panel.active { display: block; }
.phase-tab-body {
  padding: 14px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--c-text2);
}
.phase-tab-empty {
  padding: 24px 14px;
  text-align: center;
  color: var(--c-text3);
  font-size: 13px;
}

/* Artifacts */
.artifact-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.artifact-card {
  background: var(--c-surface2);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: border-color 0.15s var(--ease-out);
  cursor: pointer;
}
.artifact-card:hover { border-color: var(--c-border2); }
.artifact-thumb {
  width: 100%;
  aspect-ratio: 4/3;
  object-fit: cover;
  display: block;
  background: var(--c-bg);
}
.artifact-info {
  padding: 10px 12px;
  font-size: 12px;
}
.artifact-name {
  font-weight: 600;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.artifact-size { color: var(--c-text3); font-size: 11px; margin-top: 2px; }
.artifact-file-card {
  background: var(--c-surface2);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: border-color 0.15s var(--ease-out);
}
.artifact-file-card:hover { border-color: var(--c-border2); }
.artifact-file-icon { color: var(--c-text3); flex-shrink: 0; }
.artifact-html-frame {
  width: 100%;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: #fff;
  min-height: 200px;
  margin-bottom: 12px;
}

/* Lightbox */
.lightbox-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.85);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  backdrop-filter: blur(4px);
}
.lightbox-overlay img {
  max-width: 90vw;
  max-height: 90vh;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
}

/* ================================================================
   Log Entries (structured logger)
   ================================================================ */
.log-entries { display: flex; flex-direction: column; gap: 2px; }
.log-entry {
  display: grid;
  grid-template-columns: auto auto auto 1fr;
  gap: 8px;
  align-items: baseline;
  padding: 4px 10px;
  font-size: 12px;
  font-family: var(--font-mono);
  border-radius: 4px;
  line-height: 1.5;
}
.log-entry:hover { background: var(--c-surface3); }
.log-entry-time { color: var(--c-text3); font-size: 11px; white-space: nowrap; }
.log-entry-level {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.log-entry-level.DEBUG { background: var(--c-accent-dim); color: var(--c-accent); }
.log-entry-level.INFO { background: var(--c-passed-dim); color: var(--c-passed); }
.log-entry-level.WARNING { background: var(--c-skipped-dim); color: var(--c-skipped); }
.log-entry-level.ERROR { background: var(--c-failed-dim); color: var(--c-failed); }
.log-entry-level.CRITICAL { background: rgba(239,68,68,0.25); color: #FF6B6B; }
.log-entry-source { color: var(--c-text2); font-size: 11px; }
.log-entry-msg { color: var(--c-text); word-break: break-word; }
.log-entry-data {
  grid-column: 1 / -1;
  margin-left: 24px;
  padding: 6px 10px;
  background: var(--c-surface);
  border-radius: 4px;
  font-size: 11px;
  color: var(--c-text2);
  white-space: pre-wrap;
  max-height: 200px;
  overflow: auto;
}
.log-entry-exc {
  grid-column: 1 / -1;
  margin-left: 24px;
  padding: 8px 10px;
  background: var(--c-failed-dim);
  border-radius: 4px;
  font-size: 11px;
  color: var(--c-failed);
  white-space: pre-wrap;
  max-height: 300px;
  overflow: auto;
}
.log-hidden { display: none !important; }

/* ================================================================
   Procedure Steps
   ================================================================ */
.procedure-list { display: flex; flex-direction: column; gap: 4px; padding: 8px 0; }
.procedure-step {
  padding: 8px 12px;
  background: var(--c-surface2);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
}
.procedure-step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.procedure-step-number {
  font-weight: 700;
  color: var(--c-text2);
  font-family: var(--font-mono);
  font-size: 12px;
  min-width: 28px;
}
.procedure-step-desc { color: var(--c-text); flex: 1; }
.procedure-step-duration {
  color: var(--c-text3);
  font-size: 11px;
  font-family: var(--font-mono);
}
.procedure-substeps {
  margin-left: 28px;
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.procedure-substep {
  padding: 4px 10px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: 4px;
}
.procedure-substep:hover { background: var(--c-surface3); }
.procedure-step-exc {
  margin-top: 6px;
  padding: 6px 10px;
  background: var(--c-failed-dim);
  border-radius: 4px;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--c-failed);
  white-space: pre-wrap;
  max-height: 200px;
  overflow: auto;
}
.procedure-empty {
  padding: 24px;
  text-align: center;
  color: var(--c-text3);
  font-size: 13px;
}
.check-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}
.check-badge.pass { background: var(--c-passed-dim); color: var(--c-passed); }
.check-badge.fail { background: var(--c-failed-dim); color: var(--c-failed); }
.procedure-check-desc {
  color: var(--c-text3);
  font-size: 12px;
  font-style: italic;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ================================================================
   Verification Cards
   ================================================================ */
.check-cards { display: flex; flex-direction: column; gap: 8px; padding: 8px 0; }
.check-card {
  border-radius: var(--radius-md);
  padding: 14px 16px;
  border: 1px solid;
  transition: max-height 0.3s var(--ease-out);
  overflow: hidden;
}
.check-card.passed {
  background: var(--c-passed-dim);
  border-color: rgba(34,197,94,0.25);
  border-left: 3px solid var(--c-passed);
}
.check-card.failed {
  background: var(--c-failed-dim);
  border-color: rgba(239,68,68,0.25);
  border-left: 3px solid var(--c-failed);
}
.check-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}
.check-card-header .check-name {
  font-weight: 600;
  flex-shrink: 0;
}
.check-card-header .check-desc {
  color: var(--c-text2);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.check-card-header .check-type-badge {
  margin-left: auto;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: var(--c-surface3);
  color: var(--c-text2);
  flex-shrink: 0;
}
.check-card-body {
  display: none;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--c-border);
}
.check-card.expanded .check-card-body { display: block; }
.check-card.failed .check-card-body { display: block; }
.check-card-detail {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 14px;
  font-size: 12px;
}
.check-card-detail .label {
  color: var(--c-text3);
  font-weight: 500;
}
.check-card-detail .value {
  font-family: var(--font-mono);
  color: var(--c-text);
  font-size: 11px;
}
.check-card-longrepr {
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(0,0,0,0.2);
  border-radius: 4px;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--c-text2);
  white-space: pre-wrap;
  max-height: 200px;
  overflow: auto;
}
.checks-summary {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--c-text2);
}
.checks-summary .checks-count {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: 600;
}

/* ================================================================
   Retry Cards
   ================================================================ */
.retry-section { display: flex; flex-direction: column; gap: 12px; padding: 8px 0; }
.retry-original {
  background: var(--c-failed-dim);
  border: 1px solid rgba(239,68,68,0.3);
  border-left: 3px solid var(--c-failed);
  border-radius: var(--radius-md);
  padding: 16px;
}
.retry-original-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-weight: 600;
  font-size: 13px;
  color: var(--c-failed);
}
.retry-card {
  background: var(--c-surface2);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.retry-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: background 0.15s var(--ease-out);
}
.retry-card-header:hover { background: var(--c-surface3); }
.retry-card-body {
  padding: 0 16px 16px;
  display: none;
}
.retry-card.expanded .retry-card-body { display: block; }
.retry-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  font-weight: 700;
  margin-left: 4px;
  opacity: 0.8;
}

/* ================================================================
   Session Logs Tab
   ================================================================ */
.session-log-container { padding: 28px; max-width: 1100px; margin: 0 auto; }
.session-log-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.session-log-search-wrap {
  position: relative;
  flex: 1;
  min-width: 180px;
}
.session-log-search-wrap svg {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--c-text3);
  pointer-events: none;
}
.session-log-search {
  width: 100%;
  padding: 7px 12px 7px 32px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--c-border);
  background: var(--c-surface2);
  color: var(--c-text);
  font-family: var(--font-mono);
  font-size: 12px;
  transition: border-color 0.15s var(--ease-out);
}
.session-log-search:focus { outline: none; border-color: var(--c-accent); }
.session-log-search::placeholder { color: var(--c-text3); }
.session-log-level-filters { display: flex; gap: 4px; flex-wrap: wrap; }
.session-log-level-btn {
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid var(--c-border);
  background: none;
  color: var(--c-text3);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
  user-select: none;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.session-log-level-btn:hover { border-color: var(--c-border2); color: var(--c-text2); }
.session-log-level-btn.active { border-color: currentColor; }
.session-log-level-btn.DEBUG.active { color: var(--c-accent); background: var(--c-accent-dim); }
.session-log-level-btn.INFO.active { color: var(--c-passed); background: var(--c-passed-dim); }
.session-log-level-btn.WARNING.active { color: var(--c-skipped); background: var(--c-skipped-dim); }
.session-log-level-btn.ERROR.active { color: var(--c-failed); background: var(--c-failed-dim); }
.session-log-level-btn.CRITICAL.active { color: #FF6B6B; background: rgba(239,68,68,0.25); }
.session-log-actions { display: flex; gap: 4px; margin-left: auto; }
.session-log-action-btn {
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--c-border);
  background: none;
  color: var(--c-text2);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
  white-space: nowrap;
}
.session-log-action-btn:hover {
  background: var(--c-surface2);
  color: var(--c-text);
  border-color: var(--c-border2);
}
.session-log-tree { display: flex; flex-direction: column; gap: 6px; }
.session-log-section {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  transition: border-color 0.15s var(--ease-out);
}
.session-log-section:hover { border-color: var(--c-border2); }
.session-log-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s var(--ease-out);
  user-select: none;
}
.session-log-section-header:hover { background: var(--c-surface2); }
.session-log-chevron {
  flex-shrink: 0;
  color: var(--c-text3);
  transition: transform 0.2s var(--ease-out);
}
.session-log-section.expanded > .session-log-section-header .session-log-chevron {
  transform: rotate(90deg);
}
.session-log-section-name { font-weight: 600; color: var(--c-text); }
.session-log-section-count {
  color: var(--c-text3);
  font-size: 11px;
  font-weight: 400;
}
.session-log-section-levels {
  display: flex;
  gap: 4px;
  margin-left: auto;
}
.session-log-level-pill {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.session-log-level-pill.DEBUG { background: var(--c-accent-dim); color: var(--c-accent); }
.session-log-level-pill.INFO { background: var(--c-passed-dim); color: var(--c-passed); }
.session-log-level-pill.WARNING { background: var(--c-skipped-dim); color: var(--c-skipped); }
.session-log-level-pill.ERROR { background: var(--c-failed-dim); color: var(--c-failed); }
.session-log-level-pill.CRITICAL { background: rgba(239,68,68,0.25); color: #FF6B6B; }
.session-log-section-body {
  display: none;
  padding: 0 14px 12px;
}
.session-log-section.expanded > .session-log-section-body { display: block; }
.session-log-child {
  background: transparent;
  border: none;
  border-left: 2px solid var(--c-border2);
  border-radius: 0;
  margin-top: 4px;
}
.session-log-child > .session-log-section-header {
  padding: 7px 12px;
  font-size: 12px;
}
.session-log-child > .session-log-section-header:hover { background: var(--c-surface3); }
.session-log-child > .session-log-section-body { padding: 0 12px 8px; }
.session-log-root-entries {
  padding-top: 6px;
  border-top: 1px solid var(--c-border);
  margin-top: 6px;
}
.session-log-empty {
  padding: 60px 40px;
  text-align: center;
  color: var(--c-text3);
  font-size: 14px;
}
@media (prefers-reduced-motion: reduce) {
  .session-log-chevron { transition: none; }
}
@media (max-width: 640px) {
  .session-log-toolbar { flex-direction: column; align-items: stretch; }
  .session-log-search-wrap { min-width: 100%; }
  .session-log-actions { margin-left: 0; justify-content: flex-end; }
}

/* ================================================================
   Report Tab
   ================================================================ */
.report-container { padding: 28px; max-width: 900px; margin: 0 auto; }
.report-section {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
  overflow: hidden;
}
.report-section-header {
  padding: 16px 20px;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
  border-bottom: 1px solid var(--c-border);
  display: flex;
  align-items: center;
  gap: 10px;
}
.report-section-header svg { color: var(--c-text3); flex-shrink: 0; }
.report-section-body { padding: 16px 20px; }
.report-info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  font-size: 13px;
  border-bottom: 1px solid var(--c-border);
}
.report-info-row:last-child { border-bottom: none; }
.report-info-label { color: var(--c-text3); font-weight: 500; }
.report-info-value { color: var(--c-text); font-family: var(--font-mono); font-size: 12px; text-align: right; }
.log-viewer {
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  padding: 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 500px;
  overflow-y: auto;
  color: var(--c-text2);
}
.log-search {
  width: 100%;
  padding: 8px 12px;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  color: var(--c-text);
  font-size: 13px;
  margin-bottom: 10px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.log-search:focus {
  outline: none;
  border-color: var(--c-accent);
  box-shadow: 0 0 0 3px var(--c-accent-dim);
}
.plugin-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.plugin-tag {
  padding: 3px 10px;
  background: var(--c-surface2);
  border-radius: 20px;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--c-text2);
}

/* ================================================================
   Responsive
   ================================================================ */
@media (max-width: 768px) {
  .tests-layout { flex-direction: column; height: auto; }
  .tree-panel {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--c-border);
    max-height: 45vh;
  }
  .detail-panel { min-height: 50vh; padding: 20px 16px; }
  .counters { grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }
  .counter-card { padding: 16px; }
  .counter-card .value { font-size: 28px; }
  .charts-grid { grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
  .header { padding: 0 16px; }
  .tabs { padding: 0 16px; }
  .summary-container, .report-container { padding: 16px; }
  .info-grid { grid-template-columns: 1fr; gap: 4px 0; }
  .info-label { margin-top: 8px; }
}
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
/*__REPORT_DATA__*/

// ─── Utilities ───────────────────────────────────────────────────────
function el(tag, attrs, ...children) {
  const e = document.createElement(tag);
  if (attrs) Object.entries(attrs).forEach(([k,v]) => {
    if (k === 'className') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'role' || k === 'tabindex' || k.startsWith('aria-') || k.startsWith('data-'))
      e.setAttribute(k, v);
    else e.setAttribute(k, v);
  });
  children.flat().forEach(c => {
    if (c == null) return;
    e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  });
  return e;
}

const COLORS = {passed:'#22C55E',failed:'#EF4444',skipped:'#F59E0B',error:'#F97316'};
const LABELS = {passed:'Passed',failed:'Failed',skipped:'Skipped',error:'Error'};
const STATUSES = ['passed','failed','skipped','error'];

// SVG helper
function svgEl(tag, attrs) {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  if (attrs) Object.entries(attrs).forEach(([k,v]) => e.setAttribute(k, v));
  return e;
}

// ─── Aggregate helpers ───────────────────────────────────────────────
function aggTests(tests) {
  let p=0,f=0,s=0,e=0;
  tests.forEach(t => { p+=t.aggregate.passed; f+=t.aggregate.failed; s+=t.aggregate.skipped; e+=t.aggregate.errors; });
  return {passed:p,failed:f,skipped:s,error:e,total:p+f+s+e};
}

function buildTree(tests) {
  const root = {name:'root',children:{},tests:[]};
  tests.forEach(t => {
    const parts = t.aggregate.file.split('/');
    let node = root;
    parts.forEach(part => {
      if (!node.children[part]) node.children[part] = {name:part,children:{},tests:[]};
      node = node.children[part];
    });
    node.tests.push(t);
  });
  return root;
}

function nodeAgg(node) {
  let p=0,f=0,s=0,e=0;
  node.tests.forEach(t => { p+=t.aggregate.passed; f+=t.aggregate.failed; s+=t.aggregate.skipped; e+=t.aggregate.errors; });
  Object.values(node.children).forEach(c => {
    const a = nodeAgg(c);
    p+=a.passed; f+=a.failed; s+=a.skipped; e+=a.error;
  });
  return {passed:p,failed:f,skipped:s,error:e,total:p+f+s+e};
}

// ─── Donut chart ─────────────────────────────────────────────────────
function donutSVG(counts, size) {
  size = size || 130;
  const strokeW = 14;
  const gap = 3;
  const r = (size / 2) - strokeW / 2 - 4;
  const cx = size / 2, cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const total = counts.passed + counts.failed + counts.skipped + counts.error;

  const svg = svgEl('svg', {width: size, height: size, viewBox: `0 0 ${size} ${size}`});

  // Background track
  const track = svgEl('circle', {
    cx, cy, r, fill: 'none', stroke: 'rgba(255,255,255,0.04)', 'stroke-width': strokeW
  });
  svg.appendChild(track);

  if (total === 0) return svg;

  const segments = STATUSES.filter(k => counts[k] > 0);

  if (segments.length === 1) {
    const ring = svgEl('circle', {
      cx, cy, r, fill: 'none', stroke: COLORS[segments[0]],
      'stroke-width': strokeW, 'stroke-linecap': 'round', opacity: '0.9'
    });
    svg.appendChild(ring);
  } else {
    let offset = 0;
    const gapLen = (gap / 360) * circumference;
    const totalGap = segments.length * gapLen;
    const available = circumference - totalGap;

    segments.forEach(k => {
      const frac = counts[k] / total;
      const len = frac * available;
      const arc = svgEl('circle', {
        cx, cy, r, fill: 'none', stroke: COLORS[k],
        'stroke-width': strokeW,
        'stroke-dasharray': `${len} ${circumference - len}`,
        'stroke-dashoffset': `${-offset}`,
        'stroke-linecap': 'round',
        opacity: '0.9',
        transform: `rotate(-90 ${cx} ${cy})`
      });
      svg.appendChild(arc);
      offset += len + gapLen;
    });
  }

  // Center text
  const totalText = svgEl('text', {
    x: cx, y: cy - 2,
    'text-anchor': 'middle', 'dominant-baseline': 'middle',
    fill: '#E8ECF4', 'font-size': Math.round(size * 0.17),
    'font-weight': '700', 'font-family': "var(--font-mono)"
  });
  totalText.textContent = total;
  svg.appendChild(totalText);

  const label = svgEl('text', {
    x: cx, y: cy + Math.round(size * 0.13),
    'text-anchor': 'middle', 'dominant-baseline': 'middle',
    fill: '#5A6B84', 'font-size': Math.round(size * 0.075),
    'font-weight': '500', 'letter-spacing': '0.06em'
  });
  label.textContent = 'TESTS';
  svg.appendChild(label);

  return svg;
}

function legendEl(counts) {
  return el('div', {className:'chart-legend'},
    STATUSES.filter(k => counts[k] > 0).map(k =>
      el('span', null,
        el('span', {className:'legend-dot', style:`background:${COLORS[k]}`}),
        `${counts[k]} ${LABELS[k]}`
      )
    )
  );
}

// ─── Summary Tab ─────────────────────────────────────────────────────
function renderSummary() {
  const panel = document.getElementById('tab-summary');
  const container = el('div', {className:'summary-container'});
  const agg = aggTests(DATA.tests);

  // Count retried tests
  let retriedCount = 0;
  DATA.tests.forEach(t => t.runs.forEach(r => { if (r.retries && r.retries.attempts > 0) retriedCount++; }));

  // Counters
  const counterDefs = [{k:'passed',l:'Passed'},{k:'failed',l:'Failed'},{k:'skipped',l:'Skipped'},{k:'error',l:'Errors'}];
  if (DATA.retries_enabled) counterDefs.push({k:'retried',l:'Retried'});
  counterDefs.push({k:'total',l:'Total'});
  const counterData = Object.assign({}, agg, {retried: retriedCount});
  const counters = el('div', {className:'counters'},
    counterDefs.map(c => el('div', {className:`counter-card ${c.k}`},
      el('div', {className:'value'}, String(counterData[c.k])),
      el('div', {className:'label'}, c.l)
    ))
  );
  container.appendChild(counters);

  // Overall donut
  const overallSection = el('div', {className:'charts-section'},
    el('div', {className:'charts-section-title'}, 'Overall'),
    el('div', {className:'charts-grid'},
      el('div', {className:'chart-card'}, el('h3', null, 'All Tests'), donutSVG(agg, 150), legendEl(agg))
    )
  );
  container.appendChild(overallSection);

  // Per top-level group
  const tree = buildTree(DATA.tests);
  const topGroups = Object.entries(tree.children);
  if (topGroups.length > 0) {
    const groupCards = topGroups.map(([name, node]) => {
      const a = nodeAgg(node);
      return el('div', {className:'chart-card', onClick:()=>navigateToGroup(name)},
        el('h3', null, name), donutSVG(a, 130), legendEl(a)
      );
    });
    const topSection = el('div', {className:'charts-section'},
      el('div', {className:'charts-section-title'}, 'Top-Level Groups'),
      el('div', {className:'charts-grid'}, groupCards)
    );
    container.appendChild(topSection);

    // Per-feature donuts
    topGroups.forEach(([groupName, groupNode]) => {
      const features = Object.entries(groupNode.children);
      if (features.length > 0) {
        const featureCards = features.map(([fname, fnode]) => {
          const a = nodeAgg(fnode);
          return el('div', {className:'chart-card', onClick:()=>navigateToGroup(groupName+'/'+fname)},
            el('h3', null, fname), donutSVG(a, 110), legendEl(a)
          );
        });
        const section = el('div', {className:'charts-section'},
          el('div', {className:'charts-section-title'}, groupName + ' \u2014 Features'),
          el('div', {className:'charts-grid'}, featureCards)
        );
        container.appendChild(section);
      }
    });
  }
  panel.appendChild(container);
}

function navigateToGroup(path) {
  switchTab('tests');
  const parts = path.split('/');
  let node = document.querySelector('.tree-content');
  parts.forEach(part => {
    if (!node) return;
    const rows = node.querySelectorAll(':scope > .tree-node > .tree-row');
    rows.forEach(row => {
      if (row.querySelector('.tree-name')?.textContent === part) {
        const parent = row.parentElement;
        if (parent) parent.classList.add('expanded');
        node = parent?.querySelector('.tree-children');
      }
    });
  });
}

// ─── Tests Tab ───────────────────────────────────────────────────────
let activeFilters = new Set(STATUSES);
let selectedTest = null;
let selectedRun = null;

function renderTests() {
  const panel = document.getElementById('tab-tests');
  const layout = el('div', {className:'tests-layout'});

  // Left panel
  const treePanel = el('div', {className:'tree-panel'});
  const controls = el('div', {className:'tree-controls'});

  const searchBox = el('div', {className:'search-box'});
  const searchIconSvg = el('span', {className:'search-icon'});
  searchIconSvg.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>';
  const searchInput = el('input', {className:'search-input', placeholder:'Search tests...', type:'text'});
  let searchTimer;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => filterTree(searchInput.value), 80);
  });
  searchBox.appendChild(searchIconSvg);
  searchBox.appendChild(searchInput);
  controls.appendChild(searchBox);

  // Filters + expand/collapse row
  const controlsRow = el('div', {className:'tree-controls-row'});
  const filters = el('div', {className:'filter-toggles'});
  STATUSES.forEach(status => {
    const btn = el('button', {className:`filter-btn ${status} active`, 'data-status':status}, LABELS[status]);
    btn.addEventListener('click', () => toggleFilter(status, btn));
    filters.appendChild(btn);
  });
  controlsRow.appendChild(filters);

  // Expand all button
  const expandBtn = el('button', {className:'tree-expand-btn', title:'Expand all'});
  expandBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="7 13 12 18 17 13"/><polyline points="7 6 12 11 17 6"/></svg>';
  expandBtn.addEventListener('click', () => {
    treeContent.querySelectorAll('.tree-node').forEach(n => n.classList.add('expanded'));
  });
  controlsRow.appendChild(expandBtn);

  // Collapse all button
  const collapseBtn = el('button', {className:'tree-expand-btn', title:'Collapse all'});
  collapseBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="17 11 12 6 7 11"/><polyline points="17 18 12 13 7 18"/></svg>';
  collapseBtn.addEventListener('click', () => {
    treeContent.querySelectorAll('.tree-node').forEach(n => n.classList.remove('expanded'));
  });
  controlsRow.appendChild(collapseBtn);

  controls.appendChild(controlsRow);
  treePanel.appendChild(controls);

  const treeContent = el('div', {className:'tree-content'});
  const tree = buildTree(DATA.tests);
  Object.entries(tree.children).forEach(([name, node]) => {
    treeContent.appendChild(renderTreeNode(name, node, 0));
  });
  treePanel.appendChild(treeContent);

  // Right panel
  const detailPanel = el('div', {className:'detail-panel'});
  detailPanel.innerHTML = `<div class="detail-empty">
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>
    <span>Select a test to view details</span>
  </div>`;

  layout.appendChild(treePanel);
  layout.appendChild(detailPanel);
  panel.appendChild(layout);
}

function renderTreeNode(name, node, depth) {
  const hasChildren = Object.keys(node.children).length > 0 || node.tests.length > 0;
  const agg = nodeAgg(node);
  const container = el('div', {className:'tree-node'});

  const row = el('div', {className:'tree-row', style:`padding-left:${16 + depth * 16}px`});

  // Chevron icon for expandable nodes
  const icon = el('span', {className:'tree-icon'});
  if (hasChildren) {
    icon.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>';
  } else {
    icon.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="4"/></svg>';
  }

  const nameEl = el('span', {className:'tree-name'}, name);

  // Colored count badges
  const badges = el('span', {className:'tree-badges'});
  if (agg.passed) badges.appendChild(el('span', {className:'tree-badge passed'}, String(agg.passed)));
  if (agg.failed) badges.appendChild(el('span', {className:'tree-badge failed'}, String(agg.failed)));
  if (agg.skipped) badges.appendChild(el('span', {className:'tree-badge skipped'}, String(agg.skipped)));
  if (agg.error) badges.appendChild(el('span', {className:'tree-badge error'}, String(agg.error)));
  if (!agg.passed && !agg.failed && !agg.skipped && !agg.error) {
    badges.appendChild(el('span', {className:'tree-badge count'}, '0'));
  }

  row.appendChild(icon);
  row.appendChild(nameEl);
  row.appendChild(badges);
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    container.classList.toggle('expanded');
  });
  container.appendChild(row);

  if (hasChildren) {
    const children = el('div', {className:'tree-children'});
    Object.entries(node.children).forEach(([cname, cnode]) => {
      children.appendChild(renderTreeNode(cname, cnode, depth + 1));
    });
    node.tests.forEach(test => {
      children.appendChild(renderTestLeaf(test, depth + 1));
    });
    container.appendChild(children);
  }
  container._agg = agg;
  return container;
}

function renderTestLeaf(test, depth) {
  const container = el('div', {className:'tree-node'});
  const fn = test.aggregate.function_name;
  const outcome = getOverallOutcome(test);

  const row = el('div', {className:'tree-row', style:`padding-left:${16 + depth * 16}px`});
  const dot = el('span', {className:`status-dot ${outcome}`});
  const nameEl = el('span', {className:'tree-name'}, fn);
  const badges = el('span', {className:'tree-badges'});
  if (test.aggregate.total_runs > 1) {
    badges.appendChild(el('span', {className:'tree-badge count'}, String(test.aggregate.total_runs)));
  }
  row.appendChild(dot);
  row.appendChild(nameEl);
  row.appendChild(badges);
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    document.querySelectorAll('.tree-row.selected').forEach(r => r.classList.remove('selected'));
    row.classList.add('selected');
    showTestDetail(test);
  });
  container.appendChild(row);
  container._test = test;
  return container;
}

function getOverallOutcome(test) {
  if (test.aggregate.failed > 0 || test.aggregate.errors > 0) return 'failed';
  if (test.aggregate.skipped > 0 && test.aggregate.passed === 0) return 'skipped';
  return 'passed';
}

function showTestDetail(test) {
  selectedTest = test;
  const panel = document.querySelector('.detail-panel');
  panel.innerHTML = '';

  const outcome = getOverallOutcome(test);
  const header = el('div', {className:'detail-header'});
  const headerTop = el('div', {className:'detail-header-top'});
  const outcomeBadge = el('span', {className:'detail-header-outcome ' + outcome},
    el('span', {className:'status-dot ' + outcome}),
    outcome
  );
  headerTop.appendChild(el('h2', null, test.aggregate.function_name));
  headerTop.appendChild(outcomeBadge);
  header.appendChild(headerTop);
  header.appendChild(el('div', {className:'file-path'}, test.aggregate.file));

  // Stats row
  const agg = test.aggregate;
  const stats = el('div', {className:'detail-header-stats'});
  stats.appendChild(el('span', {className:'detail-header-stat'}, el('strong', null, String(agg.total_runs)), ' runs'));
  stats.appendChild(el('span', {className:'detail-header-stat'}, el('strong', null, agg.total_duration_seconds.toFixed(2) + 's'), ' total'));
  if (agg.passed) stats.appendChild(el('span', {className:'detail-header-stat'},
    el('span', {className:'status-dot passed'}), el('strong', null, String(agg.passed)), ' passed'));
  if (agg.failed) stats.appendChild(el('span', {className:'detail-header-stat'},
    el('span', {className:'status-dot failed'}), el('strong', null, String(agg.failed)), ' failed'));
  if (agg.skipped) stats.appendChild(el('span', {className:'detail-header-stat'},
    el('span', {className:'status-dot skipped'}), el('strong', null, String(agg.skipped)), ' skipped'));
  header.appendChild(stats);
  panel.appendChild(header);

  // Run filter toggles
  const runFilters = el('div', {className:'run-filters'});
  const filterRow = el('div', {className:'filter-toggles'});
  STATUSES.forEach(s => {
    const count = test.runs.filter(r => r.outcome === s).length;
    if (count === 0) return;
    const btn = el('button', {className:`filter-btn ${s} active`}, `${LABELS[s]} (${count})`);
    btn.addEventListener('click', () => {
      btn.classList.toggle('active');
      refreshRunPills(test, panel);
    });
    filterRow.appendChild(btn);
  });
  runFilters.appendChild(filterRow);
  panel.appendChild(runFilters);

  // Run pills
  const pillsContainer = el('div', {className:'run-pills', id:'run-pills'});
  panel.appendChild(pillsContainer);

  // Run detail
  const runDetailContainer = el('div', {id:'run-detail'});
  panel.appendChild(runDetailContainer);

  refreshRunPills(test, panel);
  if (test.runs.length > 0) showRunDetail(test.runs[0]);
}

function refreshRunPills(test, panel) {
  const container = document.getElementById('run-pills');
  if (!container) return;
  container.innerHTML = '';

  const activeStatuses = new Set();
  panel.querySelectorAll('.run-filters .filter-btn.active').forEach(b => {
    const txt = b.textContent.split(' ')[0].toLowerCase();
    STATUSES.forEach(s => { if (LABELS[s].toLowerCase() === txt) activeStatuses.add(s); });
  });
  if (activeStatuses.size === 0) STATUSES.forEach(s => activeStatuses.add(s));

  const filtered = test.runs.filter(r => activeStatuses.has(r.outcome));
  const MAX = 20;
  const shown = filtered.slice(0, MAX);
  const rest = filtered.slice(MAX);

  shown.forEach(run => {
    const pillText = run.run_id + (run.parametrize_id ? ` [${run.parametrize_id}]` : '');
    const pill = el('button', {
      className: `run-pill ${run.outcome}${selectedRun === run ? ' selected' : ''}`
    }, pillText);
    if (run.retries && run.retries.attempts > 0) {
      const badge = el('span', {className:'retry-badge'}, '\u21bb' + run.retries.attempts);
      pill.appendChild(badge);
    }
    pill.addEventListener('click', () => {
      container.querySelectorAll('.run-pill').forEach(p => p.classList.remove('selected'));
      pill.classList.add('selected');
      showRunDetail(run);
    });
    container.appendChild(pill);
  });

  if (rest.length > 0) {
    const rc = {passed:0,failed:0,skipped:0,error:0};
    rest.forEach(r => rc[r.outcome]++);
    const micro = `${rc.passed}p/${rc.failed}f/${rc.skipped}s/${rc.error}e`;
    const btn = el('button', {className:'show-more-btn'}, `Show more (${micro})`);
    let expanded = false;
    btn.addEventListener('click', () => {
      if (!expanded) {
        rest.forEach(run => {
          const pill = el('button', {className:`run-pill ${run.outcome}`}, run.run_id);
          pill.addEventListener('click', () => showRunDetail(run));
          container.insertBefore(pill, btn);
        });
        btn.textContent = 'Collapse';
        expanded = true;
      } else {
        while (container.children.length > MAX + 1) {
          container.removeChild(container.children[MAX]);
        }
        btn.textContent = `Show more (${micro})`;
        expanded = false;
      }
    });
    container.appendChild(btn);
  }
}

function showRunDetail(run) {
  selectedRun = run;
  // Update pill selection
  document.querySelectorAll('#run-pills .run-pill').forEach(p => {
    p.classList.toggle('selected', p.textContent.startsWith(run.run_id));
  });

  const container = document.getElementById('run-detail');
  if (!container) return;
  container.innerHTML = '';

  const subTabs = el('div', {className:'sub-tabs'});
  const tabNames = ['Summary','Procedure','Artifacts'];
  if (run.check_results && run.check_results.length > 0) {
    tabNames.splice(2, 0, 'Checks');
  }
  if (run.retries && run.retry_attempts && run.retry_attempts.length > 0) {
    tabNames.push('Retries');
  }
  tabNames.forEach((name, i) => {
    const btn = el('button', {className:`sub-tab-btn${i===0?' active':''}`}, name);
    btn.addEventListener('click', () => {
      subTabs.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      showSubTab(name.toLowerCase(), run);
    });
    subTabs.appendChild(btn);
  });
  container.appendChild(subTabs);

  const content = el('div', {className:'run-detail-content', id:'sub-tab-content'});
  container.appendChild(content);
  showSubTab('summary', run);
}

function showSubTab(tab, run) {
  const content = document.getElementById('sub-tab-content');
  if (!content) return;
  content.innerHTML = '';

  if (tab === 'summary') {
    const grid = el('div', {className:'info-grid'});
    const addRow = (label, value) => {
      grid.appendChild(el('span', {className:'info-label'}, label));
      if (typeof value === 'string') {
        grid.appendChild(el('span', {className:'info-value'}, value));
      } else {
        grid.appendChild(value);
      }
    };

    const outcomeEl = el('span', {className:'info-value', style:'display:flex;align-items:center;gap:6px'},
      el('span', {className:`status-dot ${run.outcome}`}),
      run.outcome.charAt(0).toUpperCase() + run.outcome.slice(1)
    );
    addRow('Outcome', outcomeEl);
    addRow('Duration', run.duration.toFixed(4) + 's');
    addRow('Run ID', run.run_id);
    if (run.parametrize_id) addRow('Parametrize ID', run.parametrize_id);
    content.appendChild(grid);

    // Parameters table
    const paramKeys = Object.keys(run.params || {});
    if (paramKeys.length > 0) {
      const table = el('table', {className:'params-table'},
        el('thead', null, el('tr', null, el('th', null, 'Name'), el('th', null, 'Type'), el('th', null, 'Value'))),
        el('tbody', null, ...paramKeys.map(k =>
          el('tr', null, el('td', null, k), el('td', null, run.params[k].type), el('td', null, run.params[k].value))
        ))
      );
      content.appendChild(table);
    }

    // Phase logs as horizontal tabs
    const phases = ['setup','call','teardown'];
    const availablePhases = phases.filter(w => run.phases[w]);
    if (availablePhases.length > 0) {
      const phaseBar = el('div', {className:'phase-tabs-bar'});
      const phasePanels = [];

      availablePhases.forEach((when, idx) => {
        const phase = run.phases[when];
        const btn = el('button', {className:`phase-tab-btn${idx===0?' active':''}`},
          el('span', {className:`status-dot ${phase.outcome}`}),
          when.charAt(0).toUpperCase() + when.slice(1),
          el('span', {className:'phase-meta'}, phase.duration.toFixed(4) + 's')
        );

        const panel = el('div', {className:`phase-tab-panel${idx===0?' active':''}`});
        const hasEntries = phase.entries && phase.entries.length > 0;
        if (hasEntries || phase.longrepr) {
          if (hasEntries) {
            panel.appendChild(renderLogEntries(phase.entries));
          }
          if (phase.longrepr) {
            const body = el('div', {className:'phase-tab-body'});
            body.textContent = phase.longrepr;
            panel.appendChild(body);
          }
        } else {
          panel.appendChild(el('div', {className:'phase-tab-empty'}, 'No output'));
        }

        btn.addEventListener('click', () => {
          phaseBar.querySelectorAll('.phase-tab-btn').forEach(b => b.classList.remove('active'));
          phasePanels.forEach(p => p.classList.remove('active'));
          btn.classList.add('active');
          panel.classList.add('active');
        });

        phaseBar.appendChild(btn);
        phasePanels.push(panel);
      });

      content.appendChild(phaseBar);
      phasePanels.forEach(p => content.appendChild(p));
    }

  } else if (tab === 'procedure') {
    const proc = run.procedure || {steps:[]};
    if (proc.steps.length === 0) {
      content.appendChild(el('div', {className:'procedure-empty'}, 'No procedure defined'));
    } else {
      content.appendChild(renderProcedure(proc));
    }

  } else if (tab === 'checks') {
    const checks = run.check_results || [];
    if (checks.length === 0) {
      content.appendChild(el('div', {style:'color:var(--c-text3);font-size:13px;padding:8px 0'}, 'No verification checks.'));
    } else {
      content.appendChild(renderCheckResults(checks));
    }

  } else if (tab === 'artifacts') {
    const artifacts = run.artifacts || [];
    if (artifacts.length === 0) {
      content.appendChild(el('div', {style:'color:var(--c-text3);font-size:13px;padding:8px 0'},
        'No artifacts collected for this run.'
      ));
    } else {
      const imageExts = ['.png','.jpg','.jpeg','.gif','.webp','.svg','.bmp'];
      const htmlExts = ['.html','.htm'];
      const images = artifacts.filter(a => imageExts.some(e => a.name.toLowerCase().endsWith(e)));
      const htmlFiles = artifacts.filter(a => htmlExts.some(e => a.name.toLowerCase().endsWith(e)));
      const others = artifacts.filter(a =>
        !imageExts.some(e => a.name.toLowerCase().endsWith(e)) &&
        !htmlExts.some(e => a.name.toLowerCase().endsWith(e))
      );

      // HTML artifacts (rendered inline as iframes)
      if (htmlFiles.length > 0) {
        htmlFiles.forEach(a => {
          const label = el('div', {style:'font-size:12px;font-weight:600;color:var(--c-text2);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.04em'}, a.name);
          content.appendChild(label);
          if (a.data_uri) {
            const iframe = el('iframe', {className:'artifact-html-frame', src:a.data_uri, sandbox:'allow-same-origin', style:'pointer-events:auto'});
            // Auto-resize iframe to content
            iframe.addEventListener('load', () => {
              try {
                const h = iframe.contentDocument.documentElement.scrollHeight;
                iframe.style.height = Math.min(h + 20, 600) + 'px';
              } catch(e) {}
            });
            content.appendChild(iframe);
          }
        });
      }

      // Image artifacts
      if (images.length > 0) {
        const grid = el('div', {className:'artifact-grid'});
        images.forEach(a => {
          const card = el('div', {className:'artifact-card'});
          if (a.data_uri) {
            const img = el('img', {className:'artifact-thumb', src:a.data_uri, alt:a.name, loading:'lazy'});
            card.appendChild(img);
            card.addEventListener('click', () => openLightbox(a.data_uri, a.name));
          }
          card.appendChild(el('div', {className:'artifact-info'},
            el('div', {className:'artifact-name'}, a.name),
            el('div', {className:'artifact-size'}, formatSize(a.size))
          ));
          grid.appendChild(card);
        });
        content.appendChild(grid);
      }

      // Other artifacts
      if (others.length > 0) {
        const list = el('div', {style:'display:flex;flex-direction:column;gap:8px;margin-top:' + (images.length > 0 || htmlFiles.length > 0 ? '16px' : '0')});
        others.forEach(a => {
          const card = el('div', {className:'artifact-file-card'});
          const icon = el('span', {className:'artifact-file-icon'});
          icon.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
          card.appendChild(icon);
          card.appendChild(el('div', null,
            el('div', {className:'artifact-name'}, a.name),
            el('div', {className:'artifact-size'}, formatSize(a.size))
          ));
          list.appendChild(card);
        });
        content.appendChild(list);
      }
    }
  } else if (tab === 'retries') {
    const retries = run.retries || {};
    const attempts = run.retry_attempts || [];
    if (attempts.length === 0) {
      content.appendChild(el('div', {style:'color:var(--c-text3);font-size:13px;padding:8px 0'}, 'No retries for this run.'));
    } else {
      const section = el('div', {className:'retry-section'});
      // Original failure card
      const origCard = el('div', {className:'retry-original'});
      const origHeader = el('div', {className:'retry-original-header'},
        el('span', {className:'status-dot failed'}),
        'Original Failure'
      );
      origCard.appendChild(origHeader);
      if (run.phases && run.phases.call && run.phases.call.longrepr) {
        const body = el('div', {className:'phase-tab-body'});
        body.textContent = run.phases.call.longrepr;
        origCard.appendChild(body);
      }
      if (run.phases && run.phases.call) {
        origCard.appendChild(el('div', {style:'font-size:11px;color:var(--c-text3);margin-top:8px'},
          'Duration: ' + run.phases.call.duration.toFixed(4) + 's'));
      }
      section.appendChild(origCard);

      // Retry attempt cards
      attempts.forEach((attempt, idx) => {
        const isLast = idx === attempts.length - 1;
        const callPhase = attempt.phases?.call;
        const attemptOutcome = callPhase?.outcome || 'error';
        const card = el('div', {className:`retry-card${isLast?' expanded':''}`});
        const header = el('div', {className:'retry-card-header'},
          el('span', {className:`status-dot ${attemptOutcome}`}),
          `Retry ${attempt.attempt}`,
          el('span', {style:'margin-left:auto;font-size:11px;color:var(--c-text3)'},
            attemptOutcome.charAt(0).toUpperCase() + attemptOutcome.slice(1))
        );
        header.addEventListener('click', () => card.classList.toggle('expanded'));
        card.appendChild(header);

        const body = el('div', {className:'retry-card-body'});
        // Phase logs
        const phases = ['setup','call','teardown'];
        const availP = phases.filter(w => attempt.phases?.[w]);
        if (availP.length > 0) {
          const pBar = el('div', {className:'phase-tabs-bar'});
          const pPanels = [];
          availP.forEach((w, pi) => {
            const ph = attempt.phases[w];
            const pbtn = el('button', {className:`phase-tab-btn${pi===0?' active':''}`},
              el('span', {className:`status-dot ${ph.outcome}`}),
              w.charAt(0).toUpperCase() + w.slice(1),
              el('span', {className:'phase-meta'}, (ph.duration_seconds||0).toFixed(4) + 's')
            );
            const ppanel = el('div', {className:`phase-tab-panel${pi===0?' active':''}`});
            if (ph.entries && ph.entries.length > 0) ppanel.appendChild(renderLogEntries(ph.entries));
            if (ph.longrepr) {
              const b = el('div', {className:'phase-tab-body'}); b.textContent = ph.longrepr; ppanel.appendChild(b);
            }
            if (!ph.entries?.length && !ph.longrepr) ppanel.appendChild(el('div', {className:'phase-tab-empty'}, 'No output'));
            pbtn.addEventListener('click', () => {
              pBar.querySelectorAll('.phase-tab-btn').forEach(b => b.classList.remove('active'));
              pPanels.forEach(p => p.classList.remove('active'));
              pbtn.classList.add('active'); ppanel.classList.add('active');
            });
            pBar.appendChild(pbtn); pPanels.push(ppanel);
          });
          body.appendChild(pBar);
          pPanels.forEach(p => body.appendChild(p));
        }
        // Procedure
        if (attempt.procedure && attempt.procedure.steps && attempt.procedure.steps.length > 0) {
          body.appendChild(el('h4', {style:'margin-top:12px;font-size:12px;color:var(--c-text2)'}, 'Procedure'));
          body.appendChild(renderProcedure(attempt.procedure));
        }
        card.appendChild(body);
        section.appendChild(card);
      });
      content.appendChild(section);
    }
  }
}

// ─── Render helpers ─────────────────────────────────────────────────
function renderLogEntries(entries) {
  const container = el('div', {className:'log-entries'});
  entries.forEach(e => {
    const row = el('div', {className:'log-entry', 'data-level': e.level || ''});
    row.appendChild(el('span', {className:'log-entry-time'}, e.t ? e.t.split('T')[1]?.replace('Z','') || '' : ''));
    const lvl = el('span', {className:`log-entry-level ${e.level || ''}`}); lvl.textContent = e.level || ''; row.appendChild(lvl);
    row.appendChild(el('span', {className:'log-entry-source'}, (e.source || []).join('.')));
    row.appendChild(el('span', {className:'log-entry-msg'}, e.msg || ''));
    if (e.data) {
      const dataEl = el('div', {className:'log-entry-data'});
      dataEl.textContent = JSON.stringify(e.data, null, 2);
      row.appendChild(dataEl);
    }
    if (e.exc) {
      const excEl = el('div', {className:'log-entry-exc'});
      excEl.textContent = e.exc.type + ': ' + e.exc.msg + (e.exc.tb ? '\n' + e.exc.tb : '');
      row.appendChild(excEl);
    }
    container.appendChild(row);
  });
  return container;
}

function _appendCheckInline(row, check) {
  if (!check) return;
  const desc = check.description || '';
  if (desc) {
    row.appendChild(el('span', {className:'procedure-check-desc'}, '\u2014 ' + desc));
  }
}

function renderProcedure(proc) {
  const list = el('div', {className:'procedure-list'});
  (proc.steps || []).forEach(step => {
    const s = el('div', {className:'procedure-step'});
    const header = el('div', {className:'procedure-step-header'},
      el('span', {className:`status-dot ${step.outcome || 'passed'}`}),
      el('span', {className:'procedure-step-number'}, step.number + '.'),
      el('span', {className:'procedure-step-desc'}, step.description)
    );
    _appendCheckInline(header, step.check);
    if (step.duration_seconds > 0) {
      header.appendChild(el('span', {className:'procedure-step-duration'}, step.duration_seconds.toFixed(2) + 's'));
    }
    s.appendChild(header);
    if (step.exc) {
      const exc = el('div', {className:'procedure-step-exc'});
      exc.textContent = step.exc.type + ': ' + step.exc.msg;
      s.appendChild(exc);
    }
    if (step.substeps && step.substeps.length > 0) {
      const subs = el('div', {className:'procedure-substeps'});
      step.substeps.forEach(sub => {
        const subEl = el('div', {className:'procedure-substep'},
          el('span', {className:`status-dot ${sub.outcome || 'passed'}`}),
          el('span', {className:'procedure-step-number'}, sub.number),
          el('span', {className:'procedure-step-desc'}, sub.description)
        );
        _appendCheckInline(subEl, sub.check);
        if (sub.duration_seconds > 0) {
          subEl.appendChild(el('span', {className:'procedure-step-duration'}, sub.duration_seconds.toFixed(2) + 's'));
        }
        if (sub.exc) {
          const excEl = el('div', {className:'procedure-step-exc'});
          excEl.textContent = sub.exc.type + ': ' + sub.exc.msg;
          subEl.appendChild(excEl);
        }
        subs.appendChild(subEl);
      });
      s.appendChild(subs);
    }
    list.appendChild(s);
  });
  return list;
}

function renderCheckResults(checks) {
  const container = el('div');
  // Summary bar
  const passed = checks.filter(c => c.passed).length;
  const failed = checks.filter(c => !c.passed).length;
  const summary = el('div', {className:'checks-summary'});
  summary.appendChild(el('span', {className:'checks-count'},
    el('span', {className:'status-dot passed'}), passed + ' passed'));
  if (failed > 0) {
    summary.appendChild(el('span', {className:'checks-count'},
      el('span', {className:'status-dot failed'}), failed + ' failed'));
  }
  summary.appendChild(el('span', null, checks.length + ' total'));
  container.appendChild(summary);

  const cards = el('div', {className:'check-cards'});
  checks.forEach((check, idx) => {
    const status = check.passed ? 'passed' : 'failed';
    const card = el('div', {className:`check-card ${status}`});

    const header = el('div', {className:'check-card-header'});
    header.appendChild(el('span', {className:`status-dot ${status}`}));
    header.appendChild(el('span', {className:'check-name'}, check.name || ('Check #' + (idx + 1))));
    if (check.description) {
      header.appendChild(el('span', {className:'check-desc'}, check.description));
    }
    header.appendChild(el('span', {className:'check-type-badge'}, check.check_type || ''));
    header.addEventListener('click', () => card.classList.toggle('expanded'));
    card.appendChild(header);

    const body = el('div', {className:'check-card-body'});
    const detail = el('div', {className:'check-card-detail'});

    // Add relevant fields based on check_type
    const fields = [
      ['actual', 'Actual'], ['expected', 'Expected'],
      ['threshold', 'Threshold'], ['low', 'Low'], ['high', 'High'],
      ['abs_tol', 'Abs tolerance'], ['rel_tol', 'Rel tolerance'],
      ['units', 'Units'], ['inclusive', 'Inclusive'],
      ['expected_type', 'Expected type'], ['actual_length', 'Actual length'],
      ['haystack', 'Haystack'], ['needle', 'Needle'], ['pattern', 'Pattern'],
      ['msg', 'Message'],
    ];
    fields.forEach(([key, label]) => {
      if (check[key] !== undefined && check[key] !== null) {
        detail.appendChild(el('span', {className:'label'}, label));
        const v = typeof check[key] === 'object' ? JSON.stringify(check[key]) : String(check[key]);
        detail.appendChild(el('span', {className:'value'}, v));
      }
    });

    body.appendChild(detail);
    card.appendChild(body);
    cards.appendChild(card);
  });
  container.appendChild(cards);
  return container;
}

function formatSize(bytes) {
  if (bytes == null) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function openLightbox(src, alt) {
  const overlay = el('div', {className:'lightbox-overlay'});
  overlay.appendChild(el('img', {src, alt}));
  overlay.addEventListener('click', () => overlay.remove());
  document.addEventListener('keydown', function esc(e) {
    if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', esc); }
  });
  document.body.appendChild(overlay);
}

function filterTree(query) {
  const q = query.toLowerCase();
  document.querySelectorAll('.tree-node').forEach(node => {
    const test = node._test;
    if (test) {
      const match = !q || test.aggregate.function_name.toLowerCase().includes(q)
        || test.aggregate.file.toLowerCase().includes(q)
        || test.base_nodeid?.toLowerCase().includes(q);
      node.style.display = match ? '' : 'none';
      // Auto-expand parents if match
      if (match && q) {
        let parent = node.parentElement;
        while (parent) {
          if (parent.classList?.contains('tree-node')) parent.classList.add('expanded');
          parent = parent.parentElement;
        }
      }
    }
  });
}

function toggleFilter(status, btn) {
  btn.classList.toggle('active');
  if (activeFilters.has(status)) activeFilters.delete(status);
  else activeFilters.add(status);
  document.querySelectorAll('.tree-node').forEach(node => {
    const test = node._test;
    if (test) {
      const outcome = getOverallOutcome(test);
      const show = activeFilters.size === 0 || activeFilters.has(outcome);
      node.style.display = show ? '' : 'none';
    }
  });
}

// ─── Session Logs Tab ────────────────────────────────────────────────
function renderSessionLogs() {
  const panel = document.getElementById('tab-session-logs');
  const container = el('div', {className:'session-log-container'});
  const entries = (DATA.session_log && DATA.session_log.entries) || [];
  if (entries.length === 0) {
    container.appendChild(el('div', {className:'session-log-empty'}, 'No session logs recorded'));
    panel.appendChild(container);
    return;
  }
  // Build tree from source paths
  const tree = {};
  entries.forEach(e => {
    const src = e.source || [];
    if (src.length === 0) {
      if (!tree['_root']) tree['_root'] = {entries:[], children:{}};
      tree['_root'].entries.push(e);
    } else {
      const top = src[0];
      if (!tree[top]) tree[top] = {entries:[], children:{}};
      if (src.length === 1) {
        tree[top].entries.push(e);
      } else {
        const child = src[1];
        if (!tree[top].children[child]) tree[top].children[child] = [];
        tree[top].children[child].push(e);
      }
    }
  });

  // ── Toolbar ──
  const toolbar = el('div', {className:'session-log-toolbar'});

  // Search with icon
  const searchWrap = el('div', {className:'session-log-search-wrap'});
  const searchSvg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  searchSvg.setAttribute('width','14'); searchSvg.setAttribute('height','14');
  searchSvg.setAttribute('viewBox','0 0 24 24'); searchSvg.setAttribute('fill','none');
  searchSvg.setAttribute('stroke','currentColor'); searchSvg.setAttribute('stroke-width','2');
  searchSvg.setAttribute('stroke-linecap','round');
  searchSvg.innerHTML = '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>';
  const search = el('input', {className:'session-log-search', type:'text', placeholder:'Search session logs...'});
  searchWrap.appendChild(searchSvg);
  searchWrap.appendChild(search);
  toolbar.appendChild(searchWrap);

  // Level filter toggle buttons
  const LEVELS = ['DEBUG','INFO','WARNING','ERROR','CRITICAL'];
  const activeLevels = new Set(LEVELS);
  const levelFilters = el('div', {className:'session-log-level-filters'});
  LEVELS.forEach(lvl => {
    const count = entries.filter(e => e.level === lvl).length;
    if (count === 0) return;
    const btn = el('button', {className:'session-log-level-btn ' + lvl + ' active'}, lvl + ' (' + count + ')');
    btn.addEventListener('click', () => {
      btn.classList.toggle('active');
      if (btn.classList.contains('active')) activeLevels.add(lvl);
      else activeLevels.delete(lvl);
      applyFilters();
    });
    levelFilters.appendChild(btn);
  });
  toolbar.appendChild(levelFilters);

  // Expand / Collapse all
  const actions = el('div', {className:'session-log-actions'});
  const expandAllBtn = el('button', {className:'session-log-action-btn'}, 'Expand all');
  const collapseAllBtn = el('button', {className:'session-log-action-btn'}, 'Collapse all');
  expandAllBtn.addEventListener('click', () => {
    treeEl.querySelectorAll('.session-log-section').forEach(s => s.classList.add('expanded'));
  });
  collapseAllBtn.addEventListener('click', () => {
    treeEl.querySelectorAll('.session-log-section').forEach(s => s.classList.remove('expanded'));
  });
  actions.appendChild(expandAllBtn);
  actions.appendChild(collapseAllBtn);
  toolbar.appendChild(actions);

  container.appendChild(toolbar);

  // ── Helpers ──
  function levelCounts(arr) {
    const counts = {};
    arr.forEach(e => { counts[e.level] = (counts[e.level] || 0) + 1; });
    return counts;
  }
  function levelPills(counts) {
    const wrap = el('div', {className:'session-log-section-levels'});
    LEVELS.forEach(lvl => {
      if (!counts[lvl]) return;
      wrap.appendChild(el('span', {className:'session-log-level-pill ' + lvl}, counts[lvl] + ' ' + lvl));
    });
    return wrap;
  }
  function chevronSvg() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('class','session-log-chevron');
    svg.setAttribute('width','16'); svg.setAttribute('height','16');
    svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('fill','none');
    svg.setAttribute('stroke','currentColor'); svg.setAttribute('stroke-width','2');
    svg.setAttribute('stroke-linecap','round'); svg.setAttribute('stroke-linejoin','round');
    svg.innerHTML = '<polyline points="9 18 15 12 9 6"/>';
    return svg;
  }

  // ── Tree ──
  const treeEl = el('div', {className:'session-log-tree'});
  Object.entries(tree).forEach(([name, data]) => {
    if (name === '_root') {
      const rootDiv = el('div', {className:'session-log-root-entries'});
      rootDiv.appendChild(renderLogEntries(data.entries));
      treeEl.appendChild(rootDiv);
      return;
    }
    // Collect all entries for this top-level source (own + children)
    const allEntries = data.entries.slice();
    Object.values(data.children).forEach(arr => arr.forEach(e => allEntries.push(e)));
    const counts = levelCounts(allEntries);

    const section = el('div', {className:'session-log-section'});
    const header = el('div', {className:'session-log-section-header'});
    header.appendChild(chevronSvg());
    header.appendChild(el('span', {className:'session-log-section-name'}, name));
    header.appendChild(el('span', {className:'session-log-section-count'}, allEntries.length + ' entries'));
    header.appendChild(levelPills(counts));
    header.addEventListener('click', () => section.classList.toggle('expanded'));
    section.appendChild(header);

    const body = el('div', {className:'session-log-section-body'});

    // Child sections (nested loggers)
    Object.entries(data.children).forEach(([childName, childEntries]) => {
      const childCounts = levelCounts(childEntries);
      const childSection = el('div', {className:'session-log-section session-log-child'});
      const childHeader = el('div', {className:'session-log-section-header'});
      childHeader.appendChild(chevronSvg());
      childHeader.appendChild(el('span', {className:'session-log-section-name'}, childName));
      childHeader.appendChild(el('span', {className:'session-log-section-count'}, String(childEntries.length)));
      childHeader.appendChild(levelPills(childCounts));
      childHeader.addEventListener('click', (ev) => {
        ev.stopPropagation();
        childSection.classList.toggle('expanded');
      });
      childSection.appendChild(childHeader);
      const childBody = el('div', {className:'session-log-section-body'});
      childBody.appendChild(renderLogEntries(childEntries));
      childSection.appendChild(childBody);
      body.appendChild(childSection);
    });

    // Root-level entries for this source
    if (data.entries.length > 0) {
      const rootDiv = el('div', {className:'session-log-root-entries'});
      rootDiv.appendChild(renderLogEntries(data.entries));
      body.appendChild(rootDiv);
    }

    section.appendChild(body);
    treeEl.appendChild(section);
  });
  container.appendChild(treeEl);

  // ── Filtering (search + level toggles) ──
  function applyFilters() {
    const q = search.value.toLowerCase();
    treeEl.querySelectorAll('.log-entry').forEach(entry => {
      const lvl = entry.getAttribute('data-level') || '';
      const levelOk = activeLevels.has(lvl);
      const textOk = !q || entry.textContent.toLowerCase().includes(q);
      entry.classList.toggle('log-hidden', !(levelOk && textOk));
    });
    // Hide sections with zero visible entries
    treeEl.querySelectorAll('.session-log-section').forEach(sec => {
      const has = sec.querySelector('.log-entry:not(.log-hidden)');
      sec.classList.toggle('log-hidden', !has);
    });
  }
  search.addEventListener('input', applyFilters);

  panel.appendChild(container);
}

// ─── Report Tab ──────────────────────────────────────────────────────
function renderReport() {
  const panel = document.getElementById('tab-report');
  const container = el('div', {className:'report-container'});

  // Run info
  const metaSection = el('div', {className:'report-section'});
  const metaHeader = el('div', {className:'report-section-header'});
  metaHeader.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
  metaHeader.appendChild(document.createTextNode(' Run Information'));
  metaSection.appendChild(metaHeader);
  const metaBody = el('div', {className:'report-section-body'});
  const metaRows = [
    ['Timestamp', DATA.timestamp],
    ['Duration', DATA.duration + 's'],
    ['Exit Code', String(DATA.exit_code)],
    ['Python', DATA.python_version],
    ['Pytest', DATA.pytest_version],
    ['Platform', DATA.platform],
  ];
  metaRows.forEach(([label, value]) => {
    metaBody.appendChild(el('div', {className:'report-info-row'},
      el('span', {className:'report-info-label'}, label),
      el('span', {className:'report-info-value'}, value)
    ));
  });
  metaSection.appendChild(metaBody);
  container.appendChild(metaSection);

  // CLI args
  if (DATA.cmdline && DATA.cmdline.length > 0) {
    const cmdSection = el('div', {className:'report-section'});
    const cmdHeader = el('div', {className:'report-section-header'});
    cmdHeader.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>';
    cmdHeader.appendChild(document.createTextNode(' Command Line'));
    cmdSection.appendChild(cmdHeader);
    const cmdBody = el('div', {className:'report-section-body'});
    cmdBody.appendChild(el('div', {className:'log-viewer'}, DATA.cmdline.join(' ')));
    cmdSection.appendChild(cmdBody);
    container.appendChild(cmdSection);
  }

  // Plugins
  if (DATA.plugins && DATA.plugins.length > 0) {
    const plugSection = el('div', {className:'report-section'});
    const plugHeader = el('div', {className:'report-section-header'});
    plugHeader.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1"/><circle cx="6" cy="18" r="1"/></svg>';
    plugHeader.appendChild(document.createTextNode(' Active Plugins'));
    plugSection.appendChild(plugHeader);
    const plugBody = el('div', {className:'report-section-body'});
    const plugList = el('div', {className:'plugin-list'});
    DATA.plugins.forEach(p => plugList.appendChild(el('span', {className:'plugin-tag'}, p)));
    plugBody.appendChild(plugList);
    plugSection.appendChild(plugBody);
    container.appendChild(plugSection);
  }

  // Log
  const logSection = el('div', {className:'report-section'});
  const logHeader = el('div', {className:'report-section-header'});
  logHeader.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>';
  logHeader.appendChild(document.createTextNode(' Pytest Log'));
  logSection.appendChild(logHeader);
  const logBody = el('div', {className:'report-section-body'});
  logBody.appendChild(el('div', {style:'color:var(--c-text3);font-size:13px'},
    'Full log available at pytest.log in the run directory.'
  ));
  logSection.appendChild(logBody);
  container.appendChild(logSection);

  panel.appendChild(container);
}

// ─── Tab switching ───────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    const isActive = b.dataset.tab === name;
    b.classList.toggle('active', isActive);
    b.setAttribute('aria-selected', isActive);
  });
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
}
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// Keyboard navigation for tabs
document.querySelector('.tabs').addEventListener('keydown', (e) => {
  const tabs = Array.from(document.querySelectorAll('.tab-btn'));
  const idx = tabs.indexOf(document.activeElement);
  if (idx === -1) return;
  if (e.key === 'ArrowRight') { tabs[(idx + 1) % tabs.length].focus(); e.preventDefault(); }
  if (e.key === 'ArrowLeft') { tabs[(idx - 1 + tabs.length) % tabs.length].focus(); e.preventDefault(); }
});

// ─── Header ──────────────────────────────────────────────────────────
(function() {
  const metaEl = document.getElementById('header-meta');
  const ts = DATA.timestamp.replace(/_/g, '-');
  const formatted = ts.slice(0,10) + ' ' + ts.slice(11).replace(/-/g,':');

  const agg = aggTests(DATA.tests);
  const badgeClass = agg.failed > 0 || agg.error > 0 ? 'fail' : agg.total === 0 ? 'mix' : 'pass';
  const badgeText = agg.failed > 0 || agg.error > 0
    ? `${agg.failed + agg.error} failed`
    : `${agg.passed} passed`;

  metaEl.innerHTML = `<span>${formatted} UTC</span><span>\u00b7</span><span>${DATA.duration}s</span>`;
  const badge = el('span', {className: `meta-badge ${badgeClass}`}, badgeText);
  metaEl.appendChild(badge);
})();

// ─── Init ────────────────────────────────────────────────────────────
renderSummary();
renderTests();
renderSessionLogs();
renderReport();
</script>
</body>
</html>
"""
