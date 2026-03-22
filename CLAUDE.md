# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A distributable pytest plugin (`pytest-reporter`) that generates JSON test reports. Activated via `--report=<path>` flag. Built with hatchling, uses src layout.

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
pytest tests/test_plugin.py::test_report_created_with_flag

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy --strict src/pytest_reporter/
```

## Architecture

- **Entry point**: `pytest11` → `pytest_reporter.plugin` (registered in `pyproject.toml`)
- **`plugin.py`**: Thin registration surface — `pytest_addoption` adds `--report`, `pytest_configure` conditionally registers the `Reporter` class as a sub-plugin (gated on flag + xdist worker check)
- **`reporter.py`**: `Reporter` class implements `pytest_runtest_logreport` (collects per-test results), `pytest_sessionfinish` (writes JSON), and `pytest_terminal_summary` (prints output path)
- **`_types.py`**: Shared `TypedDict` definitions for report data structures
- **Tests use `pytester`** — all plugin behavior is tested via subprocess isolation, never by importing plugin code directly. The `pytester` fixture is enabled in `tests/conftest.py`.

## Key Conventions

- `from __future__ import annotations` in every module; pytest types imported under `TYPE_CHECKING`
- Skipped tests are captured from the setup phase (`report.when == "setup" and report.skipped`), not the call phase
- `--import-mode=importlib` is set in `pyproject.toml` to avoid sys.path pollution
