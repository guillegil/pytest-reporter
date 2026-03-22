---
name: pytest-plugin-dev
description: >
  Architecture patterns and best practices for building production-grade,
  distributable pytest plugins using modern Python. Use this skill whenever
  the user wants to create, architect, design, or publish a pytest plugin —
  even if they phrase it as "writing a pytest hook", "making a custom
  collector", "extending pytest", "building a parametrize extension",
  "creating a custom reporter", or "packaging a pytest plugin for PyPI".
  Also trigger for questions about plugin project structure, pyproject.toml
  for pytest packages, pytester usage, or setting up a virtual environment
  for pytest plugin development.
---

# Pytest Plugin Development — Architecture & Best Practices

This skill covers the full arc of building a **distributable, maintainable,
type-safe** pytest plugin: environment setup → project layout → hook
architecture → advanced extension points → testing the plugin itself →
packaging & publishing.

> **Runtime rule:** all work happens inside a virtual environment. Use `uv`
> whenever it is available on the system (`which uv`). Fall back to
> `python -m venv` + `pip` only when `uv` is absent.

---

## 1. Environment Setup (always do this first)

Every command in this skill must run inside a virtual environment.
Prefer `uv` — it is significantly faster than pip and manages both the venv
and package installs in one tool.

### 1a. Bootstrap with `uv` (preferred)

```bash
# Check availability first
which uv || echo "uv not found — see fallback below"

# Create a venv pinned to a specific Python version
uv venv .venv --python 3.12

# Activate (all subsequent commands use this env)
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# Install the plugin in editable mode with dev extras
uv pip install -e ".[dev]"

# Add a new dependency and sync lockfile
uv add some-package
uv add --dev pytest-cov
```

`uv` respects `pyproject.toml` directly — no separate `requirements.txt`
needed. Use `uv sync` to reproduce the exact environment from a lockfile
(`uv.lock`):

```bash
uv sync --extra dev        # install all dev dependencies from lockfile
```

### 1b. Fallback — stdlib venv + pip

Use this only when `uv` is not available:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 1c. Verify the environment before doing anything else

```bash
# Confirm you are inside a venv
python -c "import sys; print(sys.prefix)"

# Confirm the plugin entry point is loaded
pytest --trace-config 2>&1 | grep myplugin
```

> **Never run pytest outside the venv.** The `pytest11` entry point is only
> registered for the currently active environment's installed packages.

---

## 2. Mental Model: How Pytest Loads Plugins

Pytest's plugin system is built on **pluggy** (a generic hook-call multiplexer).
Every plugin is a Python object (module or class) that implements *hook
functions* — plain functions with names starting with `pytest_` that pluggy
discovers and calls at well-defined lifecycle points.

**Discovery order (first wins for `firstresult` hooks):**
1. Built-in plugins (`_pytest/`)
2. Third-party plugins via `pytest11` entry point (your distributable plugin)
3. `conftest.py` files (root → test directory, innermost last)
4. `-p` CLI flag / `pytest_plugins` variable in test modules

**Key principle:** your plugin should never monkey-patch pytest internals.
Always use the published hook API.

---

## 3. Canonical Project Layout

Use the **src layout** — it prevents accidental imports of the local tree
instead of the installed package, which is critical when testing the plugin
itself.

```
pytest-myplugin/
├── pyproject.toml          # single source of truth for build, deps, tools
├── README.md
├── CHANGELOG.md
├── LICENSE
├── src/
│   └── pytest_myplugin/   # importable name (underscore, not hyphen)
│       ├── __init__.py     # re-export public API only
│       ├── plugin.py       # hook implementations (registered via entry point)
│       ├── fixtures.py     # fixture definitions
│       ├── collectors.py   # custom Item / Collector subclasses (if needed)
│       ├── parametrize.py  # parametrize extensions (if needed)
│       ├── reporter.py     # terminal/reporting hooks (if needed)
│       └── _types.py       # shared type aliases, TypedDicts, Protocols
└── tests/
    ├── conftest.py         # shared fixtures for the plugin's own test suite
    ├── test_plugin.py      # integration tests via pytester
    ├── test_fixtures.py
    └── test_collectors.py
```

**Naming rules:**
- PyPI package name: `pytest-myplugin` (hyphen)
- Importable module: `pytest_myplugin` (underscore)
- Entry point name: any short identifier under `pytest11`

---

## 4. pyproject.toml — Complete Template

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pytest-myplugin"
version = "0.1.0"
description = "One-line description of what this plugin does"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
dependencies = ["pytest>=7.4"]
classifiers = [
    "Framework :: Pytest",          # required for PyPI discoverability
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Typing :: Typed",
]

[project.entry-points.pytest11]
myplugin = "pytest_myplugin.plugin"   # points to the hook-impl module

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "mypy>=1.8",
    "ruff>=0.4",
    "pytest-cov>=4.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/pytest_myplugin"]

[tool.pytest.ini_options]
addopts = ["--import-mode=importlib"]   # avoids sys.path pollution
testpaths = ["tests"]

[tool.mypy]
strict = true
packages = ["pytest_myplugin"]

[tool.ruff]
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "ANN"]
```

> **`--import-mode=importlib`** is the modern default for new projects.
> It avoids the historical `sys.path` prepend behaviour that causes
> "testing local source instead of installed package" bugs.

---

## 5. Hook Implementation Architecture

### 5.1 Separate concerns into modules

Keep `plugin.py` thin — it is only the **registration surface**. Delegate to
focused modules.

```python
# src/pytest_myplugin/plugin.py
from __future__ import annotations
from typing import TYPE_CHECKING
import pytest
from .fixtures import register_fixtures   # noqa: F401 (imported for side effects)
from .reporter import ReportPlugin

if TYPE_CHECKING:
    from pytest import Config, Parser, Session

def pytest_addoption(parser: Parser) -> None:
    group = parser.getgroup("myplugin", "MyPlugin options")
    group.addoption(
        "--my-flag",
        action="store_true",
        default=False,
        help="Enable MyPlugin behaviour",
    )

def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers", "myplugin_marker: mark test as handled by myplugin"
    )
    if config.getoption("--my-flag", default=False):
        config.pluginmanager.register(ReportPlugin(config), "myplugin_reporter")
```

### 5.2 Hook ordering with `@pytest.hookimpl`

```python
@pytest.hookimpl(tryfirst=True)          # run before other implementations
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None: ...

@pytest.hookimpl(trylast=True)           # run after all others
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None: ...

@pytest.hookimpl(wrapper=True)           # wraps the entire call chain
def pytest_runtest_call(item: pytest.Item) -> Generator[None, None, None]:
    # code before
    yield                                # runs all other implementations
    # code after
```

### 5.3 Hook wrappers vs. regular hooks

| Use case | Pattern |
|---|---|
| Side-effect before/after (logging, timing) | `wrapper=True` |
| Short-circuit: return early if condition met | `firstresult=True` + `tryfirst=True` |
| Post-process results of others | `trylast=True` |
| Unconditional additional behaviour | plain `@hookimpl` |

---

## 6. Type Hints and Protocols

Modern pytest (7+) ships with full type stubs. Annotate everything.

```python
# src/pytest_myplugin/_types.py
from __future__ import annotations
from typing import Protocol, runtime_checkable
from pytest import Item, Config

@runtime_checkable
class SupportsMyProtocol(Protocol):
    """Any object that exposes the interface our plugin needs."""
    def get_plugin_data(self) -> dict[str, object]: ...

# Use TypeAlias for complex repeated types (Python 3.10+)
type ItemList = list[Item]              # Python 3.12+ syntax
# or: ItemList = list[Item]            # via __future__ annotations on 3.10/3.11
```

Always import pytest types under `TYPE_CHECKING` to avoid circular imports:

```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pytest import Session, Config, Item
```

---

## 7. Advanced Extension Points

For deep dives on each topic, read the corresponding reference file:

| Topic | Reference |
|---|---|
| **All hooks, signatures & lifecycle order** | `references/hooks.md` |
| Custom collectors & non-Python test items | `references/collectors.md` |
| `pytest_generate_tests` & parametrize extensions | `references/parametrize.md` |
| Terminal / JUnit / custom reporters | `references/reporters.md` |

---

## 8. Testing the Plugin Itself

The golden rule: **use `pytester`**, the official pytest fixture for testing
plugins. It runs pytest in an isolated subprocess with a temporary directory.

```python
# tests/test_plugin.py
from pytest import Pytester

def test_flag_activates_plugin(pytester: Pytester) -> None:
    pytester.makepyfile("""
        def test_example():
            assert 1 + 1 == 2
    """)
    result = pytester.runpytest("--my-flag", "-v")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*MyPlugin activated*"])

def test_custom_marker_registered(pytester: Pytester) -> None:
    pytester.makepyfile("""
        import pytest
        @pytest.mark.myplugin_marker
        def test_marked(): pass
    """)
    # --strict-markers would fail if marker not registered
    result = pytester.runpytest("--strict-markers")
    result.assert_outcomes(passed=1)
```

**Key `pytester` methods:**
- `pytester.makepyfile(...)` — create test files in the temp dir
- `pytester.makeconftest(...)` — create a `conftest.py`
- `pytester.makeini(...)` — create `pyproject.toml` / `pytest.ini`
- `pytester.runpytest(*args)` — run pytest, returns `RunResult`
- `result.assert_outcomes(passed=N, failed=M)` — assert counts
- `result.stdout.fnmatch_lines([...])` — assert output patterns

**Enable `pytester` in your plugin's own `conftest.py`:**
```python
# tests/conftest.py
pytest_plugins = ["pytester"]
```

---

## 9. Packaging and Publishing

```bash
# Install in editable mode during development (prefer uv)
uv pip install -e ".[dev]"
# fallback: pip install -e ".[dev]"

# Confirm plugin is discovered
pytest --trace-config | grep myplugin

# Build source distribution + wheel
uv build
# fallback: python -m build

# Publish to PyPI — uv publish handles auth natively (no twine needed)
uv publish --token "$UV_PUBLISH_TOKEN"
# fallback: python -m twine upload dist/*
```

`uv publish` reads credentials from the `UV_PUBLISH_TOKEN` environment
variable (a PyPI API token), or from `--token` on the command line. It
publishes all files in `dist/` by default. Use `--index-url` to target
TestPyPI first:

```bash
# Dry-run against TestPyPI first
uv publish --index-url https://test.pypi.org/legacy/ --token "$TEST_PYPI_TOKEN"

# Then publish to the real index
uv publish --token "$PYPI_TOKEN"
```

**Bumping the version** — since `hatchling` is used only as the build
*backend* (not Hatch the full CLI), bump the version directly in
`pyproject.toml`:

```toml
[project]
version = "0.2.0"   # ← edit this manually, or use a script / sed
```

Or add `hatch` to your dev dependencies (`uv add --dev hatch`) and use:

```bash
hatch version patch   # 0.1.0 → 0.1.1
hatch version minor   # 0.1.0 → 0.2.0
hatch version major   # 0.1.0 → 1.0.0
```

**Checklist before publishing:**
- [ ] `Framework :: Pytest` classifier in `pyproject.toml`
- [ ] `pytest11` entry point points to the correct module
- [ ] `py.typed` marker file present in `src/pytest_myplugin/` (PEP 561)
- [ ] `CHANGELOG.md` updated
- [ ] Version bumped in `pyproject.toml`
- [ ] All `pytester` integration tests pass
- [ ] `mypy --strict` passes with zero errors
- [ ] README shows minimal installation + usage example

---

## 10. Architecture Principles Summary

| Principle | What it means in practice |
|---|---|
| **Thin `plugin.py`** | Only hook registrations; delegate logic to focused modules |
| **No global state** | Store state on `config`, `session`, or `item` storeinfo, never module-level globals |
| **Respect `firstresult`** | If a hook is `firstresult`, return `None` to pass control to the next impl |
| **Use `config.workerinput` guard** | Check `hasattr(config, "workerinput")` before doing session-level work in `pytest-xdist` environments |
| **Deferred registration** | Register sub-plugins via `config.pluginmanager.register()` inside `pytest_configure`, gated on a CLI flag — don't always load everything |
| **Type everything** | Use `from __future__ import annotations`; annotate all hook signatures; run `mypy --strict` |
| **Test with `pytester`** | Never test plugin behaviour by importing it directly; always run a subprocess via `pytester` |
