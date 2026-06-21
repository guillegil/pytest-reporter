# CLAUDE.md — pytest-reporter

## Project Overview

`pytest-reporter` is a pytest plugin that generates structured, human-readable and machine-readable test reports. Each test run produces a timestamped folder containing per-test logs, artifacts, procedures, and an aggregated self-contained HTML report plus JUnit XML for CI/CD. The plugin includes a built-in retry system and integrates with `pytest-verify` for verification card rendering.

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
│  IMPORTS (explicit):                                        │
│  ┌────────────────────────────────────────┐                 │
│  │ from pytest_reporter import step, substep               │
│  └────────────────────────────────────────┘                 │
│                                                             │
│  HOOKS:                                                     │
│  ┌──────────────────────────────┐                           │
│  │ pytest_runtest_makereport    │ → phase log capture       │
│  │ pytest_runtest_protocol      │ → retry engine            │
│  │ pytest_sessionfinish         │ → session log + HTML gen  │
│  └──────────────────────────────┘                           │
│                                                             │
│  READS item.stash for verification cards (from pytest-verify)│
│  NEVER evaluates check descriptors or determines pass/fail  │
└─────────────────────────────────────────────────────────────┘
```

## Core Principles

- **The reporter observes, never judges.** It never raises exceptions to determine test outcomes. It hooks into `pytest_runtest_makereport` to observe what happened and records it. Pass/fail for checks is determined by `pytest-verify`.
- **Fixtures are the public API.** `log`, `session_log`, `report_artifacts` are pytest fixtures (no import). `step` and `substep` are functions (explicit import from `pytest_reporter`).
- **Single self-contained HTML report.** `report.html` must be one file with inline HTML, CSS, JS. Artifacts are base64-encoded as data URIs. No external CDN dependencies.
- **Flat serialization with source paths.** The logger uses a tree API in memory but serializes to flat arrays with `source` path arrays. Never nest on disk.
- **step(check=...) is presentation only.** When receiving a check descriptor, `step()` stores it as inline metadata on the step. The check description is rendered alongside the step text (e.g. `CPU fan above 1500 RPM — CPU fan > 1500 RPM [PASS]`). It does NOT evaluate, does NOT determine pass/fail, does NOT write to stash, does NOT create a substep.

## CLI Options

```bash
pytest tests/ --report-dir=reports                   # Activate reporter
pytest tests/ --report-dir=reports --report-retries=3  # Enable retries
```

## Package Structure

```
pytest_reporter/
├── __init__.py              # Exports: step, substep, Logger, ReportLogger
├── py.typed                 # PEP 561 marker — REQUIRED
├── plugin.py                # Plugin registration (pytest11 entry point)
├── reporter.py              # Reporter class — main hook orchestrator
├── _collector.py            # DataCollector — item registry, phase tracking, aggregation
├── _context.py              # RunContext — timestamped run directory management
├── _logger.py               # Logger class (+ ReportLogger alias) — tree-based structured logger
├── _procedure.py            # step(), substep(), ProcedureTracker, procedure.json writing
├── _types.py                # Shared TypedDicts and type aliases
├── _json_writer.py          # Phase log, test.log.json, session.log.json writers
├── _junit_writer.py         # junit.xml generation
├── _html_builder.py         # Self-contained HTML report generation at session end
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

### Functions and types (explicit import)

```python
from pytest_reporter import step, substep
from pytest_reporter import ReportLogger  # canonical public name
from pytest_reporter import Logger        # internal name, kept for compat

step(description: str, *, check: dict | None = None) -> ContextManager
substep(description: str) -> None
```

`ReportLogger` is the canonical public name documented for users. `Logger` is the underlying class name in `_logger.py`; both names refer to the same class object (`ReportLogger is Logger`).

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

```json
{
  "steps": [
    { "number": "1", "description": "...", "outcome": "passed",
      "start_time": "...", "end_time": "...", "duration_seconds": 0.0,
      "exc": null,
      "check": { ... },     // Optional — inline check descriptor
      "description_segments": [   // Optional — absent when no backtick markup
        {"text": "Set ", "style": null},
        {"text": "Pulse.Enable", "style": "mono"},
        {"text": " to 1", "style": null}
      ],
      "substeps": [
        { "number": "1.1", "description": "...", "outcome": "passed", ... ,
          "check": { ... },  // Optional — inline check descriptor
          "description_segments": [...]  // Optional — absent when no backtick markup
        }
      ]
    }
  ]
}
```

**`description_segments` rules:**
- Present only when the description contains at least one backtick-delimited span.
- Absent (key omitted, not null) for plain descriptions — backward compatible.
- Each element: `{"text": str, "style": "mono" | null}`. `"mono"` = backtick span, `null` = plain run.
- Raw `description` field always retained as-is (backticks included).
- Forward-compatible: new `style` values may be added in future versions.

## Phase Capture Flow

1. `pytest_runtest_makereport` fires for each phase (setup/call/teardown).
2. Retrieve logger from `item._reporter_logger`.
3. Call `logger.serialize()` → `{"entries": [...]}`.
4. Wrap with phase metadata (outcome, timing, longrepr).
5. Write to `{phase}.log.json`.
6. **Do NOT modify or reorder entries.** Wrap as-is.

## Procedure System

### step() behavior:
- Plain call: records step, outcome = `passed` (execution reached this line).
- Context manager: `__enter__` records start, `__exit__` records end + outcome. Exceptions re-raised.
- With `check=descriptor`: creates auto substep from `descriptor["description"]`. Does NOT evaluate.
- Counters reset per test via `pytest_runtest_call`.

### Depth limit: exactly 2 levels.
- `step()` → level 1
- `substep()` or `step()` inside `with step()` → level 2
- Deeper → `ProcedureNestingError`

### `substep()` before any `step()` → promotes to a top-level step

If `substep()` is called before any step has been recorded, it is promoted to a
top-level step (description preserved, no raise). `substep()` binds to `_steps[-1]` —
the most-recently-recorded step ("last step wins"), NOT necessarily the open CM step.

## Check Integration (§6.10 + §15)

### What step(check=...) does:
1. Records the step as usual.
2. Stores the check descriptor directly on the step's `check` field.
3. Does NOT create a substep. The check is inline metadata on the step.
4. In the HTML procedure view, rendered as: `description — check_description` (no PASS/FAIL badge).
5. That's ALL. No evaluation, no stash write, no pass/fail.

### What the reporter reads from item.stash:
- Stash key: `StashKey[list]()` — shared convention with pytest-verify.
- If present: renders verification cards in HTML (green pass / red fail cards).
- If absent: renders standard longrepr tracebacks.

### Verification cards in HTML (§7.5):
- Appear inline in phase log viewer at chronological position.
- Passed: green, collapsed. Failed: red, expanded.
- Raw traceback available in collapsible section within failed cards.
- Card content varies by check_type (approx shows tolerance, between shows range, etc.).

## HTML Report (§7)

### Requirements:
- Single self-contained file. Inline HTML, CSS, JS.
- Responsive. Desktop and mobile.
- Fast. Lazy loading for images.
- No external CDN dependencies for charts.

### Four dashboard tabs:
1. **Summary** — Counters (passed/failed/skipped/error/retried), config-driven donut charts or
   pass-rate bars per group (no whole-suite "All Tests" donut; top counters convey totals).
2. **Tests** — Left: collapsible tree (folders → files → functions, with status pills). Right: run pills + detail sub-tabs (Summary, Procedure, Artifacts, Retries).
3. **Session Logs** — Collapsible tree by child logger name, reconstructed from `source` arrays. Search bar + level filters.
4. **Report** — Run metadata, versions, platform, command line args, full `pytest.log` viewer.

### Test detail sub-tabs:
- **Summary:** Duration, outcome, parameters table, phase logs as horizontal tabs (Setup/Call/Teardown).
- **Procedure:** Numbered outline from `procedure.json`. Check substeps show verification description only (no pass/fail).
- **Artifacts:** HTML = sandboxed iframes, Images = thumbnail grid + lightbox, Others = file cards.
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

### Procedure:
- step/substep numbering: 1, 2, 2.1, 2.2, 3
- Context manager: timing, outcome tracking, exception re-raise
- check= parameter: substep created from description, check field in JSON
- Depth limit: >2 raises ProcedureNestingError
- substep before step: promotes to a top-level step (no raise); no-active-tracker ProcedureError (from _get_tracker) is unchanged
- Counter reset per test

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
- Verification cards render from stash data
- Graphs use correct colors and feature depth
- Retries tab: original failure pinned, retry cards correct

### Session logging:
- session.log.json written at session end
- Independent from per-test log
- Empty session log produces placeholder

## Common Pitfalls

- **Don't forget `py.typed`.** Without it, IDE autocompletion won't work.
- **Logger seq is global.** Root owns the counter. All children share it. Must be monotonically increasing but does not need to be gap-free.
- **`01_latest/` copy refreshed at END of run.** Not during. All files must be written first; the previous `01_latest/` is removed before the new copy is created.
- **Timestamp format uses underscores.** `YYYY_MM_DD_HH_MM_SS`. No colons, no dashes.
- **step(check=...) does NOT evaluate.** It stores the descriptor as inline metadata on the step. It does NOT create a substep. The reporter NEVER determines pass/fail.
- **Entries must not be modified.** Phase capture wraps entries as-is from the logger.
- **Parametrized folder names are sequential numbers.** Not pytest IDs. IDs go in `parameters.json`.
- **Non-parametrized = `default/` folder.** Not `01/`.
- **Retry folders omit `parameters.json`.** Parent folder is the single source of truth.
- **Aggregate counters use final outcome.** Failed-then-retried-passed = counted as passed.
- **`substep()` before any `step()` promotes, does NOT raise.** Calling `substep()` with no prior step promotes the call to a top-level step (description preserved). The no-active-tracker `ProcedureError` (raised by `_get_tracker` when called outside a test) is unchanged.
- **`substep()` binds to the last-recorded step (`_steps[-1]`), not the open CM step.** "Last step wins" — if a plain `step()` was called inside a CM body, `substep()` attaches to that inner step.
- **HTML report is ONE file.** Everything inline. Artifacts base64-encoded. No CDN.
- **Feature depth for graphs is configurable** via `pytest_reporter_dashboard` hook / `report_dashboard`
  fixture (DashboardGroupSpec: `path`, `depth`, `include_self`, `label`, `style`). Default: depth-1
  per top-level group. Style `"auto"` uses density heuristic (`depth >= 2` or child count > 5 → bars).
  Whole-suite "All Tests" donut is removed; top counter cards convey totals.