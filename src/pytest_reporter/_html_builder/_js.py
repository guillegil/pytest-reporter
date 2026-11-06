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

// Status fills come from the CSS tokens, so charts follow the theme.
const COLORS = {passed:'var(--c-passed)',failed:'var(--c-failed)',skipped:'var(--c-skipped)',error:'var(--c-error)'};
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
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  svg.setAttribute('width','16'); svg.setAttribute('height','16');
  svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('fill','none');
  svg.setAttribute('stroke','currentColor'); svg.setAttribute('stroke-width','2');
  svg.setAttribute('stroke-linecap','round'); svg.setAttribute('stroke-linejoin','round');
  svg.innerHTML = '<polyline points="9 18 15 12 9 6"/>';
  return svg;
}

// Polite live region: tells screen readers about results they can't see
// change (copied, number of tests shown).
function announce(msg) {
  let live = document.getElementById('sr-live');
  if (!live) {
    live = el('div', {id:'sr-live', className:'sr-only', 'aria-live':'polite', role:'status'});
    document.body.appendChild(live);
  }
  live.textContent = '';
  setTimeout(() => { live.textContent = msg; }, 30);
}

// Visually hidden text for screen readers (e.g. the outcome a dot shows).
function srText(text) { return el('span', {className:'sr-only'}, text); }

// Roving-tabindex tablist: Left/Right (and Up/Down), Home and End move
// between the tabs matched by `selector` and activate them through `select`.
function wireTablist(list, selector, select) {
  if (!list) return;
  list.addEventListener('keydown', (e) => {
    const tabs = Array.from(list.querySelectorAll(selector)).filter(t => t.offsetParent !== null);
    const idx = tabs.indexOf(document.activeElement);
    if (idx === -1) return;
    let next = -1;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (idx + 1) % tabs.length;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (idx - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = tabs.length - 1;
    if (next === -1) return;
    e.preventDefault();
    tabs[next].focus();
    select(tabs[next]);
  });
}

// Mark one button of a tab set as selected (class, aria-selected, tabindex).
function setSelectedTab(tabs, selected) {
  tabs.forEach(t => {
    const on = t === selected;
    t.classList.toggle('active', on);
    t.setAttribute('aria-selected', on ? 'true' : 'false');
    t.tabIndex = on ? 0 : -1;
  });
}

let _uid = 0;
function uid(prefix) { _uid += 1; return prefix + '-' + _uid; }

// Copy-to-clipboard helper for the "run this test" command box.
// navigator.clipboard needs a secure context (file:// qualifies) + a user
// gesture (the click); the execCommand fallback covers older/edge browsers.
function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text).catch(function() { return fallbackCopy(text); });
  }
  return Promise.resolve(fallbackCopy(text));
}
function fallbackCopy(text) {
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  } catch (e) { /* clipboard unavailable — silent no-op */ }
}
// Build the exact single-test pytest command for a run's nodeid.
// Quoted because parametrize ids ([...]) are glob/shell-special.
function testCommand(nodeid) {
  return 'pytest "' + nodeid + '"';
}
// Copy the command shown in a .detail-cmd row, with transient feedback.
function copyCommandRow(rowEl) {
  const codeEl = rowEl.querySelector('.detail-cmd-code');
  if (!codeEl) return;
  copyToClipboard(codeEl.textContent);
  const hint = rowEl.querySelector('.detail-cmd-hint');
  rowEl.classList.add('copied');
  if (hint) hint.textContent = 'Copied!';
  announce('Command copied');
  setTimeout(function() {
    rowEl.classList.remove('copied');
    if (hint) hint.textContent = 'Copy';
  }, 1400);
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
    // Class-based tests are grouped under a synthetic class node on the file
    // node (file -> class -> method), so the class label is shown once instead
    // of repeated on every method leaf. Plain functions attach to the file.
    const cls = t.aggregate.class_name;
    if (cls) {
      if (!node.children[cls]) node.children[cls] = {name:cls,children:{},tests:[],_isClass:true};
      node.children[cls].tests.push(t);
    } else {
      node.tests.push(t);
    }
  });
  return root;
}

function nodeAgg(node) {
  let p=0,f=0,s=0,e=0,dur=0,retr=0;
  node.tests.forEach(t => {
    p+=t.aggregate.passed; f+=t.aggregate.failed;
    s+=t.aggregate.skipped; e+=t.aggregate.errors;
    dur += t.aggregate.total_duration_seconds || 0;
    retr += t.runs.filter(r => r.retries && r.retries.attempts > 0).length;
  });
  Object.values(node.children).forEach(c => {
    const a = nodeAgg(c);
    p+=a.passed; f+=a.failed; s+=a.skipped; e+=a.error; dur+=a.duration; retr+=a.retried;
  });
  return {passed:p,failed:f,skipped:s,error:e,total:p+f+s+e,duration:dur,retried:retr};
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
               children: newChildren, tests: node.tests, _isClass: node._isClass };

  // Merge while single-child-dir and no own tests. A class node is NOT a
  // directory — never fold it into the file's breadcrumb.
  while (!cur.tests.length && Object.keys(cur.children).length === 1) {
    const childKey = Object.keys(cur.children)[0];
    const child = cur.children[childKey];
    if (child._isClass) break;
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
                tests: node.tests, _isClass: node._isClass };
  // Merge single-function FILE nodes into one leaf. Never merge a class node —
  // its label must stay visible even with a single method.
  if (!cur._isClass && !Object.keys(cur.children).length && cur.tests.length === 1) {
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
    cx, cy, r, fill: 'none', style: 'stroke:var(--c-track)', 'stroke-width': strokeW
  });
  svg.appendChild(track);

  if (total === 0) return svg;

  const segments = STATUSES.filter(k => counts[k] > 0);

  if (segments.length === 1) {
    const ring = svgEl('circle', {
      cx, cy, r, fill: 'none', style: 'stroke:' + COLORS[segments[0]],
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
        cx, cy, r, fill: 'none', style: 'stroke:' + COLORS[k],
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
    style: 'fill:var(--c-text)', 'font-size': Math.round(size * 0.17),
    'font-weight': '700', 'font-family': "var(--font-mono)"
  });
  totalText.textContent = total;
  svg.appendChild(totalText);

  const label = svgEl('text', {
    x: cx, y: cy + Math.round(size * 0.13),
    'text-anchor': 'middle', 'dominant-baseline': 'middle',
    style: 'fill:var(--c-text3)', 'font-size': Math.round(size * 0.075),
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
// Spoken name of a dashboard group control: counts in words, not glyphs.
function groupSummary(label, a) {
  const total = a.total || 1;
  const parts = [Math.round((a.passed / total) * 100) + '% passed'];
  STATUSES.forEach(st => { if (a[st]) parts.push(a[st] + ' ' + LABELS[st].toLowerCase()); });
  return label + ': ' + parts.join(', ') + '. Show in Tests';
}

// Enter and Space activate a role=button element, as they do a <button>.
function activateOnKey(node) {
  node.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); node.click(); }
  });
}

function renderDonutGroup(entries, sectionLabel) {
  if (entries.length === 0) return null;
  const cards = entries.map(({node, path, label}) => {
    const a = nodeAgg(node);
    const card = el('div', {className:'chart-card', onClick:()=>navigateToGroup(path), role:'button',
      tabindex:'0', 'aria-label': groupSummary(label, a)},
      el('h3', null, label),
      donutSVG(a, 110),
      donutCountsEl(a),
      legendEl(a),
      el('div', {className:'chart-card-dur'}, formatDuration(a.duration))
    );
    activateOnKey(card);
    return card;
  });
  const title = el('h2', {className:'charts-section-title'},
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
    const bar = el('div', {className:'pass-rate-bar', onClick:()=>navigateToGroup(path), role:'button', tabindex:'0',
      'aria-label': groupSummary(label, a)},
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
        a.error > 0 ? el('span', {className:'prs-error', 'aria-label':'error'}, ' ⚠' + a.error) : null,
        ' ',
        el('span', {className:'prs-dur'}, formatDuration(a.duration))
      )
    );
    activateOnKey(bar);
    return bar;
  });
  const title = el('h2', {className:'charts-section-title'},
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

  // ── Hero: pass rate + duration + ratio bar ──
  const suiteDuration = DATA.tests.reduce((a, t) => a + (t.aggregate.total_duration_seconds || 0), 0);
  const hero = el('div', {className:'summary-hero'});
  const rateSection = el('div', {className:'summary-hero-rate'});
  const rateClass = passRate >= 90 ? 'good' : passRate >= 70 ? 'warn' : 'bad';
  rateSection.appendChild(el('div', {className:'summary-hero-pct ' + rateClass}, passRate + '%'));
  rateSection.appendChild(el('div', {className:'summary-hero-pct-label'}, 'Pass rate'));
  hero.appendChild(rateSection);

  hero.appendChild(el('div', {className:'summary-hero-divider'}));

  const durSection = el('div', {className:'summary-hero-dur'});
  durSection.appendChild(el('div', {className:'summary-hero-dur-value'}, formatDuration(suiteDuration)));
  durSection.appendChild(el('div', {className:'summary-hero-dur-label'}, 'Total time'));
  hero.appendChild(durSection);

  const heroBody = el('div', {className:'summary-hero-body'});
  heroBody.appendChild(el('h2', null, 'Test Results Distribution'));
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

  const failures = renderFailuresPanel();
  if (failures) container.appendChild(failures);

  // ── Counter cards ──
  const counterDefs = [{k:'passed',l:'Passed'},{k:'failed',l:'Failed'},{k:'skipped',l:'Skipped'},{k:'error',l:'Errors'}];
  if (DATA.retries_enabled) counterDefs.push({k:'retried',l:'Retried'});
  counterDefs.push({k:'total',l:'Total'});
  const counterData = Object.assign({}, agg, {retried: retriedCount});
  const counters = el('div', {className:'counters'},
    counterDefs.map(c => {
      const val = counterData[c.k];
      // Cards with something behind them open the Tests tab filtered to it.
      const clickable = val > 0;
      const card = el(clickable ? 'button' : 'div', {className:'counter-card ' + c.k},
        el('div', {className:'value'}, String(val)),
        el('div', {className:'label'}, c.l)
      );
      if (clickable) {
        card.type = 'button';
        card.title = c.k === 'total' ? 'Show all tests' : 'Show ' + c.l.toLowerCase() + ' tests';
        card.addEventListener('click', () => {
          if (c.k === 'total') showTreeSubset(STATUSES, false);
          else if (c.k === 'retried') showTreeSubset(STATUSES, true);
          else if (c.k === 'failed' || c.k === 'error') showTreeSubset(['failed', 'error'], false);
          else showTreeSubset([c.k], false);
        });
      }
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

// Every failed or errored run, each with the line that says why, linking to
// its run in the Tests tab. Absent when nothing failed.
const FAILURES_SHOWN = 8;
function renderFailuresPanel() {
  const items = [];
  DATA.tests.forEach(t => t.runs.forEach(r => { if (isBad(r.outcome)) items.push({test:t, run:r}); }));
  if (items.length === 0) return null;

  const testCount = new Set(items.map(i => i.test)).size;
  const section = el('section', {className:'failures-panel', 'aria-labelledby':'failures-heading'});
  const head = el('div', {className:'failures-head'});
  head.appendChild(el('h2', {id:'failures-heading'}, 'Failures'));
  const runsWord = items.length === 1 ? 'run' : 'runs';
  const testsWord = testCount === 1 ? 'test' : 'tests';
  head.appendChild(el('span', {className:'failures-count'},
    items.length + ' failed ' + runsWord + ' in ' + testCount + ' ' + testsWord));

  const rerun = 'pytest ' + items.map(i => '"' + i.run.nodeid + '"').join(' ');
  const copyBtn = el('button', {className:'strip-btn failures-copy', type:'button',
    title: rerun}, 'Copy rerun command');
  copyBtn.addEventListener('click', () => {
    copyToClipboard(rerun);
    copyBtn.textContent = 'Copied';
    announce('Rerun command copied');
    setTimeout(() => { copyBtn.textContent = 'Copy rerun command'; }, 1400);
  });
  head.appendChild(copyBtn);
  section.appendChild(head);

  const list = el('ul', {className:'failures-list'});
  items.forEach((item, idx) => {
    const when = failedPhase(item.run);
    const reason = failureReason(item.run);
    const where = item.test.aggregate.file + (when && when !== 'call' ? ' · failed in ' + when : '');
    const btn = el('button', {className:'failure-row', type:'button'},
      el('span', {className:'status-dot ' + item.run.outcome, 'aria-hidden':'true'}),
      el('span', {className:'failure-row-main'},
        el('span', {className:'failure-row-name'}, runLabel(item.test, item.run)),
        el('span', {className:'failure-row-file'}, where)
      ),
      el('span', {className:'failure-row-reason', title: reason}, reason || 'No failure message')
    );
    btn.addEventListener('click', () => openRunInTests(item.test, item.run));
    const li = el('li', null, btn);
    if (idx >= FAILURES_SHOWN) li.hidden = true;
    list.appendChild(li);
  });
  section.appendChild(list);

  if (items.length > FAILURES_SHOWN) {
    const more = el('button', {className:'failures-more', type:'button', 'aria-expanded':'false'},
      'Show all ' + items.length);
    more.addEventListener('click', () => {
      const open = more.getAttribute('aria-expanded') !== 'true';
      list.querySelectorAll('li').forEach((li, i) => { if (i >= FAILURES_SHOWN) li.hidden = !open; });
      more.setAttribute('aria-expanded', open ? 'true' : 'false');
      more.textContent = open ? 'Show fewer' : 'Show all ' + items.length;
    });
    section.appendChild(more);
  }
  return section;
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
        if (parent) setTreeExpanded(parent, true);
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
  searchIconSvg.innerHTML = '<svg aria-hidden="true" focusable="false" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>';
  const searchInput = el('input', {className:'search-input', placeholder:'Search tests...', type:'search',
    'aria-label':'Search tests'});
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
    const btn = el('button', {className:`filter-btn ${status} active`, 'data-status':status,
      'aria-pressed':'true'}, LABELS[status]);
    btn.addEventListener('click', () => toggleFilter(status, btn));
    filters.appendChild(btn);
  });
  const retriedChip = el('button', {className:'filter-chip', id:'retried-chip', type:'button',
    title:'Show all tests again', 'aria-label':'Retried tests only. Show all tests again'},
    'Retried only ×');
  retriedChip.hidden = true;
  retriedChip.addEventListener('click', () => { retriedOnly = false; refreshTree(false); });
  filters.appendChild(retriedChip);
  controlsRow.appendChild(filters);

  // Expand all button
  const expandBtn = el('button', {className:'tree-expand-btn', title:'Expand all', 'aria-label':'Expand all folders', type:'button'});
  expandBtn.innerHTML = '<svg aria-hidden="true" focusable="false" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="7 13 12 18 17 13"/><polyline points="7 6 12 11 17 6"/></svg>';
  expandBtn.addEventListener('click', () => {
    treeContent.querySelectorAll('.tree-node').forEach(n => setTreeExpanded(n, true));
  });
  controlsRow.appendChild(expandBtn);

  // Collapse all button
  const collapseBtn = el('button', {className:'tree-expand-btn', title:'Collapse all', 'aria-label':'Collapse all folders', type:'button'});
  collapseBtn.innerHTML = '<svg aria-hidden="true" focusable="false" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="17 11 12 6 7 11"/><polyline points="17 18 12 13 7 18"/></svg>';
  collapseBtn.addEventListener('click', () => {
    treeContent.querySelectorAll('.tree-node').forEach(n => setTreeExpanded(n, false));
    ensureTreeTabStop();
  });
  controlsRow.appendChild(collapseBtn);

  controls.appendChild(controlsRow);
  treePanel.appendChild(controls);

  const treeContent = el('div', {className:'tree-content', role:'tree', 'aria-label':'Tests'});
  treeContent.addEventListener('keydown', onTreeKeydown);
  const rawTree = buildTree(DATA.tests);
  const compacted = compactTree(rawTree);
  Object.entries(compacted.children).forEach(([name, node]) => {
    treeContent.appendChild(renderTreeNode(name, node, 0));
  });
  treePanel.appendChild(treeContent);
  const treeEmpty = el('div', {className:'tree-empty', id:'tree-empty'},
    el('p', null, 'No tests match the search and filters.'));
  const resetBtn = el('button', {className:'strip-btn', type:'button'}, 'Show all tests');
  resetBtn.addEventListener('click', () => {
    searchQuery = '';
    searchInput.value = '';
    retriedOnly = false;
    activeFilters = new Set(STATUSES);
    refreshTree(false);
    searchInput.focus();
  });
  treeEmpty.appendChild(resetBtn);
  treeEmpty.hidden = true;
  treePanel.appendChild(treeEmpty);

  // Right panel
  const detailPanel = el('div', {className:'detail-panel'});
  detailPanel.innerHTML = `<div class="detail-empty">
    <svg aria-hidden="true" focusable="false" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>
    <span>Select a test to view details</span>
  </div>`;

  layout.appendChild(treePanel);
  layout.appendChild(detailPanel);
  panel.appendChild(layout);

  // A red run opens the Tests tab on its failures, with the first one shown.
  const failing = DATA.tests.filter(t => getOverallOutcome(t) === 'failed');
  if (failing.length > 0) {
    activeFilters = new Set(['failed', 'error']);
    refreshTree(true);
    const firstLeaf = Array.from(treeContent.querySelectorAll('.tree-node'))
      .find(n => n._test && n.style.display !== 'none');
    if (firstLeaf) {
      const row = firstLeaf.querySelector(':scope > .tree-row');
      if (row) markTreeSelected(row);
      showTestDetail(firstLeaf._test);
    }
  }
  ensureTreeTabStop();
}

// ─── Tree keyboard support (WAI-ARIA tree pattern) ──────────────────
// Rows are role=treeitem with aria-level; the wrapping divs are role=none.
// One row at a time has tabindex=0 (roving tab stop).
function treeRowOf(node) { return node ? node.querySelector(':scope > .tree-row') : null; }

function setTreeExpanded(node, open) {
  const row = treeRowOf(node);
  if (!row || !row.hasAttribute('aria-expanded')) return;
  node.classList.toggle('expanded', open);
  row.setAttribute('aria-expanded', open ? 'true' : 'false');
}

// Shown in the tree (not filtered out, not inside a collapsed folder). Works
// while the Tests tab itself is hidden, unlike offsetParent.
function isTreeRowShown(row) {
  let e = row.parentElement;
  while (e && !e.classList.contains('tree-content')) {
    if (e.style.display === 'none') return false;
    if (e.classList.contains('tree-children') && !e.parentElement.classList.contains('expanded')) return false;
    e = e.parentElement;
  }
  return true;
}

function visibleTreeRows() {
  return Array.from(document.querySelectorAll('.tree-content .tree-row')).filter(isTreeRowShown);
}

function setTreeTabStop(row) {
  document.querySelectorAll('.tree-content .tree-row[tabindex="0"]').forEach(r => { r.tabIndex = -1; });
  if (row) row.tabIndex = 0;
}

// Keep exactly one reachable row: the current stop if visible, else the
// selected test, else the first visible row.
function ensureTreeTabStop() {
  const rows = visibleTreeRows();
  const current = rows.find(r => r.tabIndex === 0);
  if (current) return;
  setTreeTabStop(rows.find(r => r.classList.contains('selected')) || rows[0] || null);
}

function markTreeSelected(row) {
  document.querySelectorAll('.tree-content .tree-row.selected').forEach(r => {
    r.classList.remove('selected');
    if (r.hasAttribute('aria-selected')) r.setAttribute('aria-selected', 'false');
  });
  row.classList.add('selected');
  row.setAttribute('aria-selected', 'true');
  setTreeTabStop(row);
}

function onTreeKeydown(e) {
  const row = e.target.closest && e.target.closest('.tree-row');
  if (!row) return;
  const rows = visibleTreeRows();
  const idx = rows.indexOf(row);
  const node = row.parentElement;
  const isFolder = row.hasAttribute('aria-expanded');
  const open = isFolder && node.classList.contains('expanded');
  let target = null;
  switch (e.key) {
    case 'ArrowDown': target = rows[idx + 1]; break;
    case 'ArrowUp': target = rows[idx - 1]; break;
    case 'Home': target = rows[0]; break;
    case 'End': target = rows[rows.length - 1]; break;
    case 'ArrowRight':
      if (isFolder && !open) { setTreeExpanded(node, true); e.preventDefault(); return; }
      if (open) target = visibleTreeRows()[idx + 1];
      break;
    case 'ArrowLeft':
      if (open) { setTreeExpanded(node, false); e.preventDefault(); return; }
      target = treeRowOf(node.parentElement && node.parentElement.closest('.tree-node'));
      break;
    case 'Enter':
    case ' ':
      e.preventDefault();
      row.click();
      return;
    default:
      return;
  }
  e.preventDefault();
  if (target) {
    setTreeTabStop(target);
    target.focus();
  }
}

function renderTreeNode(name, node, depth) {
  // Merged single-function file: delegate entirely to renderTestLeaf.
  if (node._mergedTest) {
    return renderTestLeaf(node._mergedTest, depth);
  }

  const hasChildren = Object.keys(node.children).length > 0 || node.tests.length > 0;
  const agg = nodeAgg(node);
  const isClass = !!node._isClass;
  const container = el('div', {className:'tree-node', role:'none'});

  const row = el('div', {
    className: 'tree-row' + (isClass ? ' tree-class-row' : ''),
    style: `padding-left:${16 + depth * 16}px`,
    role: 'treeitem', 'aria-level': String(depth + 1), tabindex: '-1',
  });
  if (hasChildren) row.setAttribute('aria-expanded', 'false');

  // Chevron icon for expandable nodes
  const icon = el('span', {className:'tree-icon'});
  if (hasChildren) {
    icon.innerHTML = '<svg aria-hidden="true" focusable="false" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>';
  } else {
    icon.innerHTML = '<svg aria-hidden="true" focusable="false" width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="4"/></svg>';
  }

  // Build label: breadcrumb for collapsed chains (_segments), plain name otherwise.
  // Each segment emits a data-seg attribute for navigateToGroup D4 matching.
  const nameEl = el('span', {className:'tree-name' + (isClass ? ' tree-class' : '')});
  const segs = node._segments || [name];
  segs.forEach((seg, i) => {
    nameEl.appendChild(el('span', {'data-seg': seg}, seg));
    if (i < segs.length - 1) {
      nameEl.appendChild(el('span', {className:'crumb-sep'}, ' / '));
    }
  });

  // Colored count badges (read out once, as text, by srText below)
  const badges = el('span', {className:'tree-badges', 'aria-hidden':'true'});
  if (agg.retried) {
    badges.appendChild(el('span', {
      className: 'tree-badge retried',
      title: 'Retried tests in this group: ' + agg.retried,
    }, '↻' + agg.retried));
  }
  if (agg.passed) badges.appendChild(el('span', {className:'tree-badge passed'}, String(agg.passed)));
  if (agg.failed) badges.appendChild(el('span', {className:'tree-badge failed'}, String(agg.failed)));
  if (agg.skipped) badges.appendChild(el('span', {className:'tree-badge skipped'}, String(agg.skipped)));
  if (agg.error) badges.appendChild(el('span', {className:'tree-badge error'}, String(agg.error)));
  if (!agg.passed && !agg.failed && !agg.skipped && !agg.error) {
    badges.appendChild(el('span', {className:'tree-badge count'}, '0'));
  }

  row.appendChild(icon);
  row.appendChild(nameEl);
  const counts = STATUSES.filter(st => agg[st]).map(st => agg[st] + ' ' + LABELS[st].toLowerCase());
  if (agg.retried) counts.push(agg.retried + ' retried');
  if (counts.length) row.appendChild(srText(', ' + counts.join(', ')));
  row.appendChild(badges);
  row.title = segs.join(' / ');
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    setTreeExpanded(container, !container.classList.contains('expanded'));
    setTreeTabStop(row);
  });
  container.appendChild(row);

  if (hasChildren) {
    const children = el('div', {className:'tree-children', role:'none'});
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

// Return the bare display name for a test aggregate (strips class prefix).
function testDisplayName(agg) {
  return agg.display_name || agg.function_name;
}

function renderTestLeaf(test, depth) {
  const container = el('div', {className:'tree-node', role:'none'});
  const agg = test.aggregate;
  const outcome = getOverallOutcome(test);
  const displayName = testDisplayName(agg);

  const row = el('div', {className:'tree-row', style:`padding-left:${16 + depth * 16}px`,
    role:'treeitem', 'aria-level': String(depth + 1), 'aria-selected':'false', tabindex:'-1',
    title: displayName});
  const dot = el('span', {className:`status-dot ${outcome}`, 'aria-hidden':'true'});

  // Class context comes from the parent class node (file -> class -> method),
  // so the leaf shows just the bare method/function name — aligned with peers.
  const nameEl = el('span', {className:'tree-name'}, displayName);

  const badges = el('span', {className:'tree-badges', 'aria-hidden':'true'});
  // Flaky marker: any run that needed retries gets a ↻ pill so passed-on-retry
  // tests are visible at a glance in the tree (final outcome alone hides them).
  const anyRetried = test.runs.some(r => r.retries && r.retries.attempts > 0);
  if (anyRetried) {
    const n = test.runs.reduce((a, r) => a + ((r.retries && r.retries.attempts) || 0), 0);
    badges.appendChild(el('span', {
      className: 'tree-badge retried',
      title: 'Retried (' + n + ' attempt' + (n === 1 ? '' : 's') + ')',
    }, '↻' + n));
  }
  if (agg.total_runs > 1) {
    badges.appendChild(el('span', {className:'tree-badge count'}, String(agg.total_runs)));
  }
  row.appendChild(dot);
  row.appendChild(nameEl);
  let leafInfo = ', ' + LABELS[outcome];
  if (anyRetried) leafInfo += ', retried';
  if (agg.total_runs > 1) leafInfo += ', ' + agg.total_runs + ' runs';
  row.appendChild(srText(leafInfo));
  row.appendChild(badges);
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    markTreeSelected(row);
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

// ─── Failure-first helpers ───────────────────────────────────────────
// A failed report should open on what broke: the failing run, the phase
// that failed, and the line that says why.
function isBad(outcome) { return outcome === 'failed' || outcome === 'error'; }

function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

// The run a test opens on: its first failed/errored run, else its first run.
function firstFailingRun(test) {
  return test.runs.find(r => isBad(r.outcome)) || test.runs[0] || null;
}

// The phase that failed (setup, call or teardown), or null.
function failedPhase(run) {
  const phases = run.phases || {};
  return ['setup','call','teardown'].find(w => phases[w] && isBad(phases[w].outcome)) || null;
}

// The phase a run's Summary opens on: the failed one, else a skipped one.
function phaseOfInterest(run) {
  const phases = run.phases || {};
  return failedPhase(run)
    || ['setup','call','teardown'].find(w => phases[w] && phases[w].outcome === 'skipped')
    || null;
}

function failedChecks(run) {
  return (run.check_results || []).filter(c => c.passed === false);
}

// One line saying why a run failed: the checks summary, the first "E" line
// of the traceback, the first failed check, else the traceback's last line.
function failureReason(run) {
  const when = failedPhase(run);
  const longrepr = when ? (run.phases[when].longrepr || '') : '';
  const lines = longrepr.split('\n');
  const first = (lines.find(l => l.trim()) || '').trim();
  if (/^\d+ of \d+ checks? failed/.test(first)) return first;
  const eLine = lines.find(l => /^E\s/.test(l));
  if (eLine) return eLine.replace(/^E\s+/, '').trim();
  const check = failedChecks(run)[0];
  if (check) return (check.name || check.description || 'Check') + (check.detail ? ' — ' + check.detail : '');
  const rest = lines.map(l => l.trim()).filter(Boolean);
  return rest.length ? rest[rest.length - 1] : '';
}

function runLabel(test, run) {
  const name = testDisplayName(test.aggregate);
  return run && run.parametrize_id ? name + ' [' + run.parametrize_id + ']' : name;
}

// Banner at the top of a failed run: where it failed, why, and the way to
// the traceback and the checks.
function renderFailureStrip(run, selectSubTab) {
  const when = failedPhase(run);
  const checks = failedChecks(run);
  const strip = el('div', {className:'failure-strip ' + run.outcome, role:'group',
    'aria-label':'Why this run failed'});

  const label = (run.outcome === 'error' ? 'Error' : 'Failed') + (when ? ' in ' + when : '');
  strip.appendChild(el('div', {className:'failure-strip-label'}, label));

  if (checks.length > 0) {
    const total = (run.check_results || []).length;
    strip.appendChild(el('div', {className:'failure-strip-reason'},
      checks.length + ' of ' + total + ' check' + (total === 1 ? '' : 's') + ' failed'));
    const list = el('ul', {className:'failure-strip-checks'});
    checks.slice(0, 3).forEach(c => {
      const item = el('li', null,
        el('span', {className:'failure-strip-check-name'}, c.description || c.name || 'Check'));
      if (c.detail) item.appendChild(el('span', {className:'failure-strip-check-detail'}, c.detail));
      if (c.location) item.appendChild(el('span', {className:'failure-strip-check-loc'}, c.location));
      list.appendChild(item);
    });
    if (checks.length > 3) {
      list.appendChild(el('li', {className:'failure-strip-more'}, '+' + (checks.length - 3) + ' more'));
    }
    strip.appendChild(list);
  } else {
    const reason = failureReason(run);
    if (reason) strip.appendChild(el('div', {className:'failure-strip-reason', title:reason}, reason));
  }

  const actions = el('div', {className:'failure-strip-actions'});
  if (when) {
    const tbBtn = el('button', {className:'strip-btn', type:'button'}, 'Show traceback');
    tbBtn.addEventListener('click', () => {
      selectSubTab('Summary');
      const phaseBtn = document.querySelector('#sub-tab-content .phase-tab-btn.active');
      const panel = document.querySelector('#sub-tab-content .phase-tab-panel.active');
      if (panel) panel.scrollIntoView({block:'start', behavior:'smooth'});
      if (phaseBtn) phaseBtn.focus({preventScroll:true});
    });
    actions.appendChild(tbBtn);
  }
  if (checks.length > 0) {
    const ckBtn = el('button', {className:'strip-btn', type:'button'}, 'Open checks');
    ckBtn.addEventListener('click', () => selectSubTab('Checks'));
    actions.appendChild(ckBtn);
  }
  if (actions.children.length) strip.appendChild(actions);
  return strip;
}

function showTestDetail(test, initialRun) {
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
  // Class eyebrow above the function name (class-based tests only)
  if (test.aggregate.class_name) {
    headerTop.appendChild(el('div', {className:'detail-eyebrow'}, test.aggregate.class_name));
  }
  headerTop.appendChild(el('h2', null, testDisplayName(test.aggregate)));
  headerTop.appendChild(outcomeBadge);
  header.appendChild(headerTop);
  header.appendChild(el('div', {className:'file-path'}, test.aggregate.file));

  // Exact "run only this test" command — updates with the selected run's nodeid.
  const firstRun = initialRun || firstFailingRun(test);
  const initialCmd = testCommand(firstRun ? firstRun.nodeid : test.base_nodeid);
  const cmdRow = el('div', {
    className:'detail-cmd', id:'detail-cmd', role:'button', tabindex:'0',
    'aria-label':'Copy command to run this test'
  },
    el('code', {className:'detail-cmd-code'}, initialCmd),
    el('span', {className:'detail-cmd-hint'}, 'Copy')
  );
  cmdRow.addEventListener('click', function() { copyCommandRow(cmdRow); });
  cmdRow.addEventListener('keydown', function(ev) {
    if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); copyCommandRow(cmdRow); }
  });
  header.appendChild(cmdRow);

  // Stats row
  const agg = test.aggregate;
  const stats = el('div', {className:'detail-header-stats'});
  stats.appendChild(el('span', {className:'detail-header-stat'}, el('strong', null, String(agg.total_runs)), ' runs'));
  stats.appendChild(el('span', {className:'detail-header-stat'}, el('strong', null, formatDuration(agg.total_duration_seconds)), ' total'));
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
  const filterRow = el('div', {className:'filter-toggles', role:'group', 'aria-label':'Show runs by outcome'});
  STATUSES.forEach(s => {
    const count = test.runs.filter(r => r.outcome === s).length;
    if (count === 0) return;
    const btn = el('button', {className:`filter-btn ${s} active`, type:'button', 'aria-pressed':'true'},
      `${LABELS[s]} (${count})`);
    btn.addEventListener('click', () => {
      const on = !btn.classList.contains('active');
      btn.classList.toggle('active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      refreshRunPills(test, panel);
    });
    filterRow.appendChild(btn);
  });
  runFilters.appendChild(filterRow);
  panel.appendChild(runFilters);

  // Run pills
  const pillsContainer = el('div', {className:'run-pills', id:'run-pills', role:'group', 'aria-label':'Runs'});
  panel.appendChild(pillsContainer);

  // Run detail
  const runDetailContainer = el('div', {id:'run-detail'});
  panel.appendChild(runDetailContainer);

  refreshRunPills(test, panel);
  if (firstRun) showRunDetail(firstRun);
}

// A run pill: its outcome is spoken (not only coloured), its selection is
// aria-pressed, and the run it stands for is kept for showRunDetail.
function makeRunPill(run, text) {
  const on = selectedRun === run;
  const pill = el('button', {className:`run-pill ${run.outcome}${on ? ' selected' : ''}`, type:'button',
    'aria-pressed': on ? 'true' : 'false'}, text);
  pill._run = run;
  pill.appendChild(srText(', ' + (LABELS[run.outcome] || run.outcome)));
  if (run.retries && run.retries.attempts > 0) {
    const n = run.retries.attempts;
    pill.appendChild(el('span', {className:'retry-badge', 'aria-hidden':'true'}, '\u21bb' + n));
    pill.appendChild(srText(', retried ' + n + (n === 1 ? ' time' : ' times')));
  }
  return pill;
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
    const pill = makeRunPill(run, pillText);
    pill.addEventListener('click', () => showRunDetail(run));
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
          const pill = makeRunPill(run, run.run_id);
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
  // Keep the header command in sync with the selected run's exact nodeid.
  const cmdCode = document.querySelector('#detail-cmd .detail-cmd-code');
  if (cmdCode) cmdCode.textContent = testCommand(run.nodeid);
  // Update pill selection
  document.querySelectorAll('#run-pills .run-pill').forEach(p => {
    const on = p._run === run;
    p.classList.toggle('selected', on);
    p.setAttribute('aria-pressed', on ? 'true' : 'false');
  });

  const container = document.getElementById('run-detail');
  if (!container) return;
  container.innerHTML = '';

  const subTabs = el('div', {className:'sub-tabs', role:'tablist', 'aria-label':'Run details'});
  const subPanelId = 'sub-tab-content';
  const tabNames = ['Summary','Procedure','Artifacts'];
  if (run.check_results && run.check_results.length > 0) {
    tabNames.splice(2, 0, 'Checks');
  }
  if (run.retries && run.retry_attempts && run.retry_attempts.length > 0) {
    tabNames.push('Retries');
  }
  const selectSubTab = (name) => {
    const tabs = Array.from(subTabs.querySelectorAll('.sub-tab-btn'));
    const tab = tabs.find(b => b.textContent === name) || tabs[0];
    setSelectedTab(tabs, tab);
    const content = document.getElementById('sub-tab-content');
    if (content) content.setAttribute('aria-labelledby', tab.id);
    showSubTab(name.toLowerCase(), run);
  };
  tabNames.forEach((name, i) => {
    const btn = el('button', {className:`sub-tab-btn${i===0?' active':''}`, type:'button', role:'tab',
      id: uid('subtab'), 'aria-selected': i === 0 ? 'true' : 'false', 'aria-controls': subPanelId,
      tabindex: i === 0 ? '0' : '-1'}, name);
    btn.addEventListener('click', () => selectSubTab(name));
    subTabs.appendChild(btn);
  });
  wireTablist(subTabs, '.sub-tab-btn', btn => selectSubTab(btn.textContent));
  if (isBad(run.outcome)) container.appendChild(renderFailureStrip(run, selectSubTab));
  container.appendChild(subTabs);

  const content = el('div', {className:'run-detail-content', id:'sub-tab-content', role:'tabpanel',
    'aria-labelledby': subTabs.querySelector('.sub-tab-btn').id});
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
    if (run.strategy) {
      // pytest-strategies row: "levels \u00b7 directed zero", and its seed
      const st = run.strategy;
      const row = [st.kind, st.name].filter(Boolean).join(' ');
      addRow('Strategy', [st.strategy, row].filter(Boolean).join(' \u00b7 '));
      if (st.seed != null) addRow('Row seed', String(st.seed));
    }
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
      const phaseBar = el('div', {className:'phase-tabs-bar', role:'tablist', 'aria-label':'Phase logs'});
      const phasePanels = [];
      // Open on the phase that failed (or was skipped), not always on Setup.
      const activeIdx = Math.max(0, availablePhases.indexOf(phaseOfInterest(run)));

      availablePhases.forEach((when, idx) => {
        const phase = run.phases[when];
        const tabId = uid('phasetab'), panelId = uid('phasepanel');
        const btn = el('button', {className:`phase-tab-btn${idx===activeIdx?' active':''}`, type:'button',
          role:'tab', id:tabId, 'aria-controls':panelId, 'aria-selected': idx===activeIdx ? 'true' : 'false',
          tabindex: idx===activeIdx ? '0' : '-1'},
          el('span', {className:`status-dot ${phase.outcome}`, 'aria-hidden':'true'}),
          when.charAt(0).toUpperCase() + when.slice(1),
          srText(', ' + (LABELS[phase.outcome] || phase.outcome)),
          el('span', {className:'phase-meta'}, phase.duration.toFixed(4) + 's')
        );

        const panel = el('div', {className:`phase-tab-panel${idx===activeIdx?' active':''}`, role:'tabpanel',
          id:panelId, 'aria-labelledby':tabId, tabindex:'0'});
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
          setSelectedTab(Array.from(phaseBar.querySelectorAll('.phase-tab-btn')), btn);
          phasePanels.forEach(p => p.classList.toggle('active', p === panel));
        });

        phaseBar.appendChild(btn);
        phasePanels.push(panel);
      });

      wireTablist(phaseBar, '.phase-tab-btn', b => b.click());
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
            // A data: frame is cross-origin, so its height can't be read
            // after load: size it from the table rows in the HTML instead.
            const rows = artifactRowCount(a.data_uri);
            const fullHeight = rows === null ? 480 : ARTIFACT_CHROME_PX + rows * ARTIFACT_ROW_PX;
            const capped = Math.min(fullHeight, ARTIFACT_MAX_PX);
            const iframe = el('iframe', {className:'artifact-html-frame', src:a.data_uri, sandbox:'allow-same-origin',
              title:a.name, style:'pointer-events:auto;height:' + capped + 'px'});
            content.appendChild(iframe);
            if (fullHeight > capped) {
              const more = el('button', {className:'strip-btn artifact-expand', type:'button',
                'aria-expanded':'false'}, rows === null ? 'Show taller' : 'Show all ' + rows + ' rows');
              more.addEventListener('click', () => {
                const open = more.getAttribute('aria-expanded') !== 'true';
                iframe.style.height = (open ? fullHeight : capped) + 'px';
                more.setAttribute('aria-expanded', open ? 'true' : 'false');
                more.textContent = open ? 'Show fewer rows' : (rows === null ? 'Show taller' : 'Show all ' + rows + ' rows');
              });
              content.appendChild(more);
            }
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
          icon.innerHTML = '<svg aria-hidden="true" focusable="false" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
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
        // Verification checks of this attempt
        if (attempt.check_results && attempt.check_results.length > 0) {
          body.appendChild(el('h4', {style:'margin-top:12px;font-size:12px;color:var(--c-text2)'}, 'Checks'));
          body.appendChild(renderCheckResults(attempt.check_results));
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
// depth 1 = L1 step, depth 2 = L2 substep, depth 3 = L3 sub-substep (deeper
// nodes render at depth 3). Nodes come from stepdoc: kind 'step', 'action'
// (a line of the executed report) or 'check' (a Verify line). Files without a
// kind (pytest-reporter 0.2) are steps. Text is set via textContent only.
function renderNode(node, depth) {
  const kind = node.kind || 'step';
  const cls = (depth === 1 ? 'procedure-step'
            : depth === 2 ? 'procedure-substep'
            : 'procedure-substep procedure-subsubstep') + ' proc-kind-' + kind;
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
  if (node.result) {
    header.appendChild(el('span', {className: 'procedure-result'}, '\u2192 ' + node.result));
  }
  _appendCheckInline(header, node.check);
  if (node.duration_seconds > 0) {
    header.appendChild(el('span', {className: 'procedure-step-duration'},
      node.duration_seconds.toFixed(2) + 's'));
  }
  row.appendChild(header);
  if (node.detail && node.outcome === 'failed') {
    row.appendChild(el('div', {className: 'procedure-step-exc'}, node.detail));
  }
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

// Setup (S1…) and Teardown (T1…) steps from fixtures get a heading of their
// own; the test's steps get one only when one of the others is present.
const PROC_SECTIONS = [['setup','Setup'], ['procedure','Procedure'], ['teardown','Teardown']];

function renderProcedure(proc) {
  const list = el('div', {className:'procedure-list'});
  const steps = proc.steps || [];
  const sectionOf = s => s.section || 'procedure';
  const framed = steps.some(s => sectionOf(s) !== 'procedure');
  PROC_SECTIONS.forEach(function(pair) {
    const inSection = steps.filter(s => sectionOf(s) === pair[0]);
    if (inSection.length === 0) return;
    if (framed) list.appendChild(el('div', {className:'procedure-section'}, pair[1]));
    inSection.forEach(function(s) { list.appendChild(renderNode(s, 1)); });
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
    const isExpanded = status === 'failed';
    const card = el('div', {className:`check-card ${status}${isExpanded ? ' expanded' : ''}`});

    const header = el('div', {className:'check-card-header'});
    header.setAttribute('role', 'button');
    header.setAttribute('tabindex', '0');
    header.setAttribute('aria-expanded', String(isExpanded));
    header.appendChild(chevronSvg('check-card-chevron'));
    header.appendChild(el('span', {className:`status-dot ${status}`}));
    header.appendChild(el('span', {className:'check-name'}, checkLabel(check, idx)));
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
    // Composite checks (guard/conditional/all_satisfy) carry branches/cases/
    // child_checks — not the flat leaf fields — so render their chain instead.
    body.appendChild(renderCheckBody(check));
    card.appendChild(body);
    cards.appendChild(card);
  });
  container.appendChild(cards);
  return container;
}

// "3V3 \u203a Vout": a check's verify.section titles, then its name.
function checkLabel(check, idx) {
  const name = check.name || ('Check #' + (idx + 1));
  const section = Array.isArray(check.section) ? check.section : [];
  return section.length ? section.concat([name]).join(' \u203a ') : name;
}

// Leaf check detail — the flat field grid for a single (non-guard) descriptor.
// pytest-verifier records carry a rendered `detail` ("expected 2, got 1"), an
// `error` when the comparison raised, and where the check was made.
function renderCheckDetail(check) {
  const detail = el('div', {className:'check-card-detail'});
  const fields = [
    ['detail', 'Result'], ['error', 'Error'], ['also_failed', 'Also failed'],
    ['actual', 'Actual'], ['expected', 'Expected'],
    ['threshold', 'Threshold'], ['low', 'Low'], ['high', 'High'],
    ['abs_tol', 'Abs tolerance'], ['rel_tol', 'Rel tolerance'],
    ['units', 'Units'], ['inclusive', 'Inclusive'],
    ['expected_type', 'Expected type'], ['actual_length', 'Actual length'],
    ['haystack', 'Haystack'], ['needle', 'Needle'], ['pattern', 'Pattern'],
    ['msg', 'Message'],
    ['raised_type', 'Raised'], ['raised_message', 'Raised message'], ['match', 'Match'],
    ['raised_at', 'Raised at'],
    ['timeout', 'Timeout (s)'], ['duration', 'Duration (s)'], ['interval', 'Interval (s)'],
    ['tries', 'Tries'], ['elapsed', 'Elapsed (s)'],
    ['phase', 'Phase'], ['location', 'Made at'], ['called_from', 'Called from'],
  ];
  fields.forEach(([key, label]) => {
    if (check[key] !== undefined && check[key] !== null) {
      detail.appendChild(el('span', {className:'label'}, label));
      const v = typeof check[key] === 'object' ? JSON.stringify(check[key]) : String(check[key]);
      detail.appendChild(el('span', {className:'value'}, v));
    }
  });
  return detail;
}

// Dispatch a check descriptor to its body renderer (composite chain or leaf grid).
function renderCheckBody(check) {
  switch (check.check_type) {
    case 'guard': return renderGuardBody(check);
    case 'conditional': return renderConditionalBody(check);
    case 'all_satisfy': return renderAllSatisfyBody(check);
    case 'eventually':
    case 'stable': return renderSamplingBody(check);
    default: return renderCheckDetail(check);
  }
}

// Render a nested check descriptor inside a composite branch/case. The chosen
// one is expanded with its full body; recurses for nested composites.
function renderGuardCheck(check, expand) {
  const box = el('div', {className:'guard-check'});
  if (!check) { box.appendChild(el('span', {className:'guard-check-desc'}, '—')); return box; }
  const meta = el('div', {className:'guard-check-meta'});
  meta.appendChild(el('span', {className:'check-type-badge'}, check.check_type || ''));
  if (check.name) meta.appendChild(el('span', {className:'guard-check-name'}, check.name));
  if (check.description) meta.appendChild(el('span', {className:'guard-check-desc'}, check.description));
  box.appendChild(meta);
  if (expand) box.appendChild(renderCheckBody(check));
  return box;
}

// Render a guard descriptor body: the ordered if/elif/else branch chain, the
// evaluated branch marked via matched_index (or the default when null).
function renderGuardBody(check) {
  const wrap = el('div', {className:'guard-body'});
  const branches = check.branches || [];
  const matched = check.matched_index;  // int | null
  branches.forEach((b, i) => {
    const chosen = matched === i;
    const row = el('div', {className:'guard-branch' + (chosen ? ' chosen' : '')});
    const head = el('div', {className:'guard-branch-head'});
    head.appendChild(el('span', {className:'guard-kw'}, i === 0 ? 'if' : 'elif'));
    head.appendChild(el('span', {className:'guard-label'}, b.label || ''));
    head.appendChild(el('span', {className:'guard-cond ' + (b.condition ? 'true' : 'false')},
      b.condition ? 'true' : 'false'));
    if (chosen) head.appendChild(el('span', {className:'guard-chosen-tag'}, 'evaluated'));
    row.appendChild(head);
    row.appendChild(renderGuardCheck(b.check, chosen));
    wrap.appendChild(row);
  });
  if (check.default) {
    const chosen = matched == null;
    const row = el('div', {className:'guard-branch guard-default' + (chosen ? ' chosen' : '')});
    const head = el('div', {className:'guard-branch-head'});
    head.appendChild(el('span', {className:'guard-kw'}, 'else'));
    head.appendChild(el('span', {className:'guard-label'}, check.default.name || 'default'));
    if (chosen) head.appendChild(el('span', {className:'guard-chosen-tag'}, 'evaluated'));
    row.appendChild(head);
    row.appendChild(renderGuardCheck(check.default, chosen));
    wrap.appendChild(row);
  } else if (matched == null) {
    wrap.appendChild(el('div', {className:'guard-nomatch'},
      'No branch matched and no default — check fails.'));
  }
  return wrap;
}

// Render a conditional descriptor: a switch over named cases, the matched case
// (matched_case, or the default when null) marked as evaluated.
function renderConditionalBody(check) {
  const wrap = el('div', {className:'guard-body'});
  wrap.appendChild(el('div', {className:'guard-switch'},
    el('span', {className:'guard-kw'}, 'switch'),
    el('span', {className:'guard-switch-val'}, String(check.switch_value))));
  const cases = check.cases || {};
  const matched = check.matched_case;  // str | null
  Object.keys(cases).forEach(key => {
    const chosen = matched === key;
    const row = el('div', {className:'guard-branch' + (chosen ? ' chosen' : '')});
    const head = el('div', {className:'guard-branch-head'});
    head.appendChild(el('span', {className:'guard-kw'}, 'case'));
    head.appendChild(el('span', {className:'guard-label'}, key));
    if (chosen) head.appendChild(el('span', {className:'guard-chosen-tag'}, 'evaluated'));
    row.appendChild(head);
    row.appendChild(renderGuardCheck(cases[key], chosen));
    wrap.appendChild(row);
  });
  if (check.default) {
    const chosen = matched == null;
    const row = el('div', {className:'guard-branch guard-default' + (chosen ? ' chosen' : '')});
    const head = el('div', {className:'guard-branch-head'});
    head.appendChild(el('span', {className:'guard-kw'}, 'default'));
    head.appendChild(el('span', {className:'guard-label'}, check.default.name || 'default'));
    if (chosen) head.appendChild(el('span', {className:'guard-chosen-tag'}, 'evaluated'));
    row.appendChild(head);
    row.appendChild(renderGuardCheck(check.default, chosen));
    wrap.appendChild(row);
  } else if (matched == null) {
    wrap.appendChild(el('div', {className:'guard-nomatch'},
      'No case matched and no default — check fails.'));
  }
  return wrap;
}

// Render an all_satisfy descriptor: every child is evaluated (AND); failures are
// expanded so the offending item is visible.
function renderAllSatisfyBody(check) {
  const wrap = el('div', {className:'guard-body'});
  const kids = check.child_checks || [];
  wrap.appendChild(el('div', {className:'guard-switch'},
    el('span', {className:'guard-kw'}, 'all of'),
    el('span', {className:'guard-switch-val'}, kids.length + ' items')));
  kids.forEach((c, i) => {
    const ok = !!(c && c.passed);
    // every child is evaluated → full opacity (.chosen); expand failures.
    const row = el('div', {className:'guard-branch chosen'});
    const head = el('div', {className:'guard-branch-head'});
    head.appendChild(el('span', {className:`status-dot ${ok ? 'passed' : 'failed'}`}));
    head.appendChild(el('span', {className:'guard-label'}, '#' + (i + 1)));
    row.appendChild(head);
    row.appendChild(renderGuardCheck(c, !ok));
    wrap.appendChild(row);
  });
  return wrap;
}

// Render an eventually/stable descriptor: its own fields, then the kept try's
// check (child_checks holds the one try pytest-verifier kept).
function renderSamplingBody(check) {
  const wrap = el('div', {className:'guard-body'});
  wrap.appendChild(renderCheckDetail(check));
  (check.child_checks || []).forEach(c => {
    const ok = !!(c && c.passed);
    const row = el('div', {className:'guard-branch chosen'});
    const head = el('div', {className:'guard-branch-head'});
    head.appendChild(el('span', {className:`status-dot ${ok ? 'passed' : 'failed'}`}));
    head.appendChild(el('span', {className:'guard-label'}, 'kept try'));
    row.appendChild(head);
    row.appendChild(renderGuardCheck(c, true));
    wrap.appendChild(row);
  });
  return wrap;
}

// HTML artifact frames: page chrome (title, meta, header row, padding) plus
// one row height per <tr> in the body, from the table artifact's own CSS.
const ARTIFACT_CHROME_PX = 180;
const ARTIFACT_ROW_PX = 29;
const ARTIFACT_MAX_PX = 560;

// Number of body rows in a base64 HTML artifact, or null when it isn't a
// table (or can't be decoded).
function artifactRowCount(dataUri) {
  try {
    const comma = dataUri.indexOf(',');
    if (comma < 0 || dataUri.slice(0, comma).indexOf('base64') < 0) return null;
    const html = atob(dataUri.slice(comma + 1));
    const trs = (html.match(/<tr[\s>]/gi) || []).length;
    return trs > 0 ? Math.max(0, trs - 1) : null;
  } catch (e) {
    return null;
  }
}

function formatSize(bytes) {
  if (bytes == null) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function formatDuration(sec) {
  if (sec == null || isNaN(sec)) return '—';
  if (sec < 1) return '<1s';
  let s = Math.floor(sec);
  const d = Math.floor(s / 86400); s -= d * 86400;
  const h = Math.floor(s / 3600);  s -= h * 3600;
  const m = Math.floor(s / 60);    s -= m * 60;
  const parts = [];
  if (d) parts.push(d + 'd');
  if (h) parts.push(h + 'h');
  if (m) parts.push(m + 'm');
  if (s || !parts.length) parts.push(s + 's');
  return parts.join(' ');
}

// Format the run timestamp (YYYY_MM_DD_HH_MM_SS, UTC) into a legible string:
// "Monday, June 23rd of 2026 at 23:01:42". Falls back to the raw value if it
// doesn't match the expected shape.
function ordinalSuffix(n) {
  const v = n % 100;
  if (v >= 11 && v <= 13) return 'th';
  return ({1:'st', 2:'nd', 3:'rd'})[n % 10] || 'th';
}
function formatTimestamp(ts) {
  if (!ts) return '—';
  const m = /^(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})$/.exec(ts);
  if (!m) return ts;
  const [, y, mo, d, hh, mm, ss] = m;
  const MONTHS = ['January','February','March','April','May','June',
                  'July','August','September','October','November','December'];
  const DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const dt = new Date(Date.UTC(+y, +mo - 1, +d, +hh, +mm, +ss));
  const day = +d;
  return `${DAYS[dt.getUTCDay()]}, ${MONTHS[+mo - 1]} ${day}${ordinalSuffix(day)} `
       + `of ${y} at ${hh}:${mm}:${ss}`;
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

// Tree visibility combines the search text, the status filters and the
// "retried only" view; folders with nothing visible inside are hidden too.
let searchQuery = '';
let retriedOnly = false;

function testMatchesQuery(test, q) {
  return !q || test.aggregate.function_name.toLowerCase().includes(q)
    || test.aggregate.file.toLowerCase().includes(q)
    || test.base_nodeid?.toLowerCase().includes(q)
    || test.aggregate.class_name?.toLowerCase().includes(q);
}

function testIsRetried(test) {
  return test.runs.some(r => r.retries && r.retries.attempts > 0);
}

function expandAncestors(node) {
  let parent = node.parentElement;
  while (parent) {
    if (parent.classList?.contains('tree-node')) setTreeExpanded(parent, true);
    parent = parent.parentElement;
  }
}

function refreshTree(expandMatches) {
  const q = searchQuery.toLowerCase();
  const narrowed = !!q || retriedOnly || activeFilters.size < STATUSES.length;
  const nodes = Array.from(document.querySelectorAll('.tree-content .tree-node'));
  nodes.forEach(node => {
    const test = node._test;
    if (!test) return;
    const outcome = getOverallOutcome(test);
    const show = (activeFilters.size === 0 || activeFilters.has(outcome))
      && (!retriedOnly || testIsRetried(test))
      && testMatchesQuery(test, q);
    node.style.display = show ? '' : 'none';
    if (show && narrowed && expandMatches) expandAncestors(node);
  });
  // Folders last to first, so a folder sees its sub-folders' final state.
  nodes.reverse().forEach(node => {
    if (node._test) return;
    const kids = node.querySelectorAll(':scope > .tree-children > .tree-node');
    const any = Array.from(kids).some(k => k.style.display !== 'none');
    node.style.display = any ? '' : 'none';
  });
  syncFilterButtons();
  ensureTreeTabStop();
  const empty = document.getElementById('tree-empty');
  if (empty) empty.hidden = nodes.some(n => n._test && n.style.display !== 'none');
}

function syncFilterButtons() {
  document.querySelectorAll('.tree-controls .filter-btn[data-status]').forEach(btn => {
    const on = activeFilters.has(btn.dataset.status);
    btn.classList.toggle('active', on);
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  const chip = document.getElementById('retried-chip');
  if (chip) chip.hidden = !retriedOnly;
}

function filterTree(query) {
  searchQuery = query;
  refreshTree(true);
  const n = Array.from(document.querySelectorAll('.tree-content .tree-node'))
    .filter(x => x._test && x.style.display !== 'none').length;
  announce(n === 0 ? 'No tests match' : n + (n === 1 ? ' test' : ' tests') + ' shown');
}

function toggleFilter(status, btn) {
  if (activeFilters.has(status)) activeFilters.delete(status);
  else activeFilters.add(status);
  refreshTree(false);
}

// Show only the given statuses (or retried tests) in the Tests tab.
function showTreeSubset(statuses, onlyRetried) {
  activeFilters = new Set(statuses);
  retriedOnly = !!onlyRetried;
  switchTab('tests');
  refreshTree(true);
}

function selectTreeRow(test) {
  const node = Array.from(document.querySelectorAll('.tree-content .tree-node'))
    .find(n => n._test === test);
  if (!node) return null;
  if (node.style.display === 'none') {
    // Make the requested test visible again rather than opening it unseen.
    activeFilters.add(getOverallOutcome(test));
    retriedOnly = false;
    searchQuery = '';
    const input = document.querySelector('.tree-controls .search-input');
    if (input) input.value = '';
    refreshTree(false);
  }
  expandAncestors(node);
  const row = node.querySelector(':scope > .tree-row');
  if (row) {
    markTreeSelected(row);
    row.scrollIntoView({block:'nearest'});
  }
  return node;
}

// Open one run of a test in the Tests tab (from the Summary failures list).
function openRunInTests(test, run) {
  switchTab('tests');
  selectTreeRow(test);
  showTestDetail(test, run);
  const panel = document.querySelector('.detail-panel');
  if (panel && window.matchMedia('(max-width: 768px)').matches) {
    panel.scrollIntoView({block:'start'});
  }
}

// ─── Session Logs Tab ────────────────────────────────────────────────
// A section header that opens and closes its section: a button for the
// keyboard and screen readers, with its state in aria-expanded.
function setDisclosure(section, open) {
  section.classList.toggle('expanded', open);
  const header = section.querySelector(':scope > .session-log-section-header');
  if (header) header.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function wireDisclosure(header, section) {
  header.setAttribute('role', 'button');
  header.setAttribute('tabindex', '0');
  header.setAttribute('aria-expanded', section.classList.contains('expanded') ? 'true' : 'false');
  const toggle = (ev) => {
    ev.stopPropagation();
    setDisclosure(section, !section.classList.contains('expanded'));
  };
  header.addEventListener('click', toggle);
  header.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggle(ev); }
  });
}

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
  searchSvg.setAttribute('stroke-linecap','round'); searchSvg.setAttribute('aria-hidden','true');
  searchSvg.innerHTML = '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>';
  const search = el('input', {className:'session-log-search', type:'search', placeholder:'Search session logs...',
    'aria-label':'Search session logs'});
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
    const btn = el('button', {className:'session-log-level-btn ' + lvl + ' active', type:'button',
      'aria-pressed':'true'}, lvl + ' (' + count + ')');
    btn.addEventListener('click', () => {
      btn.classList.toggle('active');
      btn.setAttribute('aria-pressed', btn.classList.contains('active') ? 'true' : 'false');
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
    treeEl.querySelectorAll('.session-log-section').forEach(s => setDisclosure(s, true));
  });
  collapseAllBtn.addEventListener('click', () => {
    treeEl.querySelectorAll('.session-log-section').forEach(s => setDisclosure(s, false));
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
    wireDisclosure(header, section);
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
      wireDisclosure(childHeader, childSection);
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
  metaHeader.innerHTML = '<svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
  metaHeader.appendChild(document.createTextNode(' Run Information'));
  metaSection.appendChild(metaHeader);
  const metaBody = el('div', {className:'report-section-body'});
  const metaRows = [
    ['Timestamp', formatTimestamp(DATA.timestamp)],
    ['Duration', formatDuration(DATA.duration)],
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
  // Seed row (rendered separately to support conditional mono / not-provided styling)
  metaBody.appendChild(el('div', {className:'report-info-row'},
    el('span', {className:'report-info-label'}, 'Seed'),
    DATA.seed != null
      ? el('span', {className:'report-info-value mono'}, DATA.seed)
      : el('span', {className:'report-info-not-provided'}, 'Not Provided')
  ));
  metaSection.appendChild(metaBody);
  container.appendChild(metaSection);

  // CLI args
  if (DATA.cmdline && DATA.cmdline.length > 0) {
    const cmdSection = el('div', {className:'report-section'});
    const cmdHeader = el('div', {className:'report-section-header'});
    cmdHeader.innerHTML = '<svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>';
    cmdHeader.appendChild(document.createTextNode(' Command Line'));
    cmdSection.appendChild(cmdHeader);
    const cmdBody = el('div', {className:'report-section-body'});
    cmdBody.appendChild(el('div', {className:'log-viewer'}, DATA.cmdline.join(' ')));
    cmdSection.appendChild(cmdBody);
    container.appendChild(cmdSection);
  }

  // Plugins — collapsible, distributed-only, versioned
  {
    const plugSection = el('div', {className:'report-section'});
    const plugHeader = el('div', {
      className: 'report-section-header plugins-collapsible',
      role: 'button', tabIndex: 0
    });
    plugHeader.setAttribute('aria-expanded', 'false');
    const plugIcon = el('span');
    plugIcon.innerHTML = '<svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1"/><circle cx="6" cy="18" r="1"/></svg>';
    plugHeader.appendChild(plugIcon);
    plugHeader.appendChild(document.createTextNode(' Active Plugins'));
    plugHeader.appendChild(chevronSvg('plugins-chevron'));
    const plugBody = el('div', {className:'report-section-body plugins-body'});
    plugBody.style.display = 'none';
    const togglePlugins = () => {
      const open = plugBody.style.display !== 'none';
      plugBody.style.display = open ? 'none' : '';
      plugHeader.setAttribute('aria-expanded', open ? 'false' : 'true');
      const ch = plugHeader.querySelector('.plugins-chevron');
      if (ch) ch.style.transform = open ? '' : 'rotate(90deg)';
    };
    plugHeader.addEventListener('click', togglePlugins);
    plugHeader.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); togglePlugins(); } });
    plugSection.appendChild(plugHeader);
    const plugList = el('div', {className:'plugin-list'});
    if (!DATA.plugins || DATA.plugins.length === 0) {
      plugList.appendChild(el('span', {className:'plugins-empty'}, 'No distributed plugins detected'));
    } else {
      DATA.plugins.forEach(p => {
        const tag = el('span', {className:'plugin-tag'}, p.name || String(p));
        if (p.version) tag.appendChild(el('span', {className:'plugin-ver'}, p.version));
        plugList.appendChild(tag);
      });
    }
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
  logHeader.innerHTML = '<svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>';
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
    b.setAttribute('aria-selected', isActive ? 'true' : 'false');
    b.tabIndex = isActive ? 0 : -1;
  });
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
}
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});
// Arrow keys, Home and End move between the top tabs and select them.
wireTablist(document.querySelector('.tabs'), '.tab-btn', btn => switchTab(btn.dataset.tab));

// ─── Header ──────────────────────────────────────────────────────────
(function() {
  const metaEl = document.getElementById('header-meta');
  const formatted = formatTimestamp(DATA.timestamp);

  const agg = aggTests(DATA.tests);
  const badgeClass = agg.failed > 0 || agg.error > 0 ? 'fail' : agg.total === 0 ? 'mix' : 'pass';
  const badgeText = agg.failed > 0 || agg.error > 0
    ? `${agg.failed + agg.error} failed`
    : `${agg.passed} passed`;

  metaEl.innerHTML = `<span>${formatted} UTC</span><span>\u00b7</span><span>${formatDuration(DATA.duration)}</span>`;
  const badge = el('span', {className: `meta-badge ${badgeClass}`}, badgeText);
  metaEl.appendChild(badge);
})();

// ─── Theme toggle ────────────────────────────────────────────────────
// The page follows the OS setting until the viewer picks a theme; the pick
// is remembered in localStorage when the browser allows it.
(function() {
  const root = document.documentElement;
  const btn = document.getElementById('theme-toggle');
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
  const shown = () => root.getAttribute('data-theme') || (media && media.matches ? 'light' : 'dark');
  function sync() {
    const now = shown();
    root.setAttribute('data-theme-shown', now);
    const label = now === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
    btn.setAttribute('aria-label', label);
    btn.title = label;
  }
  btn.addEventListener('click', () => {
    const next = shown() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('pytest-reporter-theme', next); } catch (e) { /* storage blocked */ }
    sync();
    announce(next === 'dark' ? 'Dark theme' : 'Light theme');
  });
  if (media && media.addEventListener) media.addEventListener('change', sync);
  sync();
})();

// ─── Init ────────────────────────────────────────────────────────────
renderSummary();
renderTests();
renderSessionLogs();
renderReport();"""
