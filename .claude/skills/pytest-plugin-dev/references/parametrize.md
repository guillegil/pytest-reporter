# Parametrize Extensions

## The three extension points

| Hook | What it controls |
|---|---|
| `pytest_generate_tests` | Inject parametrize calls at collection time |
| `pytest_make_parametrize_id` | Customize the string ID for each parameter set |
| `pytest_collection_modifyitems` | Filter / re-order already-collected parametrized items |

---

## `pytest_generate_tests` — dynamic parametrization

This hook fires once per test function during collection. You receive a
`Metafunc` object that lets you introspect fixtures and markers, then call
`metafunc.parametrize()` to inject parameter sets.

```python
# src/pytest_myplugin/parametrize.py
from __future__ import annotations
from typing import TYPE_CHECKING
import pytest

if TYPE_CHECKING:
    from pytest import Metafunc


def pytest_generate_tests(metafunc: Metafunc) -> None:
    """Drive parametrization from a custom marker."""
    marker = metafunc.definition.get_closest_marker("load_cases")
    if marker is None:
        return

    source: str = marker.kwargs.get("from", "cases.yaml")
    cases = _load_cases(source)           # your loader

    # parametrize only if the function requests the fixture
    if "case" in metafunc.fixturenames:
        metafunc.parametrize(
            "case",
            cases,
            ids=[c["name"] for c in cases],
            indirect=False,               # True = pass through a fixture
        )


def _load_cases(path: str) -> list[dict[str, object]]:
    import yaml
    from pathlib import Path
    return yaml.safe_load(Path(path).read_text())
```

Usage in a test file:
```python
@pytest.mark.load_cases(from="tests/fixtures/auth_cases.yaml")
def test_auth(case: dict[str, object]) -> None:
    assert authenticate(case["user"], case["password"]) == case["expected"]
```

---

## `pytest_make_parametrize_id` — custom test IDs

Called for each parameter value. Return a string to override the default
`repr`-based ID, or `None` to leave it to pytest.

```python
def pytest_make_parametrize_id(
    config: pytest.Config,
    val: object,
    argname: str,
) -> str | None:
    # Give dataclass instances a clean ID
    if hasattr(val, "__dataclass_fields__"):
        fields = val.__dataclass_fields__  # type: ignore[union-attr]
        key_field = next(iter(fields))     # use first field as ID
        return f"{type(val).__name__}({getattr(val, key_field)!r})"
    return None   # fall through to default
```

---

## `pytest_collection_modifyitems` — post-collection filtering

Called once after all items are collected. Use it to reorder, deselect, or
annotate items.

```python
@pytest.hookimpl(trylast=True)  # run after all other modifiers
def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if not config.getoption("--prioritize-slow", default=False):
        return

    slow: list[pytest.Item] = []
    fast: list[pytest.Item] = []

    for item in items:
        if item.get_closest_marker("slow"):
            slow.append(item)
        else:
            fast.append(item)

    items[:] = fast + slow   # mutate in-place — do NOT reassign
```

> **Critical:** always mutate `items` in-place with `items[:] = ...`.
> Reassigning `items = [...]` has no effect outside the function.

---

## Indirect parametrization pattern

Use `indirect=True` when parameter values need setup/teardown (they are
passed through a fixture before the test sees them):

```python
# In the plugin
metafunc.parametrize("db_config", configs, indirect=True)

# In conftest.py of the project using the plugin
@pytest.fixture
def db_config(request: pytest.FixtureRequest) -> Generator[Database, None, None]:
    config = request.param                # the raw value from parametrize
    db = Database.connect(config)
    yield db
    db.close()
```

---

## Architecture tip: separate data loading from hook logic

```
pytest_myplugin/
├── parametrize.py      # hook implementations only
└── loaders/
    ├── __init__.py
    ├── yaml_loader.py  # load from YAML
    ├── csv_loader.py   # load from CSV
    └── base.py         # Protocol / ABC for loaders
```

Define a `CaseLoader` Protocol so you can swap data sources without changing
hook code:

```python
# loaders/base.py
from typing import Protocol

class CaseLoader(Protocol):
    def load(self, source: str) -> list[dict[str, object]]: ...
```
