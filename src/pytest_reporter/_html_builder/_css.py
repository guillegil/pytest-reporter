"""Inline CSS for the HTML report template."""

from __future__ import annotations

# Light theme roles: for bright rooms, and for printing. The fills stay the
# pinned graph colours; ink, surfaces and text move to the light side.
_LIGHT_TOKENS = """  color-scheme: light;

  --c-bg: #F5F7FA;
  --c-surface: #FFFFFF;
  --c-surface2: #EEF2F7;
  --c-surface3: #E3E9F1;
  --c-text: #0F172A;
  --c-text2: #475569;
  --c-text3: #526174;
  --c-border: #E2E8F0;
  --c-border2: #CBD5E1;

  --c-passed-ink: #166534;
  --c-failed-ink: #B91C1C;
  --c-skipped-ink: #92400E;
  --c-error-ink: #9A3412;
  --c-accent-ink: #1D4ED8;
  --c-accent-strong: #1D4ED8;

  --tint: 12%;
  --c-overlay: rgba(15,23,42,0.82);
  --c-well: rgba(15,23,42,0.05);
  --c-zebra: color-mix(in srgb, var(--c-surface2) 60%, transparent);
  --c-track: color-mix(in srgb, var(--c-text) 8%, transparent);
  --c-selection: color-mix(in srgb, var(--c-accent) 22%, transparent);
  --shadow-color: 15,23,42;
  --shadow-alpha: 0.35;
"""


def _themes() -> str:
    """Light theme: from the OS setting unless the viewer picked one, and for print."""
    return (
        "@media (prefers-color-scheme: light) {\n"
        '  :root:not([data-theme="dark"]) {\n' + _LIGHT_TOKENS + "  }\n}\n"
        ':root[data-theme="light"] {\n' + _LIGHT_TOKENS + "}\n"
        "@media print {\n  :root, :root[data-theme] {\n" + _LIGHT_TOKENS + "  }\n}\n"
    )


CSS: str = (
    r"""/* ================================================================
   Design tokens

   Colour roles. Status *fills* (--c-passed ...) are the pinned graph
   colours and stay the same in every theme; status *ink* (--c-*-ink) is
   the text version of each, tuned per theme for >= 4.5:1 on its own
   tint and on every surface. Tints are mixed from the fills, so a theme
   only remaps the roles below.
   ================================================================ */
:root {
  color-scheme: dark;

  --c-passed: #22C55E;
  --c-failed: #EF4444;
  --c-skipped: #F59E0B;
  --c-error: #F97316;
  --c-accent: #3B82F6;

  --c-bg: #0B1120;
  --c-surface: #131C2E;
  --c-surface2: #1B2740;
  --c-surface3: #243352;
  --c-text: #E8ECF4;
  --c-text2: #AAB6C8;
  --c-text3: #94A1B6;
  --c-border: #1E2D45;
  --c-border2: #2A3D5A;

  --c-passed-ink: #4ADE80;
  --c-failed-ink: #FCA5A5;
  --c-skipped-ink: #FBBF24;
  --c-error-ink: #FDBA74;
  --c-accent-ink: #93C5FD;
  --c-accent-strong: #2563EB;
  --c-on-accent: #FFFFFF;

  --tint: 14%;
  --c-header-bg: color-mix(in srgb, var(--c-surface) 92%, transparent);
  --c-overlay: rgba(2,6,16,0.86);
  --c-well: rgba(0,0,0,0.22);
  --c-zebra: color-mix(in srgb, var(--c-surface2) 30%, transparent);
  --c-track: color-mix(in srgb, var(--c-text) 6%, transparent);
  --c-selection: color-mix(in srgb, var(--c-accent) 38%, transparent);
  --shadow-color: 0,0,0;
  --shadow-alpha: 1;

  --c-passed-dim: color-mix(in srgb, var(--c-passed) var(--tint), transparent);
  --c-failed-dim: color-mix(in srgb, var(--c-failed) var(--tint), transparent);
  --c-skipped-dim: color-mix(in srgb, var(--c-skipped) var(--tint), transparent);
  --c-error-dim: color-mix(in srgb, var(--c-error) var(--tint), transparent);
  --c-accent-dim: color-mix(in srgb, var(--c-accent) var(--tint), transparent);
  --c-failed-strong-dim: color-mix(in srgb, var(--c-failed) 26%, transparent);
  --c-failed-line: color-mix(in srgb, var(--c-failed) 32%, transparent);

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 18px;

  --shadow-sm: 0 1px 2px rgba(var(--shadow-color),calc(0.3 * var(--shadow-alpha)));
  --shadow-md: 0 4px 12px rgba(var(--shadow-color),calc(0.25 * var(--shadow-alpha)));
  --shadow-lg: 0 8px 30px rgba(var(--shadow-color),calc(0.35 * var(--shadow-alpha)));

  /* Type roles: one step per job, 11px floor.
     xs  11  badges, counts, uppercase labels, timestamps
     sm  12  secondary text, meta, controls
     md  13  body and log text (the dense default)
     lg  15  section and app titles
     xl  18  page titles (test name, Failures)
     2xl 24  figures (counters, total time)
     3xl 36  the pass-rate hero */
  --fs-xs: 11px;
  --fs-sm: 12px;
  --fs-md: 13px;
  --fs-lg: 15px;
  --fs-xl: 18px;
  --fs-2xl: 24px;
  --fs-3xl: 36px;

  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-mono: 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace;

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}


"""
    + _themes()
    + r"""
/* Browser surfaces take the palette too */
::selection { background: var(--c-selection); color: var(--c-text); }
html { scrollbar-color: var(--c-border2) transparent; }
input, textarea { caret-color: var(--c-accent); accent-color: var(--c-accent); }

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
a { color: var(--c-accent-ink); text-decoration: none; }
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
  background: var(--c-header-bg);
}
.header-logo {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-logo svg { flex-shrink: 0; }
.header h1 {
  font-size: var(--fs-lg);
  font-weight: 600;
  letter-spacing: -0.01em;
}
.header .meta {
  color: var(--c-text2);
  font-size: var(--fs-sm);
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
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.02em;
}
.meta-badge.pass { background: var(--c-passed-dim); color: var(--c-passed-ink); }
.meta-badge.fail { background: var(--c-failed-dim); color: var(--c-failed-ink); }
.meta-badge.mix { background: var(--c-accent-dim); color: var(--c-accent-ink); }

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
  background: var(--c-header-bg);
}
.tab-btn {
  padding: 12px 20px;
  background: none;
  border: none;
  color: var(--c-text3);
  font-size: var(--fs-md);
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
  font-size: var(--fs-3xl);
  font-weight: 700;
  font-family: var(--font-mono);
  letter-spacing: -0.04em;
  line-height: 1;
}
.summary-hero-pct.good { color: var(--c-passed-ink); }
.summary-hero-pct.warn { color: var(--c-skipped-ink); }
.summary-hero-pct.bad { color: var(--c-failed-ink); }
.summary-hero-pct-label {
  font-size: var(--fs-xs);
  color: var(--c-text3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  margin-top: 4px;
}
.summary-hero-divider {
  align-self: stretch;
  width: 1px;
  background: var(--c-border);
  flex-shrink: 0;
  margin: 4px 0;
}
.summary-hero-body { flex: 1; min-width: 0; }
.summary-hero-body h2 {
  font-size: var(--fs-lg);
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
  font-size: var(--fs-2xl);
  font-weight: 700;
  font-family: var(--font-mono);
  letter-spacing: -0.02em;
  line-height: 1;
  color: var(--c-text2);
}
.summary-hero-dur-label {
  font-size: var(--fs-xs);
  color: var(--c-text2);
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
  font-size: var(--fs-sm);
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
  font-size: var(--fs-2xl);
  font-weight: 700;
  font-family: var(--font-mono);
  letter-spacing: -0.03em;
  line-height: 1.1;
}
.counter-card .label {
  font-size: var(--fs-xs);
  color: var(--c-text3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  margin-top: 4px;
}
.counter-card .counter-pct {
  font-size: var(--fs-xs);
  color: var(--c-text3);
  font-family: var(--font-mono);
  font-weight: 500;
  margin-top: 2px;
}

.counter-card.passed { border-color: color-mix(in srgb, var(--c-passed) 20%, transparent); }
.counter-card.passed::before { background: var(--c-passed); }
.counter-card.passed .value { color: var(--c-passed-ink); }
.counter-card.passed:hover { border-color: color-mix(in srgb, var(--c-passed) 35%, transparent); box-shadow: 0 4px 20px color-mix(in srgb, var(--c-passed) 10%, transparent); }

.counter-card.failed { border-color: color-mix(in srgb, var(--c-failed) 20%, transparent); }
.counter-card.failed::before { background: var(--c-failed); }
.counter-card.failed .value { color: var(--c-failed-ink); }
.counter-card.failed:hover { border-color: color-mix(in srgb, var(--c-failed) 35%, transparent); box-shadow: 0 4px 20px color-mix(in srgb, var(--c-failed) 10%, transparent); }

.counter-card.skipped { border-color: color-mix(in srgb, var(--c-skipped) 20%, transparent); }
.counter-card.skipped::before { background: var(--c-skipped); }
.counter-card.skipped .value { color: var(--c-skipped-ink); }
.counter-card.skipped:hover { border-color: color-mix(in srgb, var(--c-skipped) 35%, transparent); box-shadow: 0 4px 20px color-mix(in srgb, var(--c-skipped) 10%, transparent); }

.counter-card.error { border-color: color-mix(in srgb, var(--c-error) 20%, transparent); }
.counter-card.error::before { background: var(--c-error); }
.counter-card.error .value { color: var(--c-error-ink); }
.counter-card.error:hover { border-color: color-mix(in srgb, var(--c-error) 35%, transparent); box-shadow: 0 4px 20px color-mix(in srgb, var(--c-error) 10%, transparent); }

.counter-card.retried { border-color: color-mix(in srgb, var(--c-accent) 20%, transparent); }
.counter-card.retried::before { background: var(--c-accent); }
.counter-card.retried .value { color: var(--c-accent-ink); }
.counter-card.retried:hover { border-color: color-mix(in srgb, var(--c-accent) 35%, transparent); box-shadow: 0 4px 20px color-mix(in srgb, var(--c-accent) 10%, transparent); }

.counter-card.total { border-color: color-mix(in srgb, var(--c-accent) 20%, transparent); }
.counter-card.total::before { background: var(--c-accent); }
.counter-card.total .value { color: var(--c-accent-ink); }
.counter-card.total:hover { border-color: color-mix(in srgb, var(--c-accent) 35%, transparent); box-shadow: 0 4px 20px color-mix(in srgb, var(--c-accent) 10%, transparent); }

/* Charts */
.charts-section { margin-bottom: 28px; }
.charts-section-title {
  font-size: var(--fs-xs);
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
  font-size: var(--fs-xs);
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
  font-size: var(--fs-md);
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
  font-size: var(--fs-xs);
  color: var(--c-text2);
  margin-top: 6px;
  text-align: center;
}
/* donut-counts: accessible numeric summary below each donut (WCAG SC 1.4.1) */
.donut-counts {
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  color: var(--c-text2);
  margin-top: 8px;
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}
.donut-counts .dc-passed { color: var(--c-passed-ink); }
.donut-counts .dc-failed { color: var(--c-failed-ink); }
.donut-counts .dc-skipped { color: var(--c-skipped-ink); }
.donut-counts .dc-error { color: var(--c-error-ink); }
.donut-counts .dc-rate { color: var(--c-text2); font-weight: 600; }
.chart-legend {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 12px;
  font-size: var(--fs-xs);
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
  font-size: var(--fs-sm);
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
  font-size: var(--fs-xs);
  color: var(--c-text2);
  white-space: nowrap;
  text-align: right;
  min-width: 120px;
}
.pass-rate-bar-stats .prs-rate { font-weight: 700; font-size: var(--fs-xs); color: var(--c-text); }
.pass-rate-bar-stats .prs-passed { color: var(--c-passed-ink); }
.pass-rate-bar-stats .prs-failed { color: var(--c-failed-ink); }
.pass-rate-bar-stats .prs-skipped { color: var(--c-skipped-ink); }
.pass-rate-bar-stats .prs-error { color: var(--c-error-ink); }
.pass-rate-bar-stats .prs-dur { font-family: var(--font-mono); color: var(--c-text2); font-size: var(--fs-xs); }

@media (max-width: 640px) {
  .summary-hero { flex-direction: column; gap: 20px; padding: 22px 20px; }
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
  font-size: var(--fs-sm);
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
  font-size: var(--fs-xs);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
  user-select: none;
}
.filter-btn:hover { border-color: var(--c-border2); color: var(--c-text2); }
.filter-btn.active { border-color: currentColor; }
.filter-btn.passed.active { color: var(--c-passed-ink); background: var(--c-passed-dim); }
.filter-btn.failed.active { color: var(--c-failed-ink); background: var(--c-failed-dim); }
.filter-btn.skipped.active { color: var(--c-skipped-ink); background: var(--c-skipped-dim); }
.filter-btn.error.active { color: var(--c-error-ink); background: var(--c-error-dim); }
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
  font-size: var(--fs-md);
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
  font-size: var(--fs-xs);
  font-weight: 700;
  padding: 0px 5px;
  border-radius: 8px;
  font-family: var(--font-mono);
  line-height: 16px;
}
.tree-badge.passed { background: var(--c-passed-dim); color: var(--c-passed-ink); }
.tree-badge.failed { background: var(--c-failed-dim); color: var(--c-failed-ink); }
.tree-badge.skipped { background: var(--c-skipped-dim); color: var(--c-skipped-ink); }
.tree-badge.error { background: var(--c-error-dim); color: var(--c-error-ink); }
.tree-badge.count {
  background: var(--c-surface3);
  color: var(--c-text3);
}
/* Flaky marker: a test/group that needed retries (final outcome may be pass) */
.tree-badge.retried {
  background: var(--c-skipped-dim);
  color: var(--c-skipped-ink);
}
.tree-children { display: none; }
.tree-node.expanded > .tree-children { display: block; }
/* Breadcrumb separator for collapsed chain nodes (tests-tree-cleanup) */
.crumb-sep {
  color: var(--c-text3);
  padding: 0 0.2em;
  font-weight: 400;
  pointer-events: none;
}
/* Class grouping node in the Tests tree (file -> class -> method).
   The class label is shown once as a parent node, with a small "class" tag,
   instead of a per-method eyebrow. */
.tree-class {
  font-family: var(--font-mono);
  color: var(--c-text);
  font-weight: 500;
}
.tree-class::before {
  content: 'class';
  display: inline-block;
  margin-right: 6px;
  padding: 0 5px;
  font-size: var(--fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--c-text2);
  background: var(--c-surface3);
  border-radius: 4px;
  vertical-align: middle;
}
.detail-eyebrow {
  font-size: 0.85em;
  color: var(--c-text2);
  margin-bottom: 0.15em;
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
.detail-empty span { font-size: var(--fs-lg); }
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
  font-size: var(--fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
  margin-top: 2px;
}
.detail-header-outcome.passed { background: var(--c-passed-dim); color: var(--c-passed-ink); }
.detail-header-outcome.failed { background: var(--c-failed-dim); color: var(--c-failed-ink); }
.detail-header-outcome.skipped { background: var(--c-skipped-dim); color: var(--c-skipped-ink); }
.detail-header-outcome.error { background: var(--c-error-dim); color: var(--c-error-ink); }
.detail-header h2 {
  font-size: var(--fs-xl);
  font-weight: 700;
  overflow-wrap: anywhere;
  letter-spacing: -0.02em;
  line-height: 1.3;
}
.detail-header .file-path {
  font-size: var(--fs-sm);
  color: var(--c-text3);
  font-family: var(--font-mono);
  margin-top: 6px;
}
.detail-cmd {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 5px 10px;
  max-width: 100%;
  background: var(--c-surface2);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.detail-cmd:hover,
.detail-cmd:focus-visible {
  border-color: var(--c-accent);
  background: var(--c-surface3);
  outline: none;
}
.detail-cmd:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 2px; }
.detail-cmd.copied {
  border-color: var(--c-passed);
}
.detail-cmd-code {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-cmd-hint {
  flex-shrink: 0;
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--c-text3);
}
.detail-cmd.copied .detail-cmd-hint {
  color: var(--c-passed-ink);
}
@media (prefers-reduced-motion: reduce) {
  .detail-cmd { transition: none; }
}
.detail-header-stats {
  display: flex;
  gap: 16px;
  margin-top: 12px;
  font-size: var(--fs-sm);
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
  font-size: var(--fs-xs);
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
  font-size: var(--fs-xs);
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.15s var(--ease-out);
  font-weight: 600;
  font-family: var(--font-mono);
  letter-spacing: -0.01em;
}
.run-pill.passed { background: var(--c-passed-dim); color: var(--c-passed-ink); }
.run-pill.failed { background: var(--c-failed-dim); color: var(--c-failed-ink); }
.run-pill.skipped { background: var(--c-skipped-dim); color: var(--c-skipped-ink); }
.run-pill.error { background: var(--c-error-dim); color: var(--c-error-ink); }
.run-pill:hover { filter: brightness(1.2); }
.run-pill.selected { border-color: currentColor; box-shadow: 0 0 0 1px currentColor; }
.show-more-btn {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: var(--fs-xs);
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
  font-size: var(--fs-sm);
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
  font-size: var(--fs-md);
  margin-bottom: 20px;
}
.info-label {
  color: var(--c-text3);
  font-weight: 500;
  font-size: var(--fs-sm);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.info-value { color: var(--c-text); }
.params-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-md);
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
  font-size: var(--fs-xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.params-table td {
  padding: 8px 14px;
  border-bottom: 1px solid var(--c-border);
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
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
  font-size: var(--fs-xs);
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
  font-size: var(--fs-xs);
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
  font-size: var(--fs-sm);
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--c-text2);
}
.phase-tab-empty {
  padding: 24px 14px;
  text-align: center;
  color: var(--c-text3);
  font-size: var(--fs-md);
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
  font-size: var(--fs-sm);
}
.artifact-name {
  font-weight: 600;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.artifact-size { color: var(--c-text3); font-size: var(--fs-xs); margin-top: 2px; }
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
  min-height: 120px;
  margin-bottom: 8px;
  display: block;
}
.artifact-expand { margin-bottom: 16px; }

/* Lightbox */
.lightbox-overlay {
  position: fixed;
  inset: 0;
  background: var(--c-overlay);
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
  font-size: var(--fs-sm);
  font-family: var(--font-mono);
  border-radius: 4px;
  line-height: 1.5;
}
.log-entry:hover { background: var(--c-surface3); }
.log-entry-time { color: var(--c-text3); font-size: var(--fs-xs); white-space: nowrap; }
.log-entry-level {
  font-size: var(--fs-xs);
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.log-entry-level.DEBUG { background: var(--c-accent-dim); color: var(--c-accent-ink); }
.log-entry-level.INFO { background: var(--c-passed-dim); color: var(--c-passed-ink); }
.log-entry-level.WARNING { background: var(--c-skipped-dim); color: var(--c-skipped-ink); }
.log-entry-level.ERROR { background: var(--c-failed-dim); color: var(--c-failed-ink); }
.log-entry-level.CRITICAL { background: var(--c-failed-strong-dim); color: var(--c-failed-ink); }
.log-entry-source { color: var(--c-text2); font-size: var(--fs-xs); }
.log-entry-msg { color: var(--c-text); word-break: break-word; }
.log-entry-data {
  grid-column: 1 / -1;
  margin-left: 24px;
  padding: 6px 10px;
  background: var(--c-surface);
  border-radius: 4px;
  font-size: var(--fs-xs);
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
  font-size: var(--fs-xs);
  color: var(--c-failed-ink);
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
  font-size: var(--fs-sm);
  font-weight: 700;
  color: var(--c-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.log-entry-table-name .table-badge {
  font-size: var(--fs-xs);
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--c-accent-dim);
  color: var(--c-accent-ink);
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
  font-size: var(--fs-xs);
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
  font-size: var(--fs-xs);
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
.log-entry-table tr:nth-child(even) td { background: var(--c-zebra); }
.log-entry-table tr:nth-child(even):hover td { background: var(--c-surface3); }
.log-entry-table-footer {
  padding: 6px 12px;
  font-size: var(--fs-xs);
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
  color: var(--c-accent-ink);
  cursor: pointer;
  font-size: var(--fs-xs);
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
  font-size: var(--fs-md);
}
.procedure-step-number {
  font-weight: 700;
  color: var(--c-text2);
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  min-width: 28px;
}
.procedure-step-desc { color: var(--c-text); flex: 1; }
.procedure-step-duration {
  color: var(--c-text3);
  font-size: var(--fs-xs);
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
  font-size: var(--fs-sm);
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
  font-size: var(--fs-xs);
  font-family: var(--font-mono);
  color: var(--c-failed-ink);
  white-space: pre-wrap;
  max-height: 200px;
  overflow: auto;
}
.procedure-section {
  margin-top: 6px;
  font-size: var(--fs-xs);
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-text3);
}
.procedure-result {
  color: var(--c-text2);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
}
.proc-kind-action .procedure-step-desc { font-family: var(--font-mono); font-size: 0.95em; }
.status-dot.info { background: var(--c-text3); opacity: 0.5; }
.status-dot.unknown { background: transparent; border: 1px solid var(--c-text3); }
.procedure-empty {
  padding: 24px;
  text-align: center;
  color: var(--c-text3);
  font-size: var(--fs-md);
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
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}
.check-badge.pass { background: var(--c-passed-dim); color: var(--c-passed-ink); }
.check-badge.fail { background: var(--c-failed-dim); color: var(--c-failed-ink); }
.procedure-check-desc {
  color: var(--c-text3);
  font-size: var(--fs-sm);
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
  border-color: color-mix(in srgb, var(--c-passed) 25%, transparent);
  border-left: 3px solid var(--c-passed);
}
.check-card.failed {
  background: var(--c-failed-dim);
  border-color: color-mix(in srgb, var(--c-failed) 25%, transparent);
  border-left: 3px solid var(--c-failed);
}
.check-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: var(--fs-md);
  font-weight: 500;
}
.check-card-header .check-name {
  font-weight: 600;
  flex-shrink: 0;
}
.check-card-header .check-desc {
  color: var(--c-text2);
  font-size: var(--fs-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.check-card-header .check-type-badge {
  margin-left: auto;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: var(--fs-xs);
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
  font-size: var(--fs-sm);
}
.check-card-detail .label {
  color: var(--c-text3);
  font-weight: 500;
}
.check-card-detail .value {
  font-family: var(--font-mono);
  color: var(--c-text);
  font-size: var(--fs-xs);
}
/* Guard check (if/elif/else chain) rendering */
.guard-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.guard-branch {
  border: 1px solid var(--c-border);
  border-radius: 6px;
  padding: 8px 10px;
  background: var(--c-surface2);
  opacity: 0.65;
}
.guard-branch.chosen {
  opacity: 1;
  border-color: var(--c-accent, var(--c-passed));
  background: var(--c-surface3);
}
.guard-branch-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: var(--fs-sm);
}
.guard-kw {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: var(--fs-xs);
  color: var(--c-text2);
}
.guard-label { color: var(--c-text); font-weight: 500; }
.guard-cond {
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  padding: 0 6px;
  border-radius: 8px;
  line-height: 16px;
}
.guard-cond.true { background: var(--c-passed-dim); color: var(--c-passed-ink); }
.guard-cond.false { background: var(--c-surface); color: var(--c-text2); }
.guard-chosen-tag {
  margin-left: auto;
  font-size: var(--fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 1px 7px;
  border-radius: 8px;
  background: var(--c-accent-dim, var(--c-surface));
  color: var(--c-accent, var(--c-text));
}
.guard-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-sm);
  margin-bottom: 2px;
}
.guard-switch-val {
  font-family: var(--font-mono);
  color: var(--c-text);
  font-weight: 600;
}
.guard-check { margin-top: 6px; }
.guard-check-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: var(--fs-xs);
}
.guard-check-name { font-weight: 600; color: var(--c-text); }
.guard-check-desc { color: var(--c-text2); }
.guard-check .check-card-detail { margin-top: 6px; }
.guard-nomatch {
  font-size: var(--fs-sm);
  font-style: italic;
  color: var(--c-failed-ink);
}
.check-card-longrepr {
  margin-top: 8px;
  padding: 8px 10px;
  background: var(--c-well);
  border-radius: 4px;
  font-size: var(--fs-xs);
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
  font-size: var(--fs-sm);
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
  border: 1px solid color-mix(in srgb, var(--c-failed) 30%, transparent);
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
  font-size: var(--fs-md);
  color: var(--c-failed-ink);
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
  font-size: var(--fs-md);
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
  font-size: var(--fs-xs);
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
  font-size: var(--fs-sm);
  transition: border-color 0.15s var(--ease-out);
}
.session-log-search:focus { outline: none; border-color: var(--c-accent); box-shadow: 0 0 0 3px var(--c-accent-dim); }
.session-log-search::placeholder { color: var(--c-text3); }
.session-log-level-filters { display: flex; gap: 4px; flex-wrap: wrap; }
.session-log-level-btn {
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid var(--c-border);
  background: none;
  color: var(--c-text3);
  font-size: var(--fs-xs);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
  user-select: none;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.session-log-level-btn:hover { border-color: var(--c-border2); color: var(--c-text2); }
.session-log-level-btn.active { border-color: currentColor; }
.session-log-level-btn.DEBUG.active { color: var(--c-accent-ink); background: var(--c-accent-dim); }
.session-log-level-btn.INFO.active { color: var(--c-passed-ink); background: var(--c-passed-dim); }
.session-log-level-btn.WARNING.active { color: var(--c-skipped-ink); background: var(--c-skipped-dim); }
.session-log-level-btn.ERROR.active { color: var(--c-failed-ink); background: var(--c-failed-dim); }
.session-log-level-btn.CRITICAL.active { color: var(--c-failed-ink); background: var(--c-failed-strong-dim); }
.session-log-actions { display: flex; gap: 4px; margin-left: auto; }
.session-log-action-btn {
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--c-border);
  background: none;
  color: var(--c-text2);
  font-size: var(--fs-xs);
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
  font-size: var(--fs-md);
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
  font-size: var(--fs-xs);
  font-weight: 400;
}
.session-log-section-levels {
  display: flex;
  gap: 4px;
  margin-left: auto;
}
.session-log-level-pill {
  font-size: var(--fs-xs);
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.session-log-level-pill.DEBUG { background: var(--c-accent-dim); color: var(--c-accent-ink); }
.session-log-level-pill.INFO { background: var(--c-passed-dim); color: var(--c-passed-ink); }
.session-log-level-pill.WARNING { background: var(--c-skipped-dim); color: var(--c-skipped-ink); }
.session-log-level-pill.ERROR { background: var(--c-failed-dim); color: var(--c-failed-ink); }
.session-log-level-pill.CRITICAL { background: var(--c-failed-strong-dim); color: var(--c-failed-ink); }
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
  font-size: var(--fs-sm);
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
  font-size: var(--fs-lg);
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
  font-size: var(--fs-md);
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
  font-size: var(--fs-md);
  border-bottom: 1px solid var(--c-border);
}
.report-info-row:last-child { border-bottom: none; }
.report-info-label { color: var(--c-text3); font-weight: 500; }
.report-info-value { color: var(--c-text); font-family: var(--font-mono); font-size: var(--fs-sm); text-align: right; }
.report-info-value.mono { font-family: var(--font-mono); }
.report-info-not-provided { color: var(--c-text3); font-style: italic; font-size: var(--fs-sm); text-align: right; }
.log-viewer {
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  padding: 16px;
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
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
  font-size: var(--fs-md);
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
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  background: var(--c-surface2);
  border-radius: 20px;
  font-size: var(--fs-xs);
  font-family: var(--font-mono);
  color: var(--c-text2);
}
/* Version badge inside plugin-tag (Slice E) */
.plugin-ver {
  padding: 1px 5px;
  background: var(--c-surface3, var(--c-surface));
  border-radius: 8px;
  font-size: 0.85em;
  color: var(--c-text2);
}
/* Empty-state for no distributed plugins (Slice E) */
.plugins-empty {
  font-size: var(--fs-sm);
  color: var(--c-text2);
  font-style: italic;
}
/* Plugins collapsible chevron rotation */
.plugins-collapsible .plugins-chevron {
  margin-left: auto;
  transition: transform 0.2s ease;
}
@media (prefers-reduced-motion: reduce) { .plugins-collapsible .plugins-chevron { transition: none; } }
/* Interactive affordances — the header is role="button" (Slice E) */
.plugins-collapsible { cursor: pointer; }
.plugins-collapsible:hover { background: var(--c-surface2); }
.plugins-collapsible:focus-visible { outline: 2px solid var(--c-accent); outline-offset: -2px; }

/* ================================================================
   Failure-first triage: Summary failures list, run failure strip
   ================================================================ */
/* Counter cards that filter the Tests tab */
button.counter-card {
  font: inherit;
  color: inherit;
  width: 100%;
  cursor: pointer;
}
button.counter-card:focus-visible {
  outline: 2px solid var(--c-accent);
  outline-offset: 2px;
}

.strip-btn {
  font: inherit;
  font-size: var(--fs-sm);
  font-weight: 600;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--c-border2);
  background: var(--c-surface2);
  color: var(--c-text);
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 0.15s var(--ease-out), background 0.15s var(--ease-out);
}
.strip-btn:hover { border-color: var(--c-text2); background: var(--c-surface3); }
.strip-btn:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 2px; }

.failures-panel {
  background: var(--c-surface);
  border: 1px solid var(--c-failed-line);
  border-radius: var(--radius-lg);
  padding: 18px 20px 12px;
  margin-bottom: 28px;
}
.failures-head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-bottom: 10px;
}
.failures-head h2 {
  font-size: var(--fs-xl);
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--c-text);
}
.failures-count {
  font-size: var(--fs-md);
  color: var(--c-text2);
  font-variant-numeric: tabular-nums;
}
.failures-copy { margin-left: auto; }
.failures-list { list-style: none; }
.failure-row {
  font: inherit;
  color: inherit;
  text-align: left;
  width: 100%;
  display: grid;
  grid-template-columns: 10px minmax(0, 2fr) minmax(0, 3fr);
  align-items: baseline;
  gap: 4px 14px;
  padding: 11px 10px;
  border: 0;
  border-top: 1px solid var(--c-border);
  background: none;
  cursor: pointer;
  border-radius: 0;
}
.failures-list li:first-child .failure-row { border-top: 0; }
.failure-row:hover { background: var(--c-surface2); }
.failure-row:focus-visible {
  outline: 2px solid var(--c-accent);
  outline-offset: -2px;
  border-radius: var(--radius-sm);
}
.failure-row .status-dot { align-self: center; }
.failure-row-main { display: flex; flex-direction: column; min-width: 0; }
.failure-row-name {
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--c-text);
  overflow-wrap: anywhere;
}
.failure-row-file {
  font-size: var(--fs-sm);
  color: var(--c-text2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.failure-row-reason {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--c-failed-ink);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.failures-more {
  font: inherit;
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-text2);
  background: none;
  border: 0;
  padding: 10px 10px 6px;
  cursor: pointer;
}
.failures-more:hover { color: var(--c-text); }
.failures-more:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 2px; }

.filter-chip {
  font: inherit;
  font-size: var(--fs-xs);
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  border: 1px solid var(--c-accent);
  background: var(--c-accent-dim);
  color: var(--c-accent-ink);
  cursor: pointer;
}
.filter-chip[hidden] { display: none; }
.filter-chip:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 2px; }

/* Failure strip at the top of a failed run */
.failure-strip {
  background: var(--c-failed-dim);
  border: 1px solid var(--c-failed-line);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  margin-bottom: 16px;
}
.failure-strip.error {
  background: var(--c-error-dim);
  border-color: color-mix(in srgb, var(--c-error) 32%, transparent);
}
.failure-strip-label {
  font-size: var(--fs-sm);
  font-weight: 700;
  color: var(--c-failed-ink);
  margin-bottom: 4px;
}
.failure-strip.error .failure-strip-label { color: var(--c-error-ink); }
.failure-strip-reason {
  font-family: var(--font-mono);
  font-size: var(--fs-md);
  line-height: 1.5;
  color: var(--c-text);
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.failure-strip-checks {
  list-style: none;
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.failure-strip-checks li { display: flex; flex-wrap: wrap; gap: 2px 10px; font-size: var(--fs-md); }
.failure-strip-check-name { color: var(--c-text); font-weight: 600; }
.failure-strip-check-detail { font-family: var(--font-mono); font-size: var(--fs-sm); color: var(--c-failed-ink); }
.failure-strip-check-loc { font-family: var(--font-mono); font-size: var(--fs-sm); color: var(--c-text2); overflow-wrap: anywhere; }
.failure-strip-more { color: var(--c-text2); font-size: var(--fs-sm); }
.failure-strip-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }

@media (max-width: 640px) {
  .failures-panel { padding: 16px 14px 10px; }
  .failures-copy { margin-left: 0; }
  .failure-row { grid-template-columns: 10px minmax(0, 1fr); }
  .failure-row-reason { grid-column: 2; }
  .detail-panel { scroll-margin-top: 8px; }
}

/* ================================================================
   Accessibility helpers: screen-reader text, skip link, focus rings
   ================================================================ */
.sr-only {
  position: absolute;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.skip-link {
  position: absolute;
  left: 16px; top: -48px;
  z-index: 200;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  background: var(--c-accent-strong);
  color: var(--c-on-accent);
  font-weight: 600;
  text-decoration: none;
}
.skip-link:focus { top: 8px; }
main:focus { outline: none; }

.tree-row:focus-visible,
.session-log-section-header:focus-visible,
.chart-card:focus-visible,
.pass-rate-bar:focus-visible,
.phase-tab-panel:focus-visible {
  outline: 2px solid var(--c-accent);
  outline-offset: -2px;
}
.run-pill:focus-visible,
.sub-tab-btn:focus-visible,
.phase-tab-btn:focus-visible,
.filter-btn:focus-visible,
.session-log-level-btn:focus-visible,
.tree-expand-btn:focus-visible,
.show-more-btn:focus-visible {
  outline: 2px solid var(--c-accent);
  outline-offset: 2px;
}
.charts-section-title { font-family: inherit; }

.tree-empty {
  padding: 24px 20px;
  color: var(--c-text2);
  font-size: var(--fs-md);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}
.tree-empty[hidden] { display: none; }

@media (forced-colors: active) {
  .status-dot { forced-color-adjust: none; }
  .tree-row.selected, .run-pill.selected, .sub-tab-btn.active, .phase-tab-btn.active,
  .filter-btn.active, .tab-btn.active { outline: 2px solid Highlight; }
}

/* ================================================================
   Responsive
   ================================================================ */
@media (max-width: 768px) {
  .counters { grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px; }
  .counter-card { padding: 14px 12px; }
  .charts-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
  .header { padding: 0 16px; }
  .tabs { padding: 0 16px; }
  .summary-container, .report-container { padding: 16px; }
  .info-grid { grid-template-columns: 1fr; gap: 4px 0; }
  .info-label { margin-top: 8px; }
}

/* ================================================================
   Typography details
   ================================================================ */
h1, h2, h3, h4 { text-wrap: balance; }
.failure-row-reason, .failure-strip-reason, .log-entry-msg, .check-card-detail { text-wrap: pretty; }
/* Figures line up in columns and don't jitter as they change */
.summary-hero-pct, .summary-hero-dur-value, .counter-card .value, .counter-pct,
.donut-counts, .pass-rate-bar-stats, .tree-badge, .run-pill, .phase-meta,
.log-entry-time, .procedure-step-duration, .retry-badge, .session-log-section-count,
.charts-section-count { font-variant-numeric: tabular-nums; }

/* Phones: the header keeps the title and the result badge on one line;
   the run's date and duration are on the Report tab. */
@media (max-width: 640px) {
  .header { gap: 10px; padding: 0 16px; }
  .header h1 { white-space: nowrap; }
  .header .meta > span:not(.meta-badge) { display: none; }
}

/* ================================================================
   Phones and touch screens
   ================================================================ */
/* WCAG 2.5.8: no control smaller than 24px, whatever the pointer */
.filter-btn, .filter-chip, .session-log-level-btn { min-height: 24px; }
.tree-expand-btn { min-width: 24px; min-height: 24px; justify-content: center; }

/* Tab strips scroll sideways instead of wrapping or clipping a tab */
.tabs, .sub-tabs {
  overflow-x: auto;
  scrollbar-width: none;
  overscroll-behavior-x: contain;
}
.tabs::-webkit-scrollbar, .sub-tabs::-webkit-scrollbar { display: none; }
.tab-btn, .sub-tab-btn { white-space: nowrap; flex-shrink: 0; }
/* Phase tabs share the width; in a narrow panel the timing drops below the label */
.phase-tab-btn { flex-wrap: wrap; min-width: 0; row-gap: 2px; }
.phase-tab-label { display: inline-flex; align-items: center; gap: 8px; white-space: nowrap; }
@media (max-width: 768px) {
  .phase-tab-btn { padding-left: 6px; padding-right: 6px; letter-spacing: 0.02em; }
  .phase-tab-label { gap: 6px; }
}
@media (max-width: 360px) {
  .phase-tab-btn { text-transform: none; letter-spacing: 0; }
}

/* The test title takes focus when a phone switches to it; no ring there */
.detail-header h2:focus { outline: none; }

/* The back button only exists on the phone layout */
.detail-back { display: none; }

/* Phones: the test list and a test's detail take turns on screen. */
@media (max-width: 768px) {
  .tests-layout { display: block; height: auto; }
  .tree-panel { width: 100%; min-width: 0; border-right: none; }
  .tree-content { overflow: visible; }
  .detail-panel { display: none; overflow: visible; padding: 12px 16px 32px; }
  .tests-layout.show-detail .tree-panel { display: none; }
  .tests-layout.show-detail .detail-panel { display: block; }
  .detail-back {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin: 0 0 12px -8px;
    padding: 8px 10px 8px 6px;
    font: inherit;
    font-size: var(--fs-md);
    font-weight: 600;
    color: var(--c-accent-ink);
    background: none;
    border: 0;
    border-radius: var(--radius-sm);
    cursor: pointer;
  }
  .detail-back:hover { background: var(--c-surface2); }
}
@media (max-width: 640px) {
  .tab-btn { padding-left: 14px; padding-right: 14px; }
}

/* Touch screens: 44px targets, whatever the width */
@media (pointer: coarse) {
  .tab-btn, .sub-tab-btn, .phase-tab-btn, .run-pill, .filter-btn, .filter-chip,
  .strip-btn, .failures-more, .session-log-level-btn, .session-log-action-btn,
  .detail-back, .search-input, .session-log-search, .detail-cmd {
    min-height: 44px;
  }
  .filter-btn, .filter-chip, .session-log-level-btn { padding-left: 14px; padding-right: 14px; }
  .tree-row, .session-log-section-header, .retry-card-header, .pass-rate-bar { min-height: 44px; }
  .tree-expand-btn, .theme-toggle { min-width: 44px; min-height: 44px; }
  .filter-toggles, .session-log-level-filters { gap: 8px; }
  .run-pills { gap: 8px; }
}

/* ================================================================
   Theme toggle
   ================================================================ */
.theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--c-border2);
  background: transparent;
  color: var(--c-text2);
  cursor: pointer;
  flex-shrink: 0;
}
.theme-toggle:hover { color: var(--c-text); background: var(--c-surface2); }
.theme-toggle .icon-sun { display: none; }
:root[data-theme-shown="dark"] .theme-toggle .icon-sun { display: block; }
:root[data-theme-shown="dark"] .theme-toggle .icon-moon { display: none; }

/* ================================================================
   Print: light, without navigation, scroll areas opened up
   ================================================================ */
@media print {
  body { background: #fff; min-height: 0; }
  .skip-link, .tabs, .theme-toggle, .tree-panel,
  .detail-cmd-hint, .artifact-expand, .strip-btn, .session-log-search,
  .session-log-actions { display: none !important; }
  .header { position: static; backdrop-filter: none; background: none; margin-bottom: 16px; }
  .tests-layout { display: block; height: auto; }
  .detail-panel { overflow: visible; padding: 0; }
  pre, .phase-log, [class*="longrepr"] { max-height: none !important; overflow: visible !important; white-space: pre-wrap; }
  .counter-card, .chart-card, .check-card, .failure-strip, .failures-panel, .procedure-step,
  .retry-card, .log-entry { break-inside: avoid; }
  * { box-shadow: none !important; }
  .meta-badge, .tree-badge, .run-pill, .detail-header-outcome, .check-card,
  .failure-strip, .counter-card, .log-entry-level, .pass-rate-bar-fill, .legend-dot, .status-dot {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
}
"""
)
