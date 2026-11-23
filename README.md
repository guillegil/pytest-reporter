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
| 🪜 **Procedures from stepdoc** | Steps written with [stepdoc](https://github.com/guillegil/stepdoc)'s `step()` appear with timing, outcome, actions and checks; a test's docstring becomes its description, objective and acceptance criteria. |
| 🔁 **Built-in retries** | `--report-retries=N` re-runs failed tests with separate logs per attempt. |
| 📎 **Artifacts** | `report_artifacts` fixture for screenshots, CSVs, HTML — embedded as data URIs in the report. |
| 🔌 **pytest-verifier and pytest-strategies** | Verification cards for every check, with the names you give its operands; each test's strategy, the rows it ran and their outcomes. |
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
├── 01_latest/                      # Copy of the most recent run (hard links where possible)
└── runs/
    └── 2026_04_27_18_30_45/
        ├── report.html             # Open in any browser
        ├── junit.xml               # CI/CD
        ├── pytest.log              # Captured console output
        ├── session.log.json        # Session-scoped logs
        ├── stepdoc.json            # stepdoc's run record (with stepdoc installed)
        ├── strategies.json         # pytest-strategies 4.3+: each test's strategies
        ├── strategies.vectors.json # ... and the rows each test ran, with outcomes
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
| `report_strategies` | `true` | With pytest-strategies 4.3+, save its run export (`strategies.json`, `strategies.vectors.json`) in the run folder when you chose no export folder, and show it on the Strategy sub-tab. `false` leaves pytest-strategies alone. |

---

## Public API

The plugin auto-registers fixtures (no imports needed). The package exports only the logger class, `ReportLogger` (alias `Logger`), and `ReportTabs`, for type hints.

### Fixtures

| Fixture | Scope | Returns | Purpose |
|---|---|---|---|
| `log` | test | `Logger` | Structured logging during a test. |
| `session_log` | session | `Logger` | Structured logging from session-scoped fixtures. |
| `report_artifacts` | test | `pathlib.Path` | Directory to save artifacts (images, HTML, CSV, anything). |
| `report_tabs` | test | `ReportTabs` | Add [custom HTML tabs](#custom-tabs) to the test's detail. |
| `report_metadata` | session | `dict` | Mutable `{section: {label: value}}` shown in the Report tab. |
| `report_seed` | session | `dict` | Set `report_seed["value"]` to pin the RNG seed shown in Run Information. |

### Extensibility hooks

Implement these in a `conftest.py` to enrich the report (all optional):

| Hook | Purpose |
|---|---|
| `pytest_reporter_test_tabs(item, tabs)` | Add [custom HTML tabs](#custom-tabs) to each test's detail. |
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
- A switch above the steps chooses the view: **This run** (values, results and outcomes) or **Generic**, the procedure as the test is written, with names where this run's values were (`Verify tb.dev.map.block.reg<channel>.F == <wdata>`) and no results or outcomes. The choice is kept while you move between runs and tests. Checked expressions and operand names are set in monospace in both views; a check's `name=` stays in plain text.
- A check made for every item of a collection (pytest-verifier's `verify.all_satisfy`) is one line, like a loop: `Verify 'Index error clear': for each w in waveforms, w & INDEX_ERROR_BIT == 0 → 12 of 12 passed`. When items fail, the line says `2 of 12 failed` and lists only those items, each with its position and value. Open **Values of waveforms (12 items)** under the line to see what every item's check got. This needs a stepdoc that folds these checks and pytest-verifier 0.11+ for the words `w` and `waveforms`.
- Steps run by fixtures go into a **Setup** (`S1`, `S2`, …) or **Teardown** (`T1`, …) section of their own. The Procedure sub-tab shows **Setup**, **Call** and **Teardown** as tabs, each with its worst outcome and step count, and opens on the phase that failed (else on Call).
- Pre-conditions written with stepdoc's `stepdoc.precondition("System Mode A")` (a `with` block, or a decorator on a function or fixture) are a group of their own above the Setup / Call / Teardown tabs, numbered `P1`, `P2`, … whichever phase they ran in. A pre-condition the test applied itself shows its steps, actions and checks. One that a shared fixture (session, module or class scope) applied for an earlier test is a single line with the status it got then: `P1. System Mode A  already established, applied in tests/test_modes.py::test_one`; the test ID opens that test's procedure. These come first, before the test's own. A test without pre-conditions has no such group. Needs a stepdoc with `stepdoc.precondition()`.
- Checks appear in the step that made them: `assert` statements (passing ones need `enable_assertion_pass_hook = true`), `step("…", check=...)`, and every `verify.*` check of pytest-verifier, with its result (`→ got 3.31`). When the expected value is a variable, the line names it and gives this run's value: `Verify 'Readback' == <wdata> (243)`. A check made with pytest-verifier's `actual_name=` / `expected_name=` reads with those names as the test writes them, and its result names the value as this run has it: `Verify tb.dev.map.block.reg<channel>.F == wdata (243) → got tb.dev.map.block.reg3.F = 240` (see [pytest-verifier](#optional-integration-pytest-verifier)).
- Text between backticks in a step title is shown in monospace, as in Markdown: `` step("Write into `dut.reg1 = 1`") ``, or `step(f"Write into {fmt.mono(reg.path)}")` with stepdoc's `fmt.mono`.
- Actions recorded by stepdoc bridges (`stepdoc.record_action(...)`) appear as lines of the step (`dac.code = 12`, `Measure dmm.voltage → 1.65 V`).
- With `--report-retries`, each attempt has its own procedure.

### Test descriptions

A test function's docstring describes the test. With stepdoc installed, the run's
**Summary** sub-tab opens with an **About this test** block:

```python
def test_cmd_fifo_fill(esm_dev, channel, verify):
    """Fill the CMD FIFO until the TX flag sets.

    Objective:
        Confirm the FIFO accepts its full depth before it reports full.

    Acceptance criteria:
        1. The TX flag sets after exactly 500 writes.
        2. No write is lost or reported as an error.
    """
```

- The text before the first heading is the description. `Objective:` and
  `Acceptance criteria:` (also `Pass criteria:`) start the other two parts, on a line of
  their own or followed by the text (`Objective: Show that ...`).
- Acceptance criteria can be a sentence, a bullet list (`-`, `*`) or a numbered list
  (`1.`, `1)`); lists show as lists and keep your numbers. Text between backticks is shown
  in monospace.
- stepdoc reads the docstring (only the test function's own) and the reporter shows what
  stepdoc gives it: a test without a docstring, a run without stepdoc, or one where stepdoc
  does not record (`report_stepdoc = false` and no stepdoc option of your own) shows nothing
  new. The parts are also in `procedure.json` as
  `doc` (`description`, `objective`, `acceptance`).

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

## Custom tabs

A test's detail can show tabs of your own HTML, in the same row as Summary, Procedure, Checks
and Artifacts. They always come last, to the right of the report's own tabs, in the order
they were added.

Add them for every test from a `conftest.py`:

```python
def pytest_reporter_test_tabs(item, tabs):
    bench = item.funcargs.get("bench")          # fixtures are still alive here
    if bench is not None:
        tabs.add("Bench log", bench.log_html())
```

The hook runs once per test, after the test body and before its fixtures are torn down. Each
implementation is called on its own: one that raises (`pytest.skip()` and `pytest.fail()`
included) becomes a warning, costs only its own tabs and never changes the test's outcome.

A single test (or a fixture) can add its own with the `report_tabs` fixture:

```python
def test_scope(report_tabs, scope):
    report_tabs.add("Waveform", scope.capture_html())         # HTML as a string
    report_tabs.add("Eye diagram", Path("eye.html"))          # an HTML file
    report_tabs.add("Readings", df.style)                     # anything with _repr_html_()
    report_tabs.add("Plot", fig.to_html(), scripts=True)      # let its JavaScript run
```

`add(title, content, *, scripts=False, height=None)`:

| Argument | Meaning |
|---|---|
| `title` | The tab's name: at most 40 characters, not the name of one of the report's tabs, and not repeated in the same test (a `ValueError` otherwise). |
| `content` | A whole HTML document or a fragment. A fragment is shown in the report's font and colors, in light and dark; a whole document is shown as written. |
| `scripts` | JavaScript in the tab is blocked unless this is `True`. |
| `height` | The frame's height in pixels. By default the frame is as tall as its content; a page sized from its window (`height: 100vh`) has no height of its own and gets 480 pixels, so give it one. |

Each tab is shown in a sandboxed frame, so its HTML cannot read or change the report, with or
without scripts. The HTML is embedded in `report.html`, which stays one file; anything the tab
loads from the network (a charting library from a CDN, say) needs a connection when the report
is opened, so inline it for a report that works offline.

The tabs are also saved in the run folder as they are added, as `tabs/01_<title>.html` files
and a `tabs/tabs.json` list, next to the run's `artifacts/`. Each retry attempt has its own,
shown in its card on the Retries tab. Without `--report-dir` the arguments are still checked
and nothing is saved. The same goes for tests run in pytest-xdist workers (`-n`), where the
reporter is not active: their tabs are not saved and the hook is not called.

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

1. **Summary** — pass-rate hero and ratio bar (the pass rate leaves skipped tests out: passed ÷ (passed + failed + error + expected fails), where a non-strict unexpected pass counts as passed); when anything failed, a **Failures** list with the reason for each failed run and a **Copy rerun command** button; status counters that open the Tests tab filtered to that status; and configurable donut/bar chart groups.
2. **Tests** — collapsible test tree with status badges and a flaky-`↻` pill on tests that passed only after a retry. When the run has failures the tree starts on them, with the first one open. A test opens on its failing run, and a failed run starts with a strip naming the phase that failed, why, and its failed checks. The per-test detail panel shows a one-click **copy command** to run that single test, plus sub-tabs for **Summary** (the test's description from its docstring, parameters, phase logs), **Procedure**, **Artifacts**, **Retries**, **Checks** (for tests with pytest-verifier checks) and **Strategy** (for tests that use a pytest-strategies strategy).
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

### Operand names

pytest-verifier lets a test say how the operands of a check are spelled when
the code does not, as after a `getattr`:

```python
block_reg_f = getattr(tb.dev.map.block, f"reg{channel}").F
verify.equal(block_reg_f, wdata,
             actual_name=f"tb.dev.map.block.reg{channel}.F",
             expected_name="wdata")
```

The report shows each name where it helps most:

| Where | What you see |
|---|---|
| Verification card, failure strip, Failures list | This run's text: `tb.dev.map.block.reg3.F — expected wdata (243), got 240`. A check that also has a `name=` shows the name as its label and this text beside it. |
| Card body | **Actual name** and **Expected name**, each followed by `written as tb.dev.map.block.reg<channel>.F` when pytest-verifier knows the form with the variable parts. |
| Procedure tab (with stepdoc) | **Generic** view: the names as the test writes them, `Verify tb.dev.map.block.reg<channel>.F == <wdata>`. **This run** view: with a stepdoc that words checks with operand names, this run's names and values, `Verify tb.dev.map.block.reg3.F == wdata (243) → got 240`; with an earlier stepdoc, `Verify tb.dev.map.block.reg<channel>.F == wdata (243) → got tb.dev.map.block.reg3.F = 240`. A `name=` leads either: `Verify 'Stored word': …`. |

A plain string has no symbolic form, so every view shows the text you gave.
This needs a pytest-verifier version with `actual_name=` / `expected_name=`;
with an older one nothing changes.

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

### The run export (pytest-strategies 4.3+)

pytest-strategies 4.3 can write what each test's strategies were and which rows
ran (`strategies.json` and `strategies.vectors.json`). With `--report-dir` you
get both without any option:

- **The files are saved in the run folder**, next to `report.html`. If you chose
  a folder yourself (`--strategy-export=DIR`, a `pytest_strategies_export_dir`
  hook in a `conftest.py`, or the `strategies_export_dir` ini option), that
  folder is used and the two files are also copied into the run folder.
- **A test that uses a strategy has a Strategy sub-tab.** For each strategy it
  shows where it is defined, the arguments the test passed with `@strategy`,
  the context fingerprint, and the sample count with where it came from. A
  strategy with `pin_nsamples=True` is marked **pinned**. Below that: the
  arguments with their types and what they are drawn from, the constraints,
  and **every row the test ran** (directed, test, random and exhaustive) with
  its values and outcome. The row of the run on screen is highlighted, and an
  outcome opens that run. Directed and test vectors that the strategy defines
  but this session did not run are listed under the table.
- **The run's Summary** shows the sample count beside the strategy row, and the
  **Report tab** has a Strategies section: the pytest-strategies version, the
  seed, the session's `--nsamples`, and how many tests, strategies and rows the
  export holds.

Outcomes in the rows table are the report's own, so a row that passed on a
retry shows as passed. Set `report_strategies = false` in your pytest
configuration to turn this off. With pytest-strategies older than 4.3 nothing
changes.

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
├── _strategies.py          # pytest-strategies' run export (optional, via its hook and files)
├── _collector.py           # Test indexing, run IDs, parametrization, strategy rows
├── _phase_capture.py       # setup/call/teardown capture + pytest-verifier checks
├── _retry.py               # --report-retries engine
├── _context.py             # Path/timestamp management + filename sanitization
├── _json_writer.py         # Phase / parameters / aggregate writers
├── _junit_writer.py        # JUnit XML
├── _dashboard_config.py    # Summary dashboard group normalization
├── _tabs.py                # Custom HTML tabs: ReportTabs, reading them back for the report
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
