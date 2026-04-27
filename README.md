# pytest-reporter

A pytest plugin that turns every test run into a self-contained, structured report — JSON logs, JUnit XML, an interactive HTML dashboard, embedded artifacts, retries, and rich tables — all generated locally with zero external dependencies beyond pytest.

> **Status:** Alpha · Python 3.11+ · MIT license

---

## Why

`pytest-reporter` is built for projects that need more than pass/fail counts: hardware test benches, data pipelines, integration suites, and any workflow where you want to **see** what the test did. Every run produces:

- A timestamped folder under `reports/runs/YYYY_MM_DD_HH_MM_SS/` with per-test JSON logs, parameters, procedures, and artifacts.
- A self-contained `report.html` dashboard — open it in any browser, no server required.
- A `junit.xml` for CI/CD integration.
- A complete copy of the most recent run at `reports/01_latest/` for quick access.
- Optional automatic retries for flaky tests, with each attempt preserved separately.

---

## Features

| | |
|---|---|
| 📂 **Structured reports** | Timestamped run folders with per-test JSON logs and aggregates. |
| 🖥 **Self-contained HTML dashboard** | Single `report.html` file — no CDNs, no external assets. Summary, Tests, Session Logs, and Report tabs. |
| 🪵 **Hierarchical structured logging** | `log.info(...)`, `log.child("psu").debug(...)` — flat serialization with `source` paths. |
| 📊 **Inline tables** | `log.table(df, name="readings")` — pandas DataFrames, `list[dict]`, or `dict[str, list]` rendered inline and saved as HTML artifacts. |
| 🪜 **Procedure tracking** | `step()` / `substep()` capture test procedures with timing and outcome. |
| 🔁 **Built-in retries** | `--report-retries=N` re-runs failed tests with separate logs per attempt. |
| 📎 **Artifacts** | `report_artifacts` fixture for screenshots, CSVs, HTML — embedded as data URIs in the report. |
| 🔌 **pytest-verify integration** | Verification cards rendered inline with check details. |
| 📦 **JUnit XML** | Standard CI/CD output, augmented with retry metadata. |
| ✅ **Typed** | Ships `py.typed`; full IDE autocompletion on every fixture. |
| 🪶 **Zero deps beyond pytest** | Optional pandas support is duck-typed — no hard dependency. |

---

## Installation

```bash
pip install pytest-reporter
```

Or with `uv`:

```bash
uv pip install pytest-reporter
```

For local development:

```bash
git clone https://github.com/guillegil/pytest-reporter
cd pytest-reporter
uv pip install -e ".[dev]"
```

---

## Quick start

Activate reporting by passing `--report-dir`:

```bash
pytest tests/ --report-dir=reports
```

That single flag produces:

```
reports/
├── 01_latest/                      # Hard copy of the most recent run
└── runs/
    └── 2026_04_27_18_30_45/
        ├── report.html             # Open in any browser
        ├── junit.xml               # CI/CD
        ├── pytest.log              # Captured console output
        ├── session.log.json        # Session-scoped logs
        ├── failures/               # Per-test error logs
        └── tests/                  # Per-test structured data
            └── path/to/file.py/test_function/
                ├── test.log.json   # Aggregated outcomes across runs
                └── default/        # (or 01/, 02/ for parametrized)
                    ├── procedure.json
                    ├── parameters.json
                    ├── setup.log.json
                    ├── call.log.json
                    ├── teardown.log.json
                    └── artifacts/
```

Open `reports/01_latest/report.html` to see the dashboard.

### CLI options

| Flag | Default | Description |
|---|---|---|
| `--report-dir=<path>` | *(off)* | Activate reporting and write everything under `<path>/`. |
| `--report-retries=<N>` | `0` | When >0, automatically re-run tests whose `call` phase fails, up to `N` times. |

---

## Public API

The plugin auto-registers three fixtures (no imports needed) and exports two functions:

### Fixtures

| Fixture | Scope | Returns | Purpose |
|---|---|---|---|
| `log` | test | `Logger` | Structured logging during a test. |
| `session_log` | session | `Logger` | Structured logging from session-scoped fixtures. |
| `report_artifacts` | test | `pathlib.Path` | Directory to save artifacts (images, HTML, CSV, anything). |

### Functions

```python
from pytest_reporter import step, substep
```

---

## Logging

The `log` fixture is a hierarchical logger. Every entry has a timestamp, level, source path, message, and optional structured `data`.

```python
def test_login(log):
    log.info("Starting login flow")
    log.debug("Auth token", data={"prefix": "eyJhbGci..."})

    api = log.child("api")
    api.info("POST /session")
    api.warning("Rate-limited", data={"retry_after_s": 5})
```

Child loggers prefix entries with their path (`["api"]`) so you can group, filter, and search them in the HTML dashboard.

The `Logger` exposes:

```python
log.debug(msg, data=None)
log.info(msg, data=None)
log.warning(msg, data=None)
log.error(msg, data=None, exc_info=None)
log.critical(msg, data=None, exc_info=None)
log.child(name) -> Logger
log.table(data, name="table", *, level="INFO")
```

### Tables

`log.table(...)` renders tabular data inline in the phase log **and** as a styled HTML artifact in the Artifacts tab. It accepts:

- `pandas.DataFrame` (duck-typed — no pandas dependency)
- `list[dict]` — union of keys becomes the column set
- `dict[str, list]` — keys are columns, values are rows

```python
def test_psu_channels(log):
    psu = log.child("psu")

    readings = [
        {"Channel": "CH1", "Nominal (V)": 3.3,  "Measured": 3.301, "Status": "PASS"},
        {"Channel": "CH2", "Nominal (V)": 5.0,  "Measured": 5.002, "Status": "PASS"},
        {"Channel": "CH3", "Nominal (V)": 12.0, "Measured": 11.98, "Status": "PASS"},
    ]
    psu.table(readings, name="channel_readings")
```

Inline view is truncated to 20 rows with a "Show all" toggle (up to 200 rows). The full table is always available as `artifacts/channel_readings.html`.

---

## Procedures

`step()` and `substep()` document the procedural structure of a test. They appear in the **Procedure** sub-tab of every test detail.

```python
from pytest_reporter import step, substep

def test_voltage_sweep(log, verify):
    psu = log.child("psu")

    with step("Enable 3.3 V output"):
        psu.info("Setting CH1 to 3.3 V")

    with step("Sweep load 0–1 A"):
        for amps in (0.0, 0.25, 0.5, 1.0):
            substep(f"load = {amps} A")
            psu.info("load applied", data={"amps": amps})

    voltage = read_voltage()

    step("Verify voltage within tolerance",
         check=verify.approx(voltage, 3.3, abs_tol=0.05, name="CH1 voltage"))
```

- Used as a **context manager** (`with step(...)`) it captures timing and propagates exceptions.
- Used as a **plain call** it just records the step.
- `step(check=...)` attaches a verification descriptor (presentation only — `pytest-reporter` never determines pass/fail; that's `pytest-verify`'s job).
- Maximum nesting depth: 2 (`step` → `substep`/`step`-inside-`with`).

---

## Artifacts

Anything saved to `report_artifacts` is collected and indexed in the HTML dashboard.

```python
def test_screenshot(report_artifacts):
    report_artifacts.mkdir(parents=True, exist_ok=True)
    (report_artifacts / "screenshot.png").write_bytes(capture())
    (report_artifacts / "metrics.csv").write_text("a,b\n1,2\n")
```

Behavior in the report:

| Type | Behavior |
|---|---|
| `.png .jpg .jpeg .gif .webp .svg .bmp` | Thumbnail grid + click-to-zoom lightbox. |
| `.html .htm` | Rendered inline in a sandboxed iframe (auto-resized). |
| Anything else | File card showing name and size. |

Embeddable types are base64-encoded into the HTML so the report stays portable.

When `--report-retries` is enabled, each retry attempt gets its own `retries/01/artifacts/`, `retries/02/artifacts/`, etc.

---

## Retries

Enable automatic retries for the `call` phase of failed tests:

```bash
pytest --report-dir=reports --report-retries=3
```

Behavior:

- Only `call`-phase failures trigger retries (not setup/teardown/skipped).
- Each attempt runs with a fresh logger and procedure tracker.
- The original failure is preserved in the run's main folder; retries land in `retries/01/`, `retries/02/`, …
- The final outcome (last attempt) is what appears in `test.log.json` and `junit.xml`.
- The HTML dashboard's **Retries** sub-tab shows the original failure pinned at the top, with each retry attempt as a collapsible card below.

`junit.xml` retry metadata:

```xml
<testcase name="test_flaky" classname="tests.test_app" time="2.4">
  <properties>
    <property name="retries" value="2"/>
    <property name="original_outcome" value="failed"/>
  </properties>
</testcase>
```

---

## HTML report

The `report.html` is a single self-contained file with four tabs:

1. **Summary** — pass-rate hero, ratio bar, status counters with percentages, donut charts (overall, top-level groups, per-feature).
2. **Tests** — collapsible test tree with status badges; per-test detail panel with sub-tabs for **Summary** (parameters, phase logs), **Procedure**, **Artifacts**, **Retries**, and **Checks** (when `pytest-verify` is installed).
3. **Session Logs** — hierarchical session-scoped logger entries with search and level filters.
4. **Report** — run metadata (duration, exit code, Python/pytest versions, command line, full `pytest.log`).

Tables logged via `log.table()` appear inline in the chronological log position **and** as full HTML artifacts in the Artifacts tab.

---

## Optional integration: `pytest-verify`

If [`pytest-verify`](https://pypi.org/project/pytest-verify/) is installed, the reporter automatically picks up its check results and renders them as **verification cards** in the HTML dashboard (green for passed, red for failed) — both inline in the Procedure view and as a dedicated **Checks** sub-tab.

```bash
pip install "pytest-reporter[verify]"
```

`pytest-reporter` never evaluates checks itself; it only observes and renders them.

---

## Project layout

```
src/pytest_reporter/
├── __init__.py             # Public API (step, substep, exceptions)
├── plugin.py               # Hooks, fixtures, CLI options
├── reporter.py             # Orchestrator
├── _logger.py              # Hierarchical Logger + table()
├── _procedure.py           # step/substep tracking
├── _collector.py           # Test indexing, run IDs, parametrization
├── _context.py             # Path/timestamp management
├── _json_writer.py         # Phase / parameters / aggregate writers
├── _junit_writer.py        # JUnit XML
├── _html_builder.py        # Self-contained HTML dashboard
├── _table.py               # DataFrame normalization + HTML artifacts
├── _console_capture.py     # pytest.log tee
├── _symlinks.py            # 01_latest/ hard-copy refresh
├── _types.py               # TypedDicts and dataclasses
└── py.typed
```

---

## Development

```bash
# Setup
uv pip install -e ".[dev,verify]"

# Run unit tests
pytest tests/

# Run the example suite (generates a real report under examples/reports/)
cd examples && pytest --report-dir=reports

# Lint + type-check
ruff check src/ tests/
ruff format src/ tests/
mypy --strict src/pytest_reporter/
```

The example suite under `examples/tests/` is also a showcase of every feature — hardware verification, data analysis, database queries, UI snapshots — and produces a fully populated `report.html`.

---

## License

MIT — see [LICENSE](LICENSE).
