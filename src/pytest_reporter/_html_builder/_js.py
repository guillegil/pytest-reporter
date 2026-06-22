"""Inline JavaScript for the HTML report template.

The /*__REPORT_DATA__*/ and /*__SYSTEM_METADATA_JSON__*/ markers
must remain intact — they are substituted at report-build time.
"""

from __future__ import annotations

JS: str = r"""/*__REPORT_DATA__*/

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

// Chevron SVG — module-scope helper reused by session-log sections, check-cards,
// and the plugins collapsible.  cls: CSS class to set on the <svg> element.
function chevronSvg(cls) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('class', cls || 'chevron');
  svg.setAttribute('width','16'); svg.setAttribute('height','16');
  svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('fill','none');
  svg.setAttribute('stroke','currentColor'); svg.setAttribute('stroke-width','2');
  svg.setAttribute('stroke-linecap','round'); svg.setAttribute('stroke-linejoin','round');
  svg.innerHTML = '<polyline points="9 18 15 12 9 6"/>';
  return svg;
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

// ─── Tree compaction transform (pure — never mutates input) ──────────────
// Step 1: Strip the longest common leading single-child, no-own-tests prefix.
function commonPrefixStrip(root) {
  let node = root;
  while (true) {
    const keys = Object.keys(node.children);
    if (keys.length !== 1) break;
    if (node.tests && node.tests.length > 0) break;
    node = node.children[keys[0]];
  }
  return node;
}

// Step 2: Recursively collapse single-child-dir chains into breadcrumb nodes.
// A node with no own tests and exactly one child dir is merged with that child,
// accumulating _segments. Stops when the merged node has 2+ children or own tests.
function collapseChains(node) {
  // Recurse into children first (post-order)
  const newChildren = {};
  Object.entries(node.children).forEach(([k, v]) => { newChildren[k] = collapseChains(v); });

  // Build a working copy (never mutate input)
  let cur = { name: node.name, _segments: node._segments || [node.name],
               children: newChildren, tests: node.tests };

  // Merge while single-child-dir and no own tests
  while (!cur.tests.length && Object.keys(cur.children).length === 1) {
    const childKey = Object.keys(cur.children)[0];
    const child = cur.children[childKey];
    const childSegs = child._segments || [childKey];
    cur = { name: cur._segments.concat(childSegs).join(' / '),
            _segments: cur._segments.concat(childSegs),
            children: child.children,
            tests: child.tests };
  }
  return cur;
}

// Step 3: Flag file nodes (no child dirs, exactly one test) for merged rendering.
function flagSingleFnMerges(node) {
  const newChildren = {};
  Object.entries(node.children).forEach(([k, v]) => { newChildren[k] = flagSingleFnMerges(v); });
  const cur = { name: node.name, _segments: node._segments, children: newChildren,
                tests: node.tests };
  if (!Object.keys(cur.children).length && cur.tests.length === 1) {
    cur._mergedTest = cur.tests[0];
  }
  return cur;
}

// Compose all three steps into a single pure transform.
// rawRoot is never mutated; a new node graph is returned.
function compactTree(rawRoot) {
  const stripped = commonPrefixStrip(rawRoot);
  const collapsed = collapseChains(stripped);
  return flagSingleFnMerges(collapsed);
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

// Accessible numeric counts below a donut (WCAG SC 1.4.1 — not color alone).
// Shows: ✓N ✕N ⊘N ⚠N  ·  NN% pass
function donutCountsEl(counts) {
  const total = counts.passed + counts.failed + counts.skipped + counts.error;
  const rate = total > 0 ? Math.round((counts.passed / total) * 100) : 0;
  return el('div', {className:'donut-counts'},
    el('span', {className:'dc-passed', 'aria-label':'passed'}, '✓' + counts.passed),
    el('span', {className:'dc-failed', 'aria-label':'failed'}, '✕' + counts.failed),
    el('span', {className:'dc-skipped', 'aria-label':'skipped'}, '⊘' + counts.skipped),
    el('span', {className:'dc-error', 'aria-label':'error'}, '⚠' + counts.error),
    el('span', {className:'dc-rate', 'aria-label':'pass rate'}, '· ' + rate + '%')
  );
}

// Walk the buildTree result to the node at path[]; returns null if not found.
function getNodeAtPath(tree, pathParts) {
  let node = tree;
  for (const part of pathParts) {
    if (!node.children[part]) return null;
    node = node.children[part];
  }
  return node;
}

// Collect descendant nodes at exactly `depth` levels below `node`.
// depth=1 → direct children; depth=2 → grandchildren; etc.
function collectAtDepth(node, depth, pathSoFar) {
  if (depth === 0) return [{node, path: pathSoFar}];
  const results = [];
  Object.entries(node.children).forEach(([name, child]) => {
    const sub = collectAtDepth(child, depth - 1, pathSoFar + (pathSoFar ? '/' : '') + name);
    results.push(...sub);
  });
  return results;
}

// Render a donut grid section for an array of {node, path, label} entries.
function renderDonutGroup(entries, sectionLabel) {
  if (entries.length === 0) return null;
  const cards = entries.map(({node, path, label}) => {
    const a = nodeAgg(node);
    return el('div', {className:'chart-card', onClick:()=>navigateToGroup(path)},
      el('h3', null, label),
      donutSVG(a, 110),
      donutCountsEl(a),
      legendEl(a)
    );
  });
  const title = el('div', {className:'charts-section-title'},
    sectionLabel,
    el('span', {className:'charts-section-count'}, String(entries.length))
  );
  return el('div', {className:'charts-section'}, title, el('div', {className:'charts-grid'}, cards));
}

// Render a pass-rate bars section for an array of {node, path, label} entries.
// AAA: values always visible as text (not color alone).
function renderBarsGroup(entries, sectionLabel) {
  if (entries.length === 0) return null;
  const rows = entries.map(({node, path, label}) => {
    const a = nodeAgg(node);
    const total = a.total || 1;
    const rate = Math.round((a.passed / total) * 100);
    const fillPct = rate.toFixed(1) + '%';
    return el('div', {className:'pass-rate-bar', onClick:()=>navigateToGroup(path), role:'button', tabindex:'0'},
      el('span', {className:'pass-rate-bar-name', title:label}, label),
      el('div', {className:'pass-rate-bar-track'},
        el('div', {className:'pass-rate-bar-fill', style:'width:' + fillPct})
      ),
      el('div', {className:'pass-rate-bar-stats'},
        el('span', {className:'prs-rate'}, rate + '%'),
        ' ',
        el('span', {className:'prs-passed', 'aria-label':'passed'}, '✓' + a.passed),
        ' ',
        el('span', {className:'prs-failed', 'aria-label':'failed'}, '✕' + a.failed),
        a.skipped > 0 ? el('span', {className:'prs-skipped', 'aria-label':'skipped'}, ' ⊘' + a.skipped) : null,
        a.error > 0 ? el('span', {className:'prs-error', 'aria-label':'error'}, ' ⚠' + a.error) : null
      )
    );
  });
  const title = el('div', {className:'charts-section-title'},
    sectionLabel,
    el('span', {className:'charts-section-count'}, String(entries.length))
  );
  return el('div', {className:'charts-section'}, title,
    el('div', {className:'pass-rate-bars-section'}, rows)
  );
}

// Determine renderer for a group based on group.style + density heuristic.
// 'auto' density heuristic (pinned threshold): depth >= 2 OR child count > 5 → bars; else donuts.
// Comment kept in sync with design spec: "depth >= 2 OR child count > 5"
function pickRenderer(style, depth, childCount) {
  if (style === 'bars') return 'bars';
  if (style === 'donut') return 'donut';
  // style === 'auto': density heuristic
  return (depth >= 2 || childCount > 5) ? 'bars' : 'donut';
}

// Render all configured dashboard groups from DATA.dashboard.
// When is_default=true, falls back to built-in default: depth-1 children of
// each top-level tree node, using style='auto' (no all-tests donut).
function renderDashboardGroups(dashboard, container, tree) {
  if (dashboard.is_default) {
    // Default grouping: depth-1 feature donuts per top-level group (no all-tests donut).
    const topGroups = Object.entries(tree.children);
    topGroups.forEach(([groupName, groupNode]) => {
      const features = Object.entries(groupNode.children);
      if (features.length === 0) return;
      const entries = features.map(([fname, fnode]) => ({
        node: fnode,
        path: groupName + '/' + fname,
        label: fname,
      }));
      const renderer = pickRenderer('auto', 1, features.length);
      const sectionLabel = groupName + ' — Features';
      const section = renderer === 'bars'
        ? renderBarsGroup(entries, sectionLabel)
        : renderDonutGroup(entries, sectionLabel);
      if (section) container.appendChild(section);
    });
    return;
  }

  // Config-driven grouping: iterate groups in order.
  dashboard.groups.forEach(group => {
    const pathParts = group.path;
    const targetNode = getNodeAtPath(tree, pathParts);
    const groupLabel = group.label || pathParts[pathParts.length - 1] || '';

    // include_self: render an aggregate card for the path node itself.
    if (group.include_self && targetNode) {
      const selfPath = pathParts.join('/');
      const selfSectionLabel = groupLabel + ' (aggregate)';
      const selfEntries = [{node: targetNode, path: selfPath, label: groupLabel}];
      const selfRenderer = pickRenderer(group.style, 0, 1);
      const selfSection = selfRenderer === 'bars'
        ? renderBarsGroup(selfEntries, selfSectionLabel)
        : renderDonutGroup(selfEntries, selfSectionLabel);
      if (selfSection) container.appendChild(selfSection);
    }

    // Depth-N descendants: collect nodes at group.depth levels below path.
    if (targetNode && group.depth > 0) {
      const descendants = collectAtDepth(targetNode, group.depth, pathParts.join('/'));
      if (descendants.length === 0) return;
      const entries = descendants.map(({node, path}) => {
        const parts = path.split('/');
        return {node, path, label: parts[parts.length - 1]};
      });
      const renderer = pickRenderer(group.style, group.depth, entries.length);
      const sectionLabel = groupLabel + (group.depth > 1 ? ' — Depth ' + group.depth : ' — Features');
      const section = renderer === 'bars'
        ? renderBarsGroup(entries, sectionLabel)
        : renderDonutGroup(entries, sectionLabel);
      if (section) container.appendChild(section);
    }
  });
}

// ─── Summary Tab ─────────────────────────────────────────────────────
function renderSummary() {
  const panel = document.getElementById('tab-summary');
  const container = el('div', {className:'summary-container'});
  const agg = aggTests(DATA.tests);
  const total = agg.total || 1;
  const passRate = Math.round((agg.passed / total) * 100);

  // Count retried tests
  let retriedCount = 0;
  DATA.tests.forEach(t => t.runs.forEach(r => { if (r.retries && r.retries.attempts > 0) retriedCount++; }));

  // ── Hero: pass rate + ratio bar ──
  const hero = el('div', {className:'summary-hero'});
  const rateSection = el('div', {className:'summary-hero-rate'});
  const rateClass = passRate >= 90 ? 'good' : passRate >= 70 ? 'warn' : 'bad';
  rateSection.appendChild(el('div', {className:'summary-hero-pct ' + rateClass}, passRate + '%'));
  rateSection.appendChild(el('div', {className:'summary-hero-pct-label'}, 'Pass rate'));
  hero.appendChild(rateSection);

  const heroBody = el('div', {className:'summary-hero-body'});
  heroBody.appendChild(el('h3', null, 'Test Results Distribution'));
  const barWrap = el('div', {className:'ratio-bar-wrap'});
  const bar = el('div', {className:'ratio-bar'});
  STATUSES.forEach(s => {
    if (!agg[s]) return;
    const pct = (agg[s] / total) * 100;
    const seg = el('div', {className:'ratio-bar-seg ' + s, style:'width:' + pct.toFixed(2) + '%'});
    bar.appendChild(seg);
  });
  barWrap.appendChild(bar);

  const barLegend = el('div', {className:'ratio-bar-legend'});
  STATUSES.forEach(s => {
    if (!agg[s]) return;
    const pct = Math.round((agg[s] / total) * 100);
    const item = el('span', {className:'ratio-bar-legend-item'},
      el('span', {className:'legend-dot', style:'background:' + COLORS[s]}),
      el('strong', null, String(agg[s])),
      LABELS[s] + ' (' + pct + '%)'
    );
    barLegend.appendChild(item);
  });
  barWrap.appendChild(barLegend);
  heroBody.appendChild(barWrap);
  hero.appendChild(heroBody);
  container.appendChild(hero);

  // ── Counter cards ──
  const counterDefs = [{k:'passed',l:'Passed'},{k:'failed',l:'Failed'},{k:'skipped',l:'Skipped'},{k:'error',l:'Errors'}];
  if (DATA.retries_enabled) counterDefs.push({k:'retried',l:'Retried'});
  counterDefs.push({k:'total',l:'Total'});
  const counterData = Object.assign({}, agg, {retried: retriedCount});
  const counters = el('div', {className:'counters'},
    counterDefs.map(c => {
      const val = counterData[c.k];
      const card = el('div', {className:'counter-card ' + c.k},
        el('div', {className:'value'}, String(val)),
        el('div', {className:'label'}, c.l)
      );
      if (c.k !== 'total' && total > 0) {
        const pct = Math.round((val / total) * 100);
        card.appendChild(el('div', {className:'counter-pct'}, pct + '%'));
      }
      return card;
    })
  );
  container.appendChild(counters);

  // ── Config-driven dashboard groups (donuts or pass-rate bars per group) ──
  // NOTE: "All Tests" whole-suite donut REMOVED (configurable-dashboard change).
  // Top counter cards already convey suite-level totals. Groups are config-driven.
  const tree = buildTree(DATA.tests);
  renderDashboardGroups(DATA.dashboard, container, tree);

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
      // D4 fix: match via data-seg attribute membership instead of textContent,
      // so breadcrumb-collapsed rows (e.g. "ctec / FOX") still match on "ctec".
      const segs = row.querySelectorAll('[data-seg]');
      const matched = Array.from(segs).some(s => s.getAttribute('data-seg') === part);
      if (matched) {
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
  const rawTree = buildTree(DATA.tests);
  const compacted = compactTree(rawTree);
  Object.entries(compacted.children).forEach(([name, node]) => {
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
  // Merged single-function file: delegate entirely to renderTestLeaf.
  if (node._mergedTest) {
    return renderTestLeaf(node._mergedTest, depth);
  }

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

  // Build label: breadcrumb for collapsed chains (_segments), plain name otherwise.
  // Each segment emits a data-seg attribute for navigateToGroup D4 matching.
  const nameEl = el('span', {className:'tree-name'});
  const segs = node._segments || [name];
  segs.forEach((seg, i) => {
    nameEl.appendChild(el('span', {'data-seg': seg}, seg));
    if (i < segs.length - 1) {
      nameEl.appendChild(el('span', {className:'crumb-sep'}, ' / '));
    }
  });

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
    if (e.data && e.data._type === 'table') {
      row.appendChild(renderInlineTable(e.data));
    } else if (e.data) {
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

function renderInlineTable(td) {
  const LIMIT = 20;
  const wrap = el('div', {className:'log-entry-table-wrap'});

  // Table name header
  if (td.name) {
    const nameRow = el('div', {className:'log-entry-table-name'},
      td.name,
      el('span', {className:'table-badge'}, 'TABLE')
    );
    wrap.appendChild(nameRow);
  }

  const scrollWrap = el('div', {className:'log-entry-table-scroll'});
  const table = document.createElement('table');
  table.className = 'log-entry-table';

  // Header
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  (td.columns || []).forEach(col => {
    const th = document.createElement('th');
    th.textContent = col;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  // Body
  const tbody = document.createElement('tbody');
  const allRows = td.rows || [];
  allRows.forEach((row, i) => {
    const tr = document.createElement('tr');
    if (i >= LIMIT) tr.style.display = 'none';
    row.forEach(cell => {
      const tdc = document.createElement('td');
      tdc.textContent = cell != null ? String(cell) : '';
      tdc.title = cell != null ? String(cell) : '';
      tr.appendChild(tdc);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  scrollWrap.appendChild(table);
  wrap.appendChild(scrollWrap);

  // Footer
  const totalRows = td.total_rows || allRows.length;
  if (totalRows > 0) {
    const footer = el('div', {className:'log-entry-table-footer'});
    const showing = Math.min(LIMIT, allRows.length);
    const info = el('span', null, totalRows <= LIMIT
      ? totalRows + ' rows \u00d7 ' + (td.columns || []).length + ' columns'
      : 'Showing ' + showing + ' of ' + totalRows + ' rows');
    footer.appendChild(info);

    if (allRows.length > LIMIT) {
      let expanded = false;
      const toggleBtn = el('button', {className:'log-entry-table-toggle'},
        'Show all ' + allRows.length + ' rows');
      toggleBtn.addEventListener('click', () => {
        expanded = !expanded;
        const trs = tbody.querySelectorAll('tr');
        for (let i = LIMIT; i < trs.length; i++) {
          trs[i].style.display = expanded ? '' : 'none';
        }
        toggleBtn.textContent = expanded
          ? 'Show first ' + LIMIT + ' rows'
          : 'Show all ' + allRows.length + ' rows';
        info.textContent = expanded
          ? allRows.length + ' of ' + totalRows + ' rows'
          : 'Showing ' + showing + ' of ' + totalRows + ' rows';
      });
      footer.appendChild(toggleBtn);
    }

    if (td.truncated && td.artifact_name) {
      footer.appendChild(el('span', {style:'color:var(--c-text3)'}, '\u2022'));
      footer.appendChild(el('span', {className:'log-entry-table-toggle',
        style:'cursor:default'}, 'Full table in Artifacts \u2192 ' + td.artifact_name));
    }

    wrap.appendChild(footer);
  }

  return wrap;
}

function _appendCheckInline(row, check) {
  if (!check) return;
  const desc = check.description || '';
  if (desc) {
    row.appendChild(el('span', {className:'procedure-check-desc'}, '\u2014 ' + desc));
  }
}

// renderFormattedDesc \u2014 returns a DocumentFragment (segments present) or a
// plain TextNode (fallback for no-markup descriptions). Uses textContent only;
// NEVER innerHTML. XSS-safe: segment text is always assigned via textContent.
function renderFormattedDesc(node) {
  const segs = node.description_segments;
  if (!segs || segs.length === 0) {
    return document.createTextNode(node.description || '');
  }
  const frag = document.createDocumentFragment();
  segs.forEach(function(seg) {
    if (seg.style === 'mono') {
      const sp = document.createElement('span');
      sp.className = 'proc-mono';
      sp.textContent = seg.text;
      frag.appendChild(sp);
    } else {
      frag.appendChild(document.createTextNode(seg.text));
    }
  });
  return frag;
}

// renderNode — recursive procedure node renderer (depth 1..3).
// depth 1 = L1 step, depth 2 = L2 substep, depth 3 = L3 sub-substep.
// Preserves renderFormattedDesc, _appendCheckInline, status dots, durations,
// and exc at every depth. Old 2-level procedure.json is a depth-<=2 tree and
// renders identically (leaf substeps have no .substeps → recursion terminates).
function renderNode(node, depth) {
  const cls = depth === 1 ? 'procedure-step'
            : depth === 2 ? 'procedure-substep'
            : 'procedure-substep procedure-subsubstep';
  const row = el('div', {className: cls});
  const descSpan = el('span', {className: 'procedure-step-desc'});
  descSpan.appendChild(renderFormattedDesc(node));
  const hasKids = node.substeps && node.substeps.length > 0;
  // Parent nodes (depth 1 or anything with children) get a trailing dot:
  // "1.", "1.1.", "2." — leaves stay bare: "1.1.1".
  const numText = (depth === 1 || hasKids) ? node.number + '.' : node.number;
  const header = el('div', {className: 'procedure-step-header'},
    el('span', {className: `status-dot ${node.outcome || 'passed'}`}),
    el('span', {className: 'procedure-step-number'}, numText),
    descSpan
  );
  _appendCheckInline(header, node.check);
  if (node.duration_seconds > 0) {
    header.appendChild(el('span', {className: 'procedure-step-duration'},
      node.duration_seconds.toFixed(2) + 's'));
  }
  row.appendChild(header);
  if (node.exc) {
    const excEl = el('div', {className: 'procedure-step-exc'});
    excEl.textContent = node.exc.type + ': ' + node.exc.msg;
    row.appendChild(excEl);
  }
  if (hasKids) {
    const nextDepth = depth < 3 ? depth + 1 : 3;
    const kids = el('div', {className: 'procedure-substeps'});
    node.substeps.forEach(function(child) {
      kids.appendChild(renderNode(child, nextDepth));
    });
    row.appendChild(kids);
  }
  return row;
}

function renderProcedure(proc) {
  const list = el('div', {className: 'procedure-list'});
  (proc.steps || []).forEach(function(s) { list.appendChild(renderNode(s, 1)); });
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
    const isExpanded = status === 'failed';
    const card = el('div', {className:`check-card ${status}${isExpanded ? ' expanded' : ''}`});

    const header = el('div', {className:'check-card-header'});
    header.setAttribute('role', 'button');
    header.setAttribute('tabindex', '0');
    header.setAttribute('aria-expanded', String(isExpanded));
    header.appendChild(chevronSvg('check-card-chevron'));
    header.appendChild(el('span', {className:`status-dot ${status}`}));
    header.appendChild(el('span', {className:'check-name'}, check.name || ('Check #' + (idx + 1))));
    if (check.description) {
      header.appendChild(el('span', {className:'check-desc'}, check.description));
    }
    header.appendChild(el('span', {className:'check-type-badge'}, check.check_type || ''));

    function toggleCard() {
      const ex = card.classList.toggle('expanded');
      header.setAttribute('aria-expanded', String(ex));
    }
    header.addEventListener('click', () => toggleCard());
    header.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCard(); }
    });
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
    header.appendChild(chevronSvg('session-log-chevron'));
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
      childHeader.appendChild(chevronSvg('session-log-chevron'));
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

  // Metadata panel (server-side rendered; injected as HTML string at build time)
  const _sysMeta = /*__SYSTEM_METADATA_JSON__*/;
  if (_sysMeta) { container.insertAdjacentHTML('beforeend', _sysMeta); }

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
renderReport();"""
