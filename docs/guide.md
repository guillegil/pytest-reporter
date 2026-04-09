# User Guide

Complete reference for pytest-reporter: CLI options, fixtures, output files, the HTML report, and integration with CI/CD.

---

## Table of Contents

- [Installation](#installation)
- [CLI Options](#cli-options)
- [Fixtures](#fixtures)
  - [`log` -- Per-Test Structured Logger](#log----per-test-structured-logger)
  - [`session_log` -- Session-Level Logger](#session_log----session-level-logger)
  - [`report_artifacts` -- Test Artifacts](#report_artifacts----test-artifacts)
- [Procedure System](#procedure-system)
  - [`step()` and `substep()`](#step-and-substep)
  - [Context Manager Usage](#context-manager-usage)
  - [Nesting Rules](#nesting-rules)
- [Retry System](#retry-system)
  - [How Retries Work](#how-retries-work)
  - [What Gets Retried](#what-gets-retried)
  - [Folder Structure](#retry-folder-structure)
- [Output Files](#output-files)
  - [Report Folder Structure](#report-folder-structure)
  - [Phase Logs](#phase-logs)
  - [test.log.json](#testlogjson)
  - [parameters.json](#parametersjson)
  - [procedure.json](#procedurejson)
  - [session.log.json](#sessionlogjson)
  - [junit.xml](#junitxml)
- [HTML Report](#html-report)
  - [Summary Tab](#summary-tab)
  - [Tests Tab](#tests-tab)
  - [Session Logs Tab](#session-logs-tab)
  - [Report Tab](#report-tab)
- [CI/CD Integration](#cicd-integration)
- [Parametrized Tests](#parametrized-tests)
- [Configuration Reference](#configuration-reference)

---

## Installation

```bash
pip install pytest-reporter
```

**Requirements:** Python 3.11+, pytest 7.4+.

For development:

```bash
pip install pytest-reporter[dev]
```

---

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--report-dir=PATH` | *(none)* | Enable reporting. All output goes under this directory. |
| `--report-retries=N` | `0` | Maximum retry attempts per failed test. `0` disables retries. |

The plugin is only active when `--report-dir` is provided. Without it, all fixtures (`log`, `session_log`, `report_artifacts`) still work but produce no files --- tests remain runnable without the flag.

---

## Fixtures

### `log` -- Per-Test Structured Logger

**Scope:** function (per-test)

The `log` fixture provides a tree-based structured logger. Entries are captured at the end of each pytest phase (setup, call, teardown) and written to phase log files.

```python
def test_api_call(log):
    log.info("Starting test")
    log.debug("Configuration loaded", data={"timeout": 30, "retries": 3})

    api = log.child("api")
    api.info("POST /users", data={"email": "test@example.com"})

    auth = api.child("auth")
    auth.info("Token acquired", data={"expires_in": 3600})
```

#### Logger API

| Method | Description |
|--------|-------------|
| `log.debug(msg, data=None, exc_info=None)` | Log at DEBUG level |
| `log.info(msg, data=None, exc_info=None)` | Log at INFO level |
| `log.warning(msg, data=None, exc_info=None)` | Log at WARNING level |
| `log.error(msg, data=None, exc_info=None)` | Log at ERROR level |
| `log.critical(msg, data=None, exc_info=None)` | Log at CRITICAL level |
| `log.child(name)` | Create a child logger. Returns a new `Logger`. |

**Parameters:**
- `msg` (str) -- Human-readable log message.
- `data` (dict, optional) -- Arbitrary JSON-serializable payload.
- `exc_info` (BaseException, optional) -- Exception to capture with type, message, and traceback.

#### Child Loggers

Child loggers create a hierarchy tracked via the `source` field:

```python
api = log.child("api")        # source: ["api"]
auth = api.child("auth")      # source: ["api", "auth"]
```

The tree is serialized as a flat array --- entries appear in execution order with their `source` path.

#### Exception Capture

```python
try:
    result = call_external_service()
except TimeoutError as e:
    log.error("Service timed out", exc_info=e)
```

The exception type, message, and full traceback are stored in the `exc` field of the log entry.

#### Entry Schema

Each entry in a phase log file:

```json
{
  "seq": 0,
  "t": "2026-04-03T14:30:00.123456Z",
  "level": "INFO",
  "source": ["api", "auth"],
  "msg": "Token acquired",
  "data": { "expires_in": 3600 },
  "exc": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `seq` | int | Monotonically increasing sequence number (per-test). |
| `t` | string | ISO 8601 UTC timestamp with microsecond precision. |
| `level` | string | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `source` | string[] | Logger path from root. `[]` for root logger. |
| `msg` | string | Human-readable message. |
| `data` | object \| null | Optional structured payload. |
| `exc` | object \| null | Exception info (`type`, `msg`, `tb`) or null. |

---

### `session_log` -- Session-Level Logger

**Scope:** session

Identical API to `log`, but entries are written to `session.log.json` at the end of the test run. Use it in session-scoped fixtures for setup/teardown logging that happens outside any individual test.

```python
@pytest.fixture(scope="session")
def database(session_log):
    db = session_log.child("database")
    db.info("Creating connection pool", data={"host": "db.internal", "pool_size": 10})
    pool = create_pool()
    db.info("Pool ready")

    yield pool

    db.info("Draining connections")
    pool.close()
```

The `session_log` and `log` fixtures are **independent** --- they have separate sequence counters and separate output files. Session logs go to `session.log.json`; test logs go to `setup.log.json` / `call.log.json` / `teardown.log.json`.

---

### `report_artifacts` -- Test Artifacts

**Scope:** function (per-test)

Returns a `pathlib.Path` to a writable directory for test artifacts. Files saved here are embedded in the HTML report.

```python
def test_generate_report(report_artifacts):
    html = "<table><tr><td>Revenue</td><td>$1.2M</td></tr></table>"
    (report_artifacts / "summary.html").write_text(html)

    # Images, JSON, any file type
    (report_artifacts / "chart.png").write_bytes(png_data)
    (report_artifacts / "raw_data.json").write_text(json_string)
```

**Embeddable types** (base64-encoded into the HTML report):
- Images: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`, `.bmp`
- HTML: `.html`, `.htm`

**Non-embeddable types** (metadata only in the report; files remain on disk):
- All other extensions (`.json`, `.log`, `.csv`, `.har`, etc.)

When `--report-dir` is not active, the fixture falls back to `tmp_path / "artifacts"` so tests remain runnable.

---

## Procedure System

### `step()` and `substep()`

Import directly from the package:

```python
from pytest_reporter import step, substep
```

**Plain calls** record steps/substeps immediately:

```python
def test_checkout(log):
    step("Add items to cart")
    substep("Select product A")
    substep("Set quantity to 2")

    step("Apply discount code")
    step("Submit order")
```

Produces:
```
1. Add items to cart
   1.1. Select product A
   1.2. Set quantity to 2
2. Apply discount code
3. Submit order
```

### Context Manager Usage

`step()` can also be used as a context manager. Inside the block, subsequent `step()` calls become substeps:

```python
def test_deployment(log):
    step("Prepare environment")

    with step("Deploy application"):
        step("Build container image")      # becomes 2.1
        step("Push to registry")           # becomes 2.2
        step("Update Kubernetes manifest") # becomes 2.3

    step("Run smoke tests")
```

Produces:
```
1. Prepare environment
2. Deploy application
   2.1. Build container image
   2.2. Push to registry
   2.3. Update Kubernetes manifest
3. Run smoke tests
```

When used as a context manager, `step()` tracks:
- **Timing:** `start_time`, `end_time`, `duration_seconds`
- **Outcome:** `passed` if the block completes, `failed` if an exception propagates
- **Exception info:** captured in the `exc` field (exceptions are **not** swallowed)

### Nesting Rules

The procedure system supports exactly **two levels**: steps (level 1) and substeps (level 2).

```python
with step("Level 1"):                     # OK
    with step("Level 2"):                 # OK
        with step("Level 3"):             # raises ProcedureNestingError
            ...
```

Calling `substep()` before any `step()` raises `ProcedureError`.

Step counters reset at the start of each test.

---

## Retry System

### How Retries Work

Enable with `--report-retries=N`:

```bash
pytest --report-dir=reports --report-retries=3
```

When a test's **call phase** fails:
1. The original failure is preserved in the run folder.
2. The test is re-executed up to N times.
3. If any retry passes, the test's final outcome is **passed**.
4. If all retries fail, the final outcome is **failed**.
5. All attempts (original + retries) are stored for investigation.

### What Gets Retried

| Scenario | Retried? | Reason |
|----------|----------|--------|
| Call phase failed | Yes | Test assertion failure |
| Setup phase failed | No | Infrastructure error |
| Teardown phase failed | No | Test itself passed/failed independently |
| Test skipped | No | Intentional |
| Test passed | No | Nothing to retry |
| `--report-retries=0` | No | Retries disabled |

### Retry Folder Structure

```
tests/<file>/<function>/
├── 02/                           # Run that was retried
│   ├── parameters.json           # Source of truth for all attempts
│   ├── procedure.json            # Original attempt
│   ├── call.log.json             # outcome: "failed"
│   ├── setup.log.json
│   ├── teardown.log.json
│   ├── artifacts/
│   └── retries/
│       ├── 01/                   # Retry attempt 1 -- still failed
│       │   ├── procedure.json
│       │   ├── call.log.json     # outcome: "failed"
│       │   ├── setup.log.json
│       │   ├── teardown.log.json
│       │   └── artifacts/
│       └── 02/                   # Retry attempt 2 -- passed
│           ├── procedure.json
│           ├── call.log.json     # outcome: "passed"
│           └── ...
```

Key points:
- `parameters.json` exists only in the parent run folder (not duplicated in retries).
- The `retries/` directory only exists when at least one retry was performed.
- The `failures/` directory captures the **original** failure only.
- Each retry gets its own `procedure.json`, phase logs, and `artifacts/`.

---

## Output Files

### Report Folder Structure

Every run creates a timestamped directory:

```
reports/
├── 01_latest                     -> runs/YYYY_MM_DD_HH_MM_SS
├── 02_latest_failures            -> runs/YYYY_MM_DD_HH_MM_SS/failures
└── runs/
    └── YYYY_MM_DD_HH_MM_SS/
        ├── report.html
        ├── junit.xml
        ├── pytest.log
        ├── session.log.json
        ├── failures/
        │   └── <test_name>_<run>_error.log
        └── tests/
            └── <module>/<test_file>.py/<test_function>/
                ├── test.log.json
                ├── 01/ (or default/)
                │   ├── procedure.json
                │   ├── parameters.json
                │   ├── setup.log.json
                │   ├── call.log.json
                │   ├── teardown.log.json
                │   └── artifacts/
                └── 02/ ...
```

Symlinks are updated at the end of each run:
- `01_latest` always points to the most recent run.
- `02_latest_failures` always points to the most recent run's `failures/` directory.

### Phase Logs

`setup.log.json`, `call.log.json`, `teardown.log.json`:

```json
{
  "phase": "call",
  "outcome": "passed",
  "start_time": "2026-04-03T14:30:00.000000Z",
  "end_time": "2026-04-03T14:30:02.345678Z",
  "duration_seconds": 2.3457,
  "longrepr": null,
  "entries": [
    { "seq": 0, "t": "...", "level": "INFO", "source": [], "msg": "Starting test", "data": null, "exc": null }
  ]
}
```

Phase logs are written **immediately** after each phase completes (they survive crashes).

### test.log.json

Per-function aggregate across all parametrized runs:

```json
{
  "test_id": "tests/API/test_endpoints.py::test_crud",
  "function_name": "test_crud",
  "file": "tests/API/test_endpoints.py",
  "total_runs": 3,
  "passed": 2,
  "failed": 1,
  "skipped": 0,
  "errors": 0,
  "total_duration_seconds": 1.234,
  "runs": [
    { "run_id": "01", "outcome": "passed", "duration_seconds": 0.41 },
    { "run_id": "02", "outcome": "passed", "duration_seconds": 0.82,
      "retries": { "attempts": 1, "original_outcome": "failed", "history": ["failed", "passed"] }
    }
  ]
}
```

Aggregate counters use the **final** outcome. A test that failed then passed on retry counts as **passed**.

### parameters.json

```json
{
  "parametrize_id": "chrome-1920x1080",
  "params": {
    "browser": { "type": "str", "value": "chrome" },
    "resolution": { "type": "str", "value": "1920x1080" }
  }
}
```

Non-parametrized tests: `parametrize_id` is `null`, `params` is `{}`.

### procedure.json

```json
{
  "steps": [
    {
      "number": "1",
      "description": "Fetch user data",
      "outcome": "passed",
      "start_time": "...",
      "end_time": "...",
      "duration_seconds": 0.0,
      "exc": null,
      "substeps": []
    },
    {
      "number": "2",
      "description": "Generate report",
      "outcome": "passed",
      "start_time": "...",
      "end_time": "...",
      "duration_seconds": 1.4,
      "exc": null,
      "substeps": [
        {
          "number": "2.1",
          "description": "Render HTML",
          "outcome": "passed",
          "start_time": "...",
          "end_time": "...",
          "duration_seconds": 0.0,
          "exc": null
        }
      ]
    }
  ]
}
```

### session.log.json

```json
{
  "phase": "session",
  "start_time": "2026-04-03T14:00:00.000000Z",
  "end_time": "2026-04-03T14:05:30.000000Z",
  "duration_seconds": 330.0,
  "entries": [
    { "seq": 0, "t": "...", "level": "INFO", "source": ["testbench"], "msg": "Discovering instruments", "data": null, "exc": null }
  ]
}
```

If no code uses the `session_log` fixture, the file contains an empty `entries` array.

### junit.xml

Standard JUnit XML compatible with all major CI platforms. When retries are enabled, retried tests include `<property>` elements:

```xml
<testcase name="test_flaky[02]" classname="tests.API.test_endpoints" time="8.2">
  <properties>
    <property name="retries" value="2" />
    <property name="original_outcome" value="failed" />
  </properties>
</testcase>
```

---

## HTML Report

The report is a single self-contained HTML file --- no external dependencies, no CDN. Open it directly in any browser.

### Summary Tab

- **Counters:** Passed, Failed, Skipped, Errors, Retried (when enabled), Total.
- **Overall donut chart:** pass/fail/skipped/error distribution.
- **Per-feature donut charts:** one chart per top-level test group.

The **Tests Retried** counter is hidden when `--report-retries=0`.

### Tests Tab

Split into two panels:

**Left panel** -- Collapsible tree mirroring the test folder hierarchy:
- Feature folders with status pills (`3p / 1f / 0s / 0e`).
- Test files with function count.
- Search bar and status filter toggles.

**Right panel** -- Test detail view:
- **Run pills** with status colors. Retried runs show a retry badge (`↻2`).
- **Summary sub-tab:** outcome, duration, parameters table, and phase logs as horizontal tabs (Setup / Call / Teardown). Each phase shows structured log entries with level badges, source paths, expandable data, and exception details.
- **Procedure sub-tab:** numbered step outline with status dots, timing, and exception details.
- **Artifacts sub-tab:** HTML files rendered as iframes, images as thumbnail grids with lightbox, other files as cards.
- **Retries sub-tab** (only when retries occurred): original failure card pinned at top, followed by collapsible retry attempt cards with their own phase logs and procedure.

### Session Logs Tab

Displays session-level logs grouped by source path as a collapsible tree:

```
testbench (4 entries)
  ├── psu (2 entries)
  └── scope (2 entries)
```

Includes a search bar for filtering entries by message, source, or level.

### Report Tab

Run metadata: timestamp, duration, Python/pytest versions, platform, active plugins, command-line arguments.

---

## CI/CD Integration

The `junit.xml` file is compatible out of the box with:

| Platform | Setup |
|----------|-------|
| **GitHub Actions** | Use `dorny/test-reporter` or `mikepenz/action-junit-report` |
| **GitLab CI** | Add `junit.xml` to `artifacts:reports:junit` |
| **Jenkins** | JUnit Plugin |
| **CircleCI** | `store_test_results` step |
| **Azure DevOps** | `PublishTestResults` task |

Example GitHub Actions workflow:

```yaml
- name: Run tests
  run: pytest --report-dir=reports --report-retries=2

- name: Upload HTML report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: test-report
    path: reports/01_latest/report.html

- name: Publish JUnit results
  if: always()
  uses: dorny/test-reporter@v1
  with:
    name: Test Results
    path: reports/01_latest/junit.xml
    reporter: java-junit
```

---

## Parametrized Tests

Parametrized tests use zero-padded sequential folder names (`01/`, `02/`, `03/`, ...) instead of pytest IDs (which often contain filesystem-unfriendly characters). The full pytest parametrize ID is stored inside `parameters.json`.

Non-parametrized tests use a single `default/` folder.

Files in the `failures/` directory include the run identifier to avoid collisions:
- `test_login_01_error.log`
- `test_login_default_error.log`

---

## Configuration Reference

### pyproject.toml

```toml
[tool.pytest.ini_options]
addopts = [
    "--report-dir=reports",
    "--report-retries=2",
]
```

### Command line

```bash
# Basic report
pytest --report-dir=reports

# With retries
pytest --report-dir=reports --report-retries=3

# Combine with other flags
pytest --report-dir=reports --report-retries=2 -v --tb=long -x
```

### Fixtures summary

| Fixture | Scope | Returns | Description |
|---------|-------|---------|-------------|
| `log` | function | `Logger` | Per-test structured logger |
| `session_log` | session | `Logger` | Session-level structured logger |
| `report_artifacts` | function | `Path` | Writable directory for test artifacts |

### Imports

```python
from pytest_reporter import step, substep
from pytest_reporter import ProcedureError, ProcedureNestingError
```

All fixtures are registered automatically --- no import or conftest setup needed.
