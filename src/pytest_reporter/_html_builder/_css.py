"""Inline CSS for the HTML report template."""

from __future__ import annotations

CSS: str = r"""/* ================================================================
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

/* Hero / pass-rate section */
.summary-hero {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-xl);
  padding: 28px 32px;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  gap: 32px;
}
.summary-hero-rate {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}
.summary-hero-pct {
  font-size: 48px;
  font-weight: 800;
  font-family: var(--font-mono);
  letter-spacing: -0.04em;
  line-height: 1;
}
.summary-hero-pct.good { color: var(--c-passed); }
.summary-hero-pct.warn { color: var(--c-skipped); }
.summary-hero-pct.bad { color: var(--c-failed); }
.summary-hero-pct-label {
  font-size: 10px;
  color: var(--c-text3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  margin-top: 4px;
}
.summary-hero-body { flex: 1; min-width: 0; }
.summary-hero-body h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text);
  margin-bottom: 12px;
}
.summary-hero-dur {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}
.summary-hero-dur-value {
  font-size: 32px;
  font-weight: 800;
  font-family: var(--font-mono);
  letter-spacing: -0.04em;
  line-height: 1;
  color: var(--c-text2);
}
.summary-hero-dur-label {
  font-size: 10px;
  color: var(--c-text3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  margin-top: 4px;
}

/* Ratio bar */
.ratio-bar-wrap { width: 100%; }
.ratio-bar {
  display: flex;
  width: 100%;
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  background: var(--c-surface3);
}
.ratio-bar-seg {
  height: 100%;
  transition: width 0.3s var(--ease-out);
  min-width: 0;
}
.ratio-bar-seg.passed { background: var(--c-passed); }
.ratio-bar-seg.failed { background: var(--c-failed); }
.ratio-bar-seg.skipped { background: var(--c-skipped); }
.ratio-bar-seg.error { background: var(--c-error); }
.ratio-bar-legend {
  display: flex;
  gap: 16px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.ratio-bar-legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--c-text2);
  font-weight: 500;
}
.ratio-bar-legend-item strong {
  color: var(--c-text);
  font-weight: 700;
  font-family: var(--font-mono);
}

/* Counter cards */
.counters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
  margin-bottom: 28px;
}
.counter-card {
  background: var(--c-surface);
  border-radius: var(--radius-lg);
  padding: 18px 16px;
  text-align: center;
  border: 1px solid var(--c-border);
  transition: border-color 0.2s var(--ease-out), box-shadow 0.2s var(--ease-out);
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
  box-shadow: var(--shadow-md);
}
.counter-card .value {
  font-size: 32px;
  font-weight: 700;
  font-family: var(--font-mono);
  letter-spacing: -0.03em;
  line-height: 1.1;
}
.counter-card .label {
  font-size: 10px;
  color: var(--c-text3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  margin-top: 4px;
}
.counter-card .counter-pct {
  font-size: 11px;
  color: var(--c-text3);
  font-family: var(--font-mono);
  font-weight: 500;
  margin-top: 2px;
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
.counter-card.error .value { color: var(--c-error); }
.counter-card.error:hover { border-color: rgba(249,115,22,0.35); box-shadow: 0 4px 20px rgba(249,115,22,0.1); }

.counter-card.retried { border-color: rgba(59,130,246,0.2); }
.counter-card.retried::before { background: var(--c-accent); }
.counter-card.retried .value { color: var(--c-accent); }
.counter-card.retried:hover { border-color: rgba(59,130,246,0.35); box-shadow: 0 4px 20px rgba(59,130,246,0.1); }

.counter-card.total { border-color: rgba(59,130,246,0.2); }
.counter-card.total::before { background: var(--c-accent); }
.counter-card.total .value { color: var(--c-accent); }
.counter-card.total:hover { border-color: rgba(59,130,246,0.35); box-shadow: 0 4px 20px rgba(59,130,246,0.1); }

/* Charts */
.charts-section { margin-bottom: 28px; }
.charts-section-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-text3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.charts-section-title::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--c-border);
}
.charts-section-count {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--c-text3);
  background: var(--c-surface2);
  padding: 1px 7px;
  border-radius: 8px;
}
.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}
/* Fixed donut card dimensions prevent layout shift as charts load */
.chart-card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  padding: 22px 18px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s var(--ease-out), box-shadow 0.2s var(--ease-out);
  min-height: 210px;
  box-sizing: border-box;
}
.chart-card:hover {
  border-color: var(--c-border2);
  box-shadow: var(--shadow-md);
}
.chart-card h3 {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 14px;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chart-card svg { display: block; margin: 0 auto; }
.chart-card-dur {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--c-text3);
  margin-top: 6px;
  text-align: center;
}
/* donut-counts: accessible numeric summary below each donut (WCAG SC 1.4.1) */
.donut-counts {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--c-text2);
  margin-top: 8px;
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}
.donut-counts .dc-passed { color: var(--c-passed); }
.donut-counts .dc-failed { color: var(--c-failed); }
.donut-counts .dc-skipped { color: var(--c-skipped); }
.donut-counts .dc-error { color: var(--c-error); }
.donut-counts .dc-rate { color: var(--c-text2); font-weight: 600; }
.chart-legend {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 12px;
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
/* pass-rate-bar: AAA-grade dense chart (style='bars' or auto-dense heuristic) */
.pass-rate-bars-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pass-rate-bar {
  display: grid;
  grid-template-columns: minmax(80px, 20%) 1fr auto;
  align-items: center;
  gap: 12px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  cursor: pointer;
  transition: border-color 0.15s var(--ease-out), box-shadow 0.15s var(--ease-out);
}
.pass-rate-bar:hover { border-color: var(--c-border2); box-shadow: var(--shadow-sm); }
.pass-rate-bar-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pass-rate-bar-track {
  height: 10px;
  border-radius: 5px;
  background: var(--c-surface2);
  overflow: hidden;
  position: relative;
}
.pass-rate-bar-fill {
  height: 100%;
  border-radius: 5px;
  background: var(--c-passed);
  transition: width 0.3s var(--ease-out);
}
.pass-rate-bar-stats {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--c-text2);
  white-space: nowrap;
  text-align: right;
  min-width: 120px;
}
.pass-rate-bar-stats .prs-rate { font-weight: 700; font-size: 11px; color: var(--c-text); }
.pass-rate-bar-stats .prs-passed { color: var(--c-passed); }
.pass-rate-bar-stats .prs-failed { color: var(--c-failed); }
.pass-rate-bar-stats .prs-skipped { color: var(--c-skipped); }
.pass-rate-bar-stats .prs-error { color: var(--c-error); }
.pass-rate-bar-stats .prs-dur { font-family: var(--font-mono); color: var(--c-text3); font-size: 10px; }

@media (max-width: 640px) {
  .summary-hero { flex-direction: column; gap: 20px; padding: 22px 20px; }
  .summary-hero-pct { font-size: 36px; }
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
/* Breadcrumb separator for collapsed chain nodes (tests-tree-cleanup) */
.crumb-sep {
  color: var(--c-text3);
  padding: 0 0.2em;
  font-weight: 300;
  pointer-events: none;
}
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

/* Inline table (from log.table()) */
.log-entry-table-wrap {
  grid-column: 1 / -1;
  margin: 4px 0 4px 24px;
  overflow: hidden;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  background: var(--c-surface);
}
.log-entry-table-name {
  padding: 8px 12px 4px;
  font-size: 12px;
  font-weight: 700;
  color: var(--c-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.log-entry-table-name .table-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--c-accent-dim);
  color: var(--c-accent);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.log-entry-table-scroll {
  overflow-x: auto;
  max-height: 500px;
  overflow-y: auto;
}
.log-entry-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  font-family: var(--font-mono);
}
.log-entry-table th {
  background: var(--c-surface2);
  color: var(--c-text2);
  font-weight: 700;
  padding: 6px 12px;
  text-align: left;
  border-bottom: 2px solid var(--c-border);
  position: sticky;
  top: 0;
  z-index: 1;
  white-space: nowrap;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.log-entry-table td {
  padding: 4px 12px;
  color: var(--c-text);
  border-bottom: 1px solid var(--c-border);
  white-space: nowrap;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.log-entry-table tr:hover td { background: var(--c-surface3); }
.log-entry-table tr:nth-child(even) td { background: rgba(27,39,64,0.3); }
.log-entry-table tr:nth-child(even):hover td { background: var(--c-surface3); }
.log-entry-table-footer {
  padding: 6px 12px;
  font-size: 11px;
  color: var(--c-text3);
  border-top: 1px solid var(--c-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  background: var(--c-surface);
}
.log-entry-table-toggle {
  background: none;
  border: none;
  color: var(--c-accent);
  cursor: pointer;
  font-size: 11px;
  font-family: var(--font-mono);
  padding: 0;
}
.log-entry-table-toggle:hover { text-decoration: underline; }

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
  border-radius: 4px;
}
.procedure-step-header:hover { background: var(--c-surface3); border-radius: 4px; }
.procedure-subsubstep {
  font-size: 0.85em;
  color: var(--c-text2);
}
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
.proc-mono {
  font-family: var(--font-mono);
  background: var(--c-surface2);
  padding: 0 4px;
  border-radius: 3px;
  font-size: 0.92em;
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
.check-card-chevron {
  flex-shrink: 0;
  color: var(--c-text3);
  transition: transform 0.2s var(--ease-out);
}
.check-card.expanded > .check-card-header .check-card-chevron { transform: rotate(90deg); }
@media (prefers-reduced-motion: reduce) { .check-card-chevron { transition: none; } }
.check-card-header:hover { background: var(--c-surface2); border-radius: 4px; }
.check-card-header:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 2px; border-radius: 4px; }
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
  .counters { grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px; }
  .counter-card { padding: 14px 12px; }
  .counter-card .value { font-size: 24px; }
  .charts-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
  .header { padding: 0 16px; }
  .tabs { padding: 0 16px; }
  .summary-container, .report-container { padding: 16px; }
  .info-grid { grid-template-columns: 1fr; gap: 4px 0; }
  .info-label { margin-top: 8px; }
}"""
