# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A distributable pytest plugin (`pytest-reporter`) that generates structured test reports: timestamped run folders with per-test JSON logs, an HTML dashboard, JUnit XML, and convenience symlinks. Activated via `--report-dir=<path>`. Built with hatchling, uses src layout.

The authoritative spec is at `docs/specs.md`.

## Development Setup

```bash
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Commands

```bash
# Run all tests
pytest

# Run a single test
pytest tests/test_plugin.py::test_report_dir_created

# Run examples (produces reports in examples/reports/)
cd examples && pytest

# Lint + format
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy --strict src/pytest_reporter/
```

## Architecture

**Entry point**: `pytest11` → `pytest_reporter.plugin` (in `pyproject.toml`)

**Hook flow** (`plugin.py` → `reporter.py`):
- `pytest_addoption` adds `--report-dir` flag
- `pytest_configure` creates `RunContext` and conditionally registers `Reporter` (gated on flag + xdist worker check)
- `Reporter` is the orchestrator that wires pytest hooks to focused writer modules

**Data collection** (`_collector.py`):
- `pytest_collection_modifyitems` → indexes all items, assigns parametrize run IDs (01/02/default), extracts params from `item.callspec`
- `pytest_runtest_logreport` → records phase data (setup/call/teardown) per test
- Groups nodeids by base function (strip `[params]` suffix) for aggregation

**Output pipeline** (all triggered from `Reporter`):
- `_context.py` — `RunContext` manages timestamped paths (`reports/runs/YYYY_MM_DD_HH_MM_SS/`)
- `_json_writer.py` — writes phase logs immediately during run; test.log.json aggregates at session end
- `_junit_writer.py` — standard JUnit XML via `xml.etree.ElementTree`
- `_html_builder.py` — self-contained HTML with embedded JSON data, rendered by inline JS (SVG donut charts, tree navigation, 3 tabs)
- `_console_capture.py` — `TeeFile` wraps terminal reporter to capture pytest.log
- `_symlinks.py` — relative symlinks for `01_latest` and `02_latest_failures`

**Tests use `pytester`** — all plugin behavior is tested via subprocess isolation. The `pytester` fixture is enabled in `tests/conftest.py`.

## Key Conventions

- `from __future__ import annotations` in every module; pytest types imported under `TYPE_CHECKING`
- Phase logs written immediately (survive crashes); aggregates written at session end
- Parametrized tests: sequential zero-padded dirs (01/, 02/); non-parametrized: `default/`
- Skipped tests captured from setup phase (`report.when == "setup" and report.skipped`)
- HTML report has zero external dependencies — all CSS/JS inline, charts via SVG
- `--import-mode=importlib` set in `pyproject.toml`
