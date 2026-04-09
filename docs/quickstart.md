# Quick Start

Get a full test report in under five minutes.

## 1. Install

```bash
pip install pytest-reporter
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv pip install pytest-reporter
```

## 2. Run

Add `--report-dir` to your pytest invocation:

```bash
pytest --report-dir=reports
```

That's it. After the run completes you'll see:

```
==================================== Report ====================================
  HTML:  reports/runs/2026_04_03_14_30_00/report.html
  JUnit: reports/runs/2026_04_03_14_30_00/junit.xml
  Latest: reports/01_latest
```

Open `reports/01_latest/report.html` in a browser to view the interactive dashboard.

## 3. What you get

```
reports/
├── 01_latest              -> runs/2026_04_03_14_30_00
├── 02_latest_failures     -> runs/2026_04_03_14_30_00/failures
└── runs/
    └── 2026_04_03_14_30_00/
        ├── report.html          # Self-contained interactive report
        ├── junit.xml            # CI/CD integration
        ├── pytest.log           # Full console output
        ├── session.log.json     # Session-level structured logs
        ├── failures/            # Error logs for failed tests
        └── tests/               # Per-test structured data
```

## 4. Add structured logging

Request the `log` fixture in any test to produce structured, queryable log entries:

```python
def test_checkout(log):
    log.info("Starting checkout flow")

    api = log.child("api")
    api.info("POST /orders", data={"amount": 99.99, "currency": "USD"})
    api.info("Order created", data={"order_id": "ord_123"})

    db = log.child("db")
    db.info("Inserting order record")
```

Entries appear in phase log files (`call.log.json`) and are rendered in the HTML report with level badges, source paths, and expandable data payloads.

## 5. Add procedure steps

Import `step` and `substep` to define a numbered test procedure:

```python
from pytest_reporter import step, substep

def test_user_registration(log):
    step("Submit registration form")
    substep("Fill in email")
    substep("Fill in password")

    with step("Verify email"):
        step("Open verification link")    # becomes substep 2.1
        step("Confirm redirect")          # becomes substep 2.2

    step("Verify account is active")
```

The procedure is written to `procedure.json` and rendered in the HTML report's Procedure tab.

## 6. Enable retries

Automatically re-run failed tests:

```bash
pytest --report-dir=reports --report-retries=3
```

A test that fails on the first attempt but passes on retry is counted as **passed**. The original failure and all retry attempts are preserved in the report for investigation.

## 7. Add to pyproject.toml

Avoid typing flags every time:

```toml
[tool.pytest.ini_options]
addopts = ["--report-dir=reports", "--report-retries=2"]
```

## Next steps

- Read the full [User Guide](guide.md) for all fixtures, configuration, and report details.
