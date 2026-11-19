# CLAUDE.md — pytest-reporter

## Project Overview

`pytest-reporter` is a pytest plugin that generates structured, human-readable and machine-readable test reports. Each test run produces a timestamped folder containing per-test logs, artifacts, procedures, and an aggregated self-contained HTML report plus JUnit XML for CI/CD. The plugin includes a built-in retry system. Procedures come from `stepdoc`, verification cards from `pytest-verifier`, and strategy rows and the run export from `pytest-strategies`: all three are optional and never imported.

**Specification:** The authoritative spec lives in Notion under "Pytest Reporter". Always consult the spec for schema details, edge cases, and design decisions.

## Architecture

```
pytest-reporter (this plugin)
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  FIXTURES (no import needed — auto-registered):             │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ log      │  │ session_log  │  │ report_artifacts  │      │
│  │ (test)   │  │ (session)    │  │ (test)            │      │
│  └──────────┘  └──────────────┘  └──────────────────┘      │
│                                                             │
│  OPTIONAL INTEGRATIONS (never imported):                    │
│  stepdoc          → pytest_stepdoc_step_* hooks → procedures│
│  pytest-verifier  → report.verify_checks → check cards      │
│  pytest-strategies→ `strategy` mark (VectorInfo) → row/seed │
│                     pytest_strategies_export_dir hook +     │
│                     strategies.vectors.json → Strategy tab  │
│                                                             │
│  HOOKS:                                                     │
│  ┌──────────────────────────────┐                           │
│  │ pytest_runtest_makereport    │ → phase log capture       │
│  │ pytest_runtest_protocol      │ → retry engine            │
│  │ pytest_sessionfinish         │ → session log + HTML gen  │
│  └──────────────────────────────┘                           │
│                                                             │
│  READS report.verify_checks for verification cards          │
│  NEVER evaluates check descriptors or determines pass/fail  │
└─────────────────────────────────────────────────────────────┘
```

## Core Principles

- **The reporter observes, never judges.** It never raises exceptions to determine test outcomes. It hooks into `pytest_runtest_makereport` to observe what happened and records it. Pass/fail for checks is determined by `pytest-verifier`.
- **Fixtures are the public API.** `log`, `session_log`, `report_artifacts` are pytest fixtures (no import). The package exports only `Logger`/`ReportLogger`. There is no step API: tests use `from stepdoc import step`.
- **Integrations stay optional.** Never import stepdoc, pytest-verifier or pytest-strategies. Read what they publish: stepdoc's `pytest_stepdoc_step_started/finished` hooks (`optionalhook=True`), `report.verify_checks`, the `strategy` mark's `VectorInfo.to_dict()`, and pytest-strategies' run export (its `pytest_strategies_export_dir` hook, `optionalhook=True`, and the files it writes). CI runs the suite with and without them.
- **Single self-contained HTML report.** `report.html` must be one file with inline HTML, CSS, JS. Artifacts are base64-encoded as data URIs. No external CDN dependencies.
- **Flat serialization with source paths.** The logger uses a tree API in memory but serializes to flat arrays with `source` path arrays. Never nest on disk.

## CLI Options

```bash
pytest tests/ --report-dir=reports                   # Activate reporter
pytest tests/ --report-dir=reports --report-retries=3  # Enable retries
```

## Package Structure

```
pytest_reporter/
├── __init__.py              # Exports: Logger, ReportLogger, ReportTabs (removed names raise ImportError)
├── py.typed                 # PEP 561 marker — REQUIRED
├── plugin.py                # Plugin registration (pytest11 entry point)
├── reporter.py              # Reporter class — main hook orchestrator
├── _collector.py            # DataCollector — item registry, phase tracking, aggregation
├── _context.py              # RunContext — timestamped run directory management
├── _logger.py               # Logger class (+ ReportLogger alias) — tree-based structured logger
├── _stepdoc.py              # activate() stepdoc recording; StepCollector: steps → procedure.json
├── _strategies.py           # StrategyExport: where pytest-strategies writes its run export,
│                            #   reading strategies.vectors.json; html_data() for the report
├── _types.py                # Shared TypedDicts and type aliases
├── _json_writer.py          # Phase log, test.log.json, session.log.json writers
├── _junit_writer.py         # junit.xml generation
├── _html_builder.py         # Self-contained HTML report generation at session end
├── _tabs.py                 # ReportTabs (custom HTML tabs: saves tabs/NN_<slug>.html and
│                            #   tabs.json per attempt), collect_tabs() for the report
├── _table.py                # Table normalization and HTML artifact builder
├── _console_capture.py      # TeeFile — captures pytest.log output
└── _symlinks.py             # 01_latest/ hard-copy refresh (update_latest_copy)
```

## Public API

### Fixtures (no import, auto-registered)

| Fixture | Scope | Returns | Purpose |
|---------|-------|---------|---------|
| `log` | test | `ReportLogger` | Structured logging during test phases |
| `session_log` | session | `ReportLogger` | Structured logging for session-scoped fixtures |
| `report_artifacts` | test | `pathlib.Path` | Directory path for saving test artifacts |
| `report_tabs` | test | `ReportTabs` | Custom HTML tabs in the test's detail |

### Imports

```python
from pytest_reporter import ReportLogger     # canonical public name
from pytest_reporter import Logger           # internal name, kept for compat
```

`ReportLogger` is the canonical public name documented for users. `Logger` is the underlying class name in `_logger.py`; both names refer to the same class object (`ReportLogger is Logger`).

`step`, `substep`, `fmt`, `FormattedText`, `ProcedureError` and `ProcedureNestingError`
were removed in 0.3.0; `pytest_reporter.__getattr__` raises an `ImportError` naming stepdoc.

## IDE Autocompletion — CRITICAL REQUIREMENT

All fixtures must return fully typed class instances. Ship `py.typed` marker.

The logger class is `Logger` (internal name), exported as `ReportLogger` (public name):

```python
class Logger:  # also exported as ReportLogger
    def info(self, msg: str, data: dict | None = None) -> None: ...
    def debug(self, msg: str, data: dict | None = None) -> None: ...
    def warning(self, msg: str, data: dict | None = None) -> None: ...
    def error(self, msg: str, data: dict | None = None, exc_info: BaseException | None = None) -> None: ...
    def critical(self, msg: str, data: dict | None = None, exc_info: BaseException | None = None) -> None: ...
    def child(self, name: str) -> "Logger": ...
    def table(self, data: Any, name: str = "table", *, level: str = "INFO") -> None: ...
```

### Table Logging

`log.table(data, name="...")` logs a table that appears in two places:
1. **Inline in phase logs** — rendered as a styled HTML table at the chronological log position
2. **In the Artifacts tab** — saved as a self-contained dark-theme HTML file

**Accepted input types** (zero pandas dependency — duck-typed):
- `pandas.DataFrame` — detected via `.columns` + `.values` attributes
- `list[dict]` — union of keys as columns, values as rows
- `dict[str, list]` — keys as columns, values transposed to rows

**Inline truncation**: Shows first 20 rows with a "Show all" toggle (up to 200 rows inline). Full table is always available in the HTML artifact.

**Table log entry schema** (`data` field when `_type == "table"`):
```json
{
  "_type": "table",
  "name": "voltage_readings",
  "columns": ["Channel", "Voltage", "Status"],
  "rows": [["1", "3.301", "OK"], ["2", "5.002", "OK"]],
  "total_rows": 2,
  "truncated": false,
  "artifact_name": "voltage_readings.html"
}
```

## Report Folder Structure

```
reports/
├── 01_latest/                  → hard copy of the most recent run
└── runs/
    └── YYYY_MM_DD_HH_MM_SS/   (UTC, underscores only)
        ├── report.html
        ├── junit.xml
        ├── pytest.log
        ├── session.log.json
        ├── strategies.json          (pytest-strategies 4.3+)
        ├── strategies.vectors.json  (pytest-strategies 4.3+)
        ├── failures/
        │   ├── <test>_<run>_error.log
        │   └── <test>_<run>_screenshot.png
        └── tests/
            └── <module>/<file>.py/<function>/
                ├── test.log.json           (per-function aggregate)
                ├── 01/ (or default/)
                │   ├── procedure.json
                │   ├── parameters.json
                │   ├── setup.log.json
                │   ├── call.log.json
                │   ├── teardown.log.json
                │   ├── artifacts/
                │   └── retries/            (only if retried)
                │       ├── 01/
                │       └── 02/
                └── 02/
```

**Key rules:**
- Parametrized tests: zero-padded sequential folders (`01/`, `02/`). Pytest IDs stored in `parameters.json`.
- Non-parametrized tests: single `default/` folder.
- Failure files include run identifier: `test_login_01_error.log`.
- `01_latest/` hard copy refreshed at END of run (after all files written).
- Timestamp format: `YYYY_MM_DD_HH_MM_SS` (UTC, underscores only).

## JSON Schemas

### Log Entry (§5.2)

```json
{
  "seq": 0,            // Monotonically increasing, global across all children
  "t": "ISO8601Z",     // Microsecond precision, UTC
  "level": "INFO",     // DEBUG | INFO | WARNING | ERROR | CRITICAL
  "source": ["testbench", "psu"],  // Logger path. [] for root.
  "msg": "Setting voltage",
  "data": { "voltage": 3.3 },      // Arbitrary JSON or null
  "exc": null                       // Exception schema or null
}
```

### Exception Schema (§5.3)

```json
{ "type": "ValueError", "msg": "Invalid param", "tb": "Traceback..." }
```

### Phase File (§5.4) — `setup.log.json`, `call.log.json`, `teardown.log.json`

```json
{
  "phase": "call",           // "setup" | "call" | "teardown"
  "outcome": "passed",       // "passed" | "failed" | "skipped" | "error"
  "start_time": "ISO8601Z",
  "end_time": "ISO8601Z",
  "duration_seconds": 2.345,
  "longrepr": null,          // Raw pytest traceback or null
  "entries": [ ... ]         // Flat array of log entries
}
```

### Session Log (§5.8) — `session.log.json`

Same as phase file but `phase: "session"`, no `outcome` or `longrepr`.

### test.log.json (§3) — Per-function aggregate

```json
{
  "test_id": "tests/Module/test_foo.py::test_bar",
  "function_name": "test_bar",
  "file": "tests/Module/test_foo.py",
  "total_runs": 5, "passed": 3, "failed": 1, "skipped": 1, "errors": 0,
  "total_duration_seconds": 12.34,
  "runs": [
    { "run_id": "01", "outcome": "passed", "duration_seconds": 2.1 },
    { "run_id": "02", "outcome": "passed", "duration_seconds": 8.2,
      "retries": { "attempts": 2, "original_outcome": "failed",
                   "history": ["failed", "failed", "passed"] } }
  ]
}
```

**Aggregate counter rule:** Final outcome counts. Failed-then-passed-on-retry = counted as `passed`.

### parameters.json (§4)

```json
{ "parametrize_id": "chrome-1920x1080",
  "params": { "browser": {"type": "str", "value": "chrome"} } }
```
Non-parametrized: `parametrize_id: null`, `params: {}`.

### procedure.json (§6.7)

Built from stepdoc's steps by `_stepdoc.StepCollector` (one list of top-level steps per
attempt, filled by the `pytest_stepdoc_step_started` hook, serialized at the attempt's
end, after pytest-verifier's checks were placed by stepdoc's adapter). Recursive: every
node may hold `substeps` of the same shape.

```json
{
  "source": "stepdoc",          // absent when empty: {"steps": []}
  "steps": [
    { "kind": "step", "number": "S1", "section": "setup", "description": "Power on",
      "outcome": "passed", "start_time": "...", "end_time": "...",
      "duration_seconds": 0.01, "exc": null },
    { "kind": "step", "number": "1", "section": "procedure", "description": "Measure",
      "outcome": "failed", "exc": {"type": "AssertionError", "msg": "...", "tb": ""},
      "substeps": [
        { "kind": "action", "number": "1.1", "description": "Measure dmm.voltage",
          "result": "1.65 V", "outcome": "info", "exc": null },
        { "kind": "check", "number": "1.2", "description": "Verify 'Vout' == 3.3V ± 0.05V",
          "result": "got 1.65", "detail": "expected ...", "outcome": "failed", "exc": null }
      ] }
  ]
}
```

- Numbers are renumbered per attempt (stepdoc numbers continue across the reporter's
  retries, which run inside one stepdoc protocol): `S1…` setup, `1…` procedure, `T1…`
  teardown; entries (steps, actions, checks) share the child numbering, as in stepdoc.
- A check with stepdoc's `symbolic_text` (an expected value given by name) gets
  `_stepdoc.with_values`: the symbolic text with this run's value after each name,
  `Verify 'R' == <wdata> (243)`.
- Outcomes: stepdoc `passed/failed/error/unknown/not_run` → `passed/failed/error/unknown/skipped`;
  actions are `info`; unjudged checks `unknown`.
- A loop stepdoc collapsed (a `Repeat`: `entries` plus `until` and `count`) is a
  `"kind": "repeat"` node: `Repeat until <until>`, `result` `"16 times"`, one pass as
  `substeps`, outcome the worst of its checks (else `info`). A titled `stepdoc.repeat()`
  is a stepdoc `Step` with a `loop` (`until`, `count`, `counter`, `inc`): a step node
  `<title> (repeat until <until>)` with `result` `"16 times"`. `counter`/`inc` add
  `, counting <counter>` / `, <counter> +<inc> each pass` (`_stepdoc._loop_words`). A
  write with `count > 1` reads `Repeat <target> = <value>` with `(N times)`.
- stepdoc's `note=` on a step or repeat becomes the node's `note`, shown in italics
  under its line (`.procedure-note`). A check's `Check.note` (pytest-verifier's `note=`, or
  a source comment stepdoc found) is the check node's `note`, shown inline after its text
  in parentheses (`.procedure-check-note`), as stepdoc renders it. `procedure.json` is
  written at `pytest_runtest_logfinish`, so a comment note shows only when stepdoc has
  resolved it by then (`test_verifier_comment_note_reaches_procedure` xfails otherwise).
- stepdoc 0.4 words value checks after the checked expression: `<expr> <op> <expected>`,
  or `'<name>': <expr> <op> <expected>` when the check was named. `with_values` shows the
  expression before the operator as this run has it (`dev.block.esmi3_32dat.txfe`, not
  `esmi<channel>`) and annotates only the expected side (`wdata == <wdata> (243)`).
- A check whose pytest-verifier record (stepdoc keeps it as `Check.source`) has operand
  names (`actual_name`, `expected_name`, each with an optional `_symbolic` form) is worded
  by `_stepdoc._named_text`: the symbolic names in the text, this run's `actual_name` in
  the result. `Verify tb.dev.map.block.reg<channel>.F == wdata (243)` with `result`
  `got tb.dev.map.block.reg3.F = 240`; with `name=`, `'Stored word': <actual> ...`. The
  node carries this run's `actual_name` / `expected_name`. Without an `expected_name` the
  expected side is stepdoc's (`== <wdata> (243)`); without an `actual_name` the checked
  value keeps stepdoc's wording. A description of another shape leaves the text alone.
- A step title with Markdown code spans (stepdoc's backticks / `fmt.mono`) also gets
  `description_segments` (`[{"text", "style": "mono"|null}]`, `_stepdoc.title_segments`);
  the HTML renders them as `.proc-mono`. `description` keeps the backticks.
- Checks and actions carry `generic`: the line without this run's values (stepdoc's
  `symbolic_text`; an action's `symbolic_target` / `symbolic_value`, and `generic_result`
  `<rdata>` for a read bound to a name). Checks also carry `description_segments` and
  `generic_segments` (`_stepdoc._check_segments`): `Verify` and the check's name plain, the
  code `mono`. The Procedure tab's **This run / Generic** switch (`procedureView`,
  `renderProcedure` → `renderProcedurePhases`, `renderGenericNode`) shows the generic lines
  without outcomes, results, durations or failure text.
- A stepdoc that words checks with operand names itself (`Check.operands`, `Check.label`)
  has its `text` and `symbolic_text` shown as they are; `_named_text` / `_named_generic`
  serve earlier stepdocs.
- A check stepdoc folded from one check per item (pytest-verifier's `all_satisfy`:
  `Check.each` with `count`, `failed`, `item`, `items`, `values`; its `children` are only
  the failed items, each with `index`) gets `each` (`_stepdoc._each`: plus `failed_items`
  and `values_cut`), `result` `12 of 12 passed` / `2 of 12 failed` / `12 items` (not
  judged), and no `detail` when its failed items are listed. A failed item reads
  `Verify item [3]: <code>`. JS: `renderEachValues` (a closed `<details>` of every item's
  value, failed ones marked; positions of a cut list count from the end); the Generic view
  shows the line without items or values.
- 0.2 files (no `kind`, optional `description_segments`, `check`) still render.
- stepdoc records only with one of its options: `_stepdoc.activate()` (from the
  `tryfirst` `pytest_configure`) sets `--stepdoc-record=<run>/stepdoc.json` when the user
  gave none; `report_stepdoc = false` (ini) turns that off.

### checks.json

`{"checks": [...]}`: the run's (or retry attempt's) pytest-verifier records, from
`report.verify_checks` of each phase, written only when there are checks.

## Phase Capture Flow

1. `pytest_runtest_makereport` fires for each phase (setup/call/teardown).
2. Retrieve logger from `item._reporter_logger`.
3. Call `logger.serialize()` → `{"entries": [...]}`.
4. Wrap with phase metadata (outcome, timing, longrepr).
5. Write to `{phase}.log.json`.
6. **Do NOT modify or reorder entries.** Wrap as-is.

## Check Integration (§6.10 + §15)

### What the reporter reads from pytest-verifier:
- `report.verify_checks` on each phase report (JSON-safe; nested checks inside their
  parent). Collected per attempt in `Reporter._attempt_checks`, kept for the first
  attempt in `_check_results`, written to `checks.json` per run and per retry.
- Never `import pytest_verifier` (and never `pytest_verify`: that import name belongs to
  another project on PyPI).

### Verification cards in HTML (§7.5):
- Appear inline in phase log viewer at chronological position.
- Passed: green, collapsed. Failed: red, expanded.
- Raw traceback available in collapsible section within failed cards.
- Card content varies by check_type (approx shows tolerance, between shows range, etc.).
- A record's optional `note` (pytest-verifier's `note=`) shows after the statement, in the
  card body and in the failure banner (`checkNote`); an `auto_name` label (a name taken from
  the source, `dat.txfe`) shows in monospace. Both are optional: older records lack them.
- A record's optional `actual_name` / `expected_name` (pytest-verifier's operand names: this
  run's text) show in the card body as **Actual name** / **Expected name**, each followed by
  its `_symbolic` form (`written as reg<channel>`) when the record has one
  (`operandNameEl`). A check with a `name=` of its own also shows `actual_name` beside its
  label, in the card header, the failure strip and the failure reason (`checkOperand`;
  without `name=` the name is that text already).

### Strategy export (pytest-strategies 4.3+)

- `Reporter.pytest_strategies_export_dir` is a hook wrapper (`optionalhook=True`): when no
  other implementation chose a folder and the user's `strategies_export_dir` ini option is
  empty, `StrategyExport.answer` gives the run folder. `--strategy-export` wins in
  pytest-strategies before the hook is asked. `StrategyExport.folder()` follows the same
  order to find where the files went.
- At `pytest_sessionfinish` (ours is `trylast`, after pytest-strategies wrote the files)
  `StrategyExport.load` reads `strategies.vectors.json`. From a folder the user chose, only
  files written since the session started count, and both files are copied into the run
  folder. Anything unreadable is skipped (a warning for a broken file), never an error.
- `_strategies.html_data` gives `DATA.strategies` (generator, seed, `nsamples`, counts) and
  each test's `strategies` (by node ID without parameters), each with its `rows` and their
  `items` (`nodeid`, `outcome`). The Strategy sub-tab (`renderStrategies`) shows them; a
  row's outcome is the report's own for an item that is one of the test's runs.
- The `report_strategies` ini setting (default true) turns the integration off.

## HTML Report (§7)

### Requirements:
- Single self-contained file. Inline HTML, CSS, JS.
- Responsive. Desktop and mobile.
- Fast. Lazy loading for images.
- No external CDN dependencies for charts.

### Four dashboard tabs:
1. **Summary** — Counters (passed/failed/skipped/error/retried), config-driven donut charts or
   pass-rate bars per group (no whole-suite "All Tests" donut; top counters convey totals).
2. **Tests** — Left: collapsible tree (folders → files → functions, with status pills). Right: run pills + detail sub-tabs (Summary, Procedure, Checks, Strategy, Artifacts, Retries).
3. **Session Logs** — Collapsible tree by child logger name, reconstructed from `source` arrays. Search bar + level filters.
4. **Report** — Run metadata, versions, platform, command line args, full `pytest.log` viewer.

### Test detail sub-tabs:
- **Summary:** Duration, outcome, parameters table, phase logs as horizontal tabs (Setup/Call/Teardown).
- **Procedure:** Numbered outline from `procedure.json` in Setup / Call / Teardown tabs (by each step's `section`), opening on the failed phase, else Call; actions and checks show their result. Printing shows all three.
- **Artifacts:** HTML = sandboxed iframes, Images = thumbnail grid + lightbox, Others = file cards.
- **Strategy:** (tests that use a pytest-strategies strategy, with its 4.3+ run export) each strategy's origin, `@strategy` arguments, sample count and source (`pinned` badge), arguments, constraints and the rows the test ran with their outcomes; the current run's row is highlighted.
- **Retries:** Original failure pinned at top (red), retry cards below (collapsible), final attempt expanded.

### Graph colors:
| Status | Hex |
|--------|-----|
| Passed | `#22C55E` |
| Failed | `#EF4444` |
| Skipped | `#F59E0B` |
| Error | `#F97316` |

### Feature level for graphs: configurable via `pytest_reporter_dashboard` hook / `report_dashboard` fixture.

Each group spec carries `path` (required), `depth` (default 1), `include_self` (default False), `label`,
and `style` (`"auto"` | `"donut"` | `"bars"`, default `"auto"`). When unconfigured, defaults to
depth-1 children of each top-level tree node. The whole-suite "All Tests" donut is removed; top counter
cards convey suite-level totals instead. See `_types.py` (DashboardGroupSpec / NormalizedGroup /
DashboardConfig) and `_dashboard_config.normalize_dashboard()`.

`"auto"` density heuristic (pinned threshold): `depth >= 2` OR child count > 5 → pass-rate bars;
else donut grid.

## Custom tabs

- `ReportTabs.add(title, content, *, scripts=False, height=None)` (`_tabs.py`): from the
  `report_tabs` fixture, or from `pytest_reporter_test_tabs(item, tabs)` implementations, which
  `Reporter.pytest_runtest_teardown` (tryfirst) calls before fixtures are torn down, one
  implementation at a time (`_ask_for_tabs`: `impl.function`, wrappers skipped), turning
  anything raised into a warning, outcome exceptions too: a `pytest.skip()` leaving this
  hook would stop pytest's own teardown. `Reporter.tabs_for(nodeid)` gives both the same
  object; at each attempt's setup it is dropped and the attempt's `tabs/` folder removed
  (another plugin's rerun writes to the same folder), so a retry starts empty and writes
  to `retries/XX/tabs/`.
- Titles: stripped, at most 40 characters, not a built-in tab's name (`RESERVED`), not
  repeated in the test (casefold); usage errors raise from `add()`, also without
  `--report-dir` (where nothing is saved).
- `collect_tabs` gives each run (and retry attempt) its `tabs`: `title`, `scripts`,
  `height`, `html` (`too_large` over 25 MB). Only file names inside `tabs/` are read.
- JS: `customTabs(run)` (after every built-in tab, Retries included), `renderCustomTab`.
  The HTML goes only into an iframe's `srcdoc`: `sandbox="allow-same-origin"` without
  scripts (inert, so the report measures its height), `sandbox="allow-scripts"` with them
  (its own origin; height by `postMessage` from a script of ours placed in the head, before
  the tab's markup). Never both tokens. A fragment (`customTabIsWhole`: no leading doctype
  or `<html>`) is wrapped in a page with the report's font and colors (`customTabCss`,
  system colors in print; no hex colors in the JS), which `restyleCustomTabs` rewrites on a
  theme change. `customTabHeight` adds the frame's border and stops following a document
  that follows its viewport (8 same-direction changes under 300 ms apart: default height).
  A retry card's frames are created when the card opens (a hidden frame has no size).

## Artifact System (§9)

- `report_artifacts` fixture returns `Path` to `<run>/tests/<file>/<func>/<run_id>/artifacts/`.
- Without `--report-dir`: falls back to `tmp_path`.
- During retries: path silently rerouted to `retries/XX/artifacts/`.
- Embedding: images + HTML → base64 data URIs. Others → metadata only.

## Retry System (§13)

### CLI: `--report-retries=N` (default: 0 = disabled)

### Retry scope: Only `call` phase `failed` triggers retry. NOT: passed, skipped, error, setup failure, teardown failure.

### Execution flow:
1. Run test normally. Write to `01/` (or `default/`).
2. If call failed → enter retry loop.
3. Each retry: set write path to `retries/<attempt>/`, re-execute via `runtestprotocol()`, fresh logger/fixtures.
4. Stop on pass or limit reached.
5. Final outcome in `test.log.json` and `junit.xml` = last attempt's result.

### Retry folder rules:
- `retries/` only exists if retried. No empty placeholder.
- Contains same files as run folder EXCEPT `parameters.json` (stored once in parent).
- Original failure preserved in parent folder, never moved.
- `failures/` directory: original failure only, not retry failures.

### junit.xml extension for retries:
```xml
<testcase name="test_bar[02]" classname="tests.Module.test_foo" time="8.2">
  <properties>
    <property name="retries" value="2" />
    <property name="original_outcome" value="failed" />
  </properties>
</testcase>
```

## Coding Standards

- Python 3.9+ (use `from __future__ import annotations`)
- PEP 8 with 100 character lines
- Type hints on ALL public APIs — non-negotiable for IDE autocompletion
- Docstrings (Google style) on all public methods
- pytest for testing
- No external dependencies beyond pytest
- All JSON output must be valid, serializable
- `py.typed` marker in package root

## File Boundaries

- Safe to edit: `pytest_reporter/`, `tests/`
- Never touch: `venv/`, `__pycache__/`, `.pytest_cache/`, `dist/`, `*.egg-info/`

## Testing Strategy

### Logger:
- Tree hierarchy: root → child → grandchild, correct `source` paths
- `seq` counter: global, monotonic across all children
- Serialization: flat array, correct entry schema
- Independent loggers: `log` vs `session_log` have separate `seq` counters

### Phase capture:
- Each phase writes correct file (setup/call/teardown)
- Metadata wrapping (outcome, timing, longrepr)
- Entries not modified or reordered

### Procedure (stepdoc, `tests/test_stepdoc_procedure.py`):
- Nested steps, checks and actions; setup/teardown sections; failed step exc
- Each retry attempt has its own steps, numbered from 1
- `stepdoc.json` written; user stepdoc options and `report_stepdoc = false` respected
- Empty procedure (`{"steps": []}`) without stepdoc

### Artifacts:
- Correct path resolution with and without --report-dir
- Fallback to tmp_path
- Retry path rerouting
- Embedding: base64 for images/HTML, metadata for others

### Retries:
- Only call-phase failures trigger retry
- Correct folder structure (retries/01/, retries/02/)
- Fresh logger per retry
- Final outcome is last attempt
- No parameters.json in retry folders
- `01_latest/` hard copy refreshed after all retries complete

### HTML report:
- Self-contained (no external resources)
- All four tabs render correctly
- Verification cards render from `report.verify_checks` data
- Graphs use correct colors and feature depth
- Retries tab: original failure pinned, retry cards correct

### Session logging:
- session.log.json written at session end
- Independent from per-test log
- Empty session log produces placeholder

## Common Pitfalls

- **Don't forget `py.typed`.** Without it, IDE autocompletion won't work.
- **Never import an integration.** stepdoc, pytest-verifier and pytest-strategies are optional extras (`[stepdoc]`, `[verifier]`, `[strategies]`, `[all]`); `tests/test_stepdoc_procedure.py` and `tests/test_verify_integration.py` check the imports with `ast`. Tests that need one skip without it.
- **stepdoc's recorder spans all retry attempts.** The reporter's retries run inside stepdoc's `pytest_runtest_protocol` wrapper, so `StepCollector.begin()` (at each attempt's `pytest_runtest_setup`) starts a fresh list and the procedure is renumbered.
- **Logger seq is global.** Root owns the counter. All children share it. Must be monotonically increasing but does not need to be gap-free.
- **`01_latest/` copy refreshed at END of run.** Not during. All files must be written first; the previous `01_latest/` is removed before the new copy is created.
- **Timestamp format uses underscores.** `YYYY_MM_DD_HH_MM_SS`. No colons, no dashes.
- **Entries must not be modified.** Phase capture wraps entries as-is from the logger.
- **Parametrized folder names are sequential numbers.** Not pytest IDs. IDs go in `parameters.json`.
- **Non-parametrized = `default/` folder.** Not `01/`.
- **Retry folders omit `parameters.json`.** Parent folder is the single source of truth.
- **Aggregate counters use final outcome.** Failed-then-retried-passed = counted as passed.
- **HTML report is ONE file.** Everything inline. Artifacts base64-encoded. No CDN.
- **Feature depth for graphs is configurable** via `pytest_reporter_dashboard` hook / `report_dashboard`
  fixture (DashboardGroupSpec: `path`, `depth`, `include_self`, `label`, `style`). Default: depth-1
  per top-level group. Style `"auto"` uses density heuristic (`depth >= 2` or child count > 5 → bars).
  Whole-suite "All Tests" donut is removed; top counter cards convey totals.