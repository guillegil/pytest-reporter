# pytest-reporter

A pytest plugin that turns every test run into a self-contained, structured report — JSON logs, JUnit XML, an interactive HTML dashboard, embedded artifacts, retries, and rich tables — all generated locally with zero external dependencies beyond pytest.

[![CI](https://github.com/guillegil/pytest-reporter/actions/workflows/ci.yml/badge.svg)](https://github.com/guillegil/pytest-reporter/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

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
| 🪜 **Procedures from stepdoc** | Steps written with [stepdoc](https://github.com/guillegil/stepdoc)'s `step()` appear with timing, outcome, actions and checks. |
| 🔁 **Built-in retries** | `--report-retries=N` re-runs failed tests with separate logs per attempt. |
| 📎 **Artifacts** | `report_artifacts` fixture for screenshots, CSVs, HTML — embedded as data URIs in the report. |
| 🔌 **pytest-verifier and pytest-strategies** | Verification cards for every check; the strategy row and seed of each generated test. |
| 📦 **JUnit XML** | Standard CI/CD output, augmented with retry metadata. |
| ✅ **Typed** | Ships `py.typed`; full IDE autocompletion on every fixture. |
| 🪶 **Zero deps beyond pytest** | stepdoc, pytest-verifier, pytest-strategies and pandas are all optional; the reporter never imports them. |

---

## Installation

```bash
pip install pytest-reporter
```

Or with `uv`:

```bash
uv pip install pytest-reporter
```

The integrations are optional extras. Install the ones you use:

```bash
pip install "pytest-reporter[stepdoc]"      # procedures (step())
pip install "pytest-reporter[verifier]"     # verification cards (verify fixture)
pip install "pytest-reporter[strategies]"   # strategy rows and seeds
pip install "pytest-reporter[all]"          # all three
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
        ├── stepdoc.json            # stepdoc's run record (with stepdoc installed)
        ├── failures/               # Per-test error logs
        └── tests/                  # Per-test structured data
            └── path/to/file.py/test_function/
                ├── test.log.json   # Aggregated outcomes across runs
                └── default/        # (or 01/, 02/ for parametrized)
                    ├── procedure.json
                    ├── parameters.json
                    ├── checks.json     # pytest-verifier checks (when there are any)
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

| ini setting | Default | Description |
|---|---|---|
| `report_stepdoc` | `true` | With stepdoc installed, make it record the procedures (and save `stepdoc.json` in the run folder) when you pass no `--stepdoc-*` option. `false` leaves stepdoc alone. |

---

## Public API

The plugin auto-registers fixtures (no imports needed). The package exports only the logger class, `ReportLogger` (alias `Logger`), for type hints.

### Fixtures

| Fixture | Scope | Returns | Purpose |
|---|---|---|---|
| `log` | test | `Logger` | Structured logging during a test. |
| `session_log` | session | `Logger` | Structured logging from session-scoped fixtures. |
| `report_artifacts` | test | `pathlib.Path` | Directory to save artifacts (images, HTML, CSV, anything). |
| `report_metadata` | session | `dict` | Mutable `{section: {label: value}}` shown in the Report tab. |
| `report_seed` | session | `dict` | Set `report_seed["value"]` to pin the RNG seed shown in Run Information. |

### Extensibility hooks

Implement these in a `conftest.py` to enrich the report (all optional):

| Hook | Purpose |
|---|---|
| `pytest_reporter_metadata()` | Return `{section: {label: value}}` for the Report tab. |
| `pytest_reporter_seed()` | Return the RNG seed (`int` / `str`) shown in Run Information. |
| `pytest_reporter_dashboard()` | Configure the Summary chart groups (path, depth, style). |

The `report_metadata` / `report_seed` fixtures do the same per-session and override the hooks on collision. Without either, the seed shown is the one the [pytest-strategies](#pytest-strategies) rows were drawn from ("Not Provided" when no strategy row ran).

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

pytest-reporter has no step API of its own: write procedures with
[stepdoc](https://github.com/guillegil/stepdoc)'s `step()`, and they appear in the
**Procedure** sub-tab of every test and in `procedure.json`.

```bash
pip install "pytest-reporter[stepdoc]"
```

```python
from stepdoc import step

def test_voltage_sweep(log, verify, psu):
    with step("Enable 3.3 V output"):
        psu.enable(1, volts=3.3)

    with step("Sweep load 0–1 A"):
        for amps in (0.0, 0.25, 0.5, 1.0):
            with step(f"Load {amps} A"):
                voltage = psu.measure(1, load=amps)
                verify.approx(voltage, 3.3, abs_tol=0.05, name="CH1 voltage", units="V")
```

- Nesting `with step(...)` blocks decides the numbering (`1`, `1.1`, `1.1.1`, …). Each step has its timing, its outcome and the exception that ended it.
- Steps run by fixtures go into a **Setup** (`S1`, `S2`, …) or **Teardown** (`T1`, …) section of their own. The Procedure sub-tab shows **Setup**, **Call** and **Teardown** as tabs, each with its worst outcome and step count, and opens on the phase that failed (else on Call).
- Checks appear in the step that made them: `assert` statements (passing ones need `enable_assertion_pass_hook = true`), `step("…", check=...)`, and every `verify.*` check of pytest-verifier, with its result (`→ got 3.31`).
- Actions recorded by stepdoc bridges (`stepdoc.record_action(...)`) appear as lines of the step (`dac.code = 12`, `Measure dmm.voltage → 1.65 V`).
- With `--report-retries`, each attempt has its own procedure.

How it works: stepdoc only records when one of its output options is given. When
`--report-dir` is active and you passed none, pytest-reporter sets
`--stepdoc-record=<run>/stepdoc.json`, so stepdoc records and its run record is
kept with the report (render it later with `stepdoc render`). Your own
`--stepdoc-record`, `--stepdoc-procedure`, `--stepdoc-report` or
`--stepdoc-dry-run` are left as they are; `report_stepdoc = false` turns this
off. The reporter follows the steps through stepdoc's `pytest_stepdoc_step_*`
hooks and never imports stepdoc, so without it installed tests simply have no
procedure.

### Moving from `pytest_reporter.step` (0.2)

`step`, `substep`, `fmt` and `FormattedText` were removed in 0.3.0; importing
them raises an `ImportError` that says where they went.

| 0.2 | 0.3 with stepdoc |
|---|---|
| `from pytest_reporter import step, substep` | `from stepdoc import step` |
| `with step("Configure"): ...` | unchanged |
| `step("Load data")` followed by its code | `with step("Load data"):` around that code |
| `substep("Check limit")` inside a step | a nested `with step("Check limit"):` |
| `step("Vout", check=verify.approx(...))` | `verify.approx(...)` inside a `with step("Vout"):` (or just the call: the check lands in the enclosing step) |
| `step(fmt.text("Set ", fmt.mono("CH1"), " to 3.3 V"))` | `step("Set CH1 to 3.3 V")` |

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
- Each attempt runs with a fresh logger, and has its own procedure and verification checks.
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

1. **Summary** — pass-rate hero and ratio bar; when anything failed, a **Failures** list with the reason for each failed run and a **Copy rerun command** button; status counters that open the Tests tab filtered to that status; and configurable donut/bar chart groups.
2. **Tests** — collapsible test tree with status badges and a flaky-`↻` pill on tests that passed only after a retry. When the run has failures the tree starts on them, with the first one open. A test opens on its failing run, and a failed run starts with a strip naming the phase that failed, why, and its failed checks. The per-test detail panel shows a one-click **copy command** to run that single test, plus sub-tabs for **Summary** (parameters, phase logs), **Procedure**, **Artifacts**, **Retries**, and **Checks** (for tests with pytest-verifier checks).
3. **Session Logs** — hierarchical session-scoped logger entries with search and level filters.
4. **Report** — run metadata (human-readable timestamp, duration, exit code, Python/pytest versions, RNG seed, custom metadata, active plugins, command line, full `pytest.log`).

The report works from the keyboard and with screen readers: the test tree follows the ARIA tree pattern (arrow keys, Home/End, Enter to open), tab sets switch with the arrow keys, and outcomes are read out as text, not only shown as colour.

It also works on phones and tablets: on a phone the Tests tab shows the test list, then one test with a way back, and controls are sized for touch.

The data sits in the page as one JSON block, so even a report of several megabytes opens in about a second.

The report follows your system's light or dark setting; the button at the right of the header switches it. Printing (or saving as PDF) uses the light theme, without the navigation and the test tree.

Tables logged via `log.table()` appear inline in the chronological log position **and** as full HTML artifacts in the Artifacts tab.

---

## Optional integration: pytest-verifier

Checks made with the `verify` fixture of
[pytest-verifier](https://github.com/guillegil/pytest-verifier) appear as
**verification cards** in the **Checks** sub-tab (green for passed, red for
failed, with the result, where the check was made and its `verify.section`
titles), in the step that made them on the Procedure tab (with stepdoc), and in
each run's `checks.json`. Composite checks (`guard`, `conditional`,
`all_satisfy`, `eventually`, `stable`) show their branches or kept try.

```bash
pip install "pytest-reporter[verifier]"
```

The reporter reads the checks pytest-verifier puts on each phase report
(`report.verify_checks`), so it never imports pytest-verifier and the checks of
every retry attempt are kept with that attempt. It never evaluates checks
itself; it only observes and renders them.

## Optional integration: pytest-strategies

For tests generated by
[pytest-strategies](https://github.com/guillegil/pytest-strategies) (4.x), each
run's Summary shows its row (`dac_codes · directed zero`) and seed, and
`parameters.json` holds the row's `VectorInfo` under `strategy`. The Report tab
shows the seed the rows were drawn from, so `--rng-seed=<seed>` reproduces the
run. The reporter reads the `strategy` mark pytest-strategies puts on each test
and never imports it.

```bash
pip install "pytest-reporter[strategies]"
```

---

## Project layout

```
src/pytest_reporter/
├── __init__.py             # Public API: Logger/ReportLogger
├── plugin.py               # Hooks, fixtures, CLI options, entry point
├── _hookspecs.py           # pytest_reporter_* hook specifications
├── reporter.py             # Orchestrator
├── _report_builder.py      # Assembles the HTML data model at session end
├── _logger.py              # Hierarchical Logger + table()
├── _stepdoc.py             # Procedures from stepdoc's steps (optional, via its hooks)
├── _collector.py           # Test indexing, run IDs, parametrization, strategy rows
├── _phase_capture.py       # setup/call/teardown capture + pytest-verifier checks
├── _retry.py               # --report-retries engine
├── _context.py             # Path/timestamp management + filename sanitization
├── _json_writer.py         # Phase / parameters / aggregate writers
├── _junit_writer.py        # JUnit XML
├── _dashboard_config.py    # Summary dashboard group normalization
├── _table.py               # DataFrame normalization + HTML artifacts
├── _console_capture.py     # pytest.log tee
├── _symlinks.py            # 01_latest/ hard-copy refresh
├── _safety.py              # Crash-safety guard — the observer never breaks the run
├── _types.py               # TypedDicts and dataclasses
├── _html_builder/          # Self-contained HTML dashboard (package)
│   ├── _template.py        #   HTML skeleton + data embedding
│   ├── _css.py             #   Inline styles
│   ├── _js.py              #   Inline dashboard logic
│   └── _degraded.py        #   Minimal fallback report
└── py.typed
```

---

## Development

```bash
# Setup
uv pip install -e ".[dev,all]"   # or ".[dev]" to test without the integrations

# Run unit tests
pytest tests/

# Run the example suite (generates a real report under examples/reports/)
cd examples && pytest --report-dir=reports   # needs the [all] extras

# Lint + type-check
ruff check src/ tests/
ruff format src/ tests/
mypy --strict src/pytest_reporter/
```

The example suite under `examples/tests/` is also a showcase of every feature — hardware verification, data analysis, database queries, UI snapshots — and produces a fully populated `report.html`.

---

## License

MIT — see [LICENSE](LICENSE).
