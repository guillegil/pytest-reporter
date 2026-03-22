# Custom Collectors & Non-Python Test Items

## When to use a custom collector

Use a custom `Collector` or `Item` subclass when you need pytest to discover
and run tests from a **non-Python source** (YAML, JSON, SQL files, etc.) or
when you need to present Python objects as test items in a non-standard way.

---

## Anatomy of the collector hierarchy

```
Session          (top-level, one per run)
└── Dir          (directory)
    └── Module   (Python .py file)
        ├── Class
        │   └── Function   (test method)
        └── Function       (test function)
```

For a custom file type you implement two classes:
- **`Collector`** subclass — knows how to find items inside a file
- **`Item`** subclass — knows how to run one test case

---

## Minimal example: YAML test files

```python
# src/pytest_myplugin/collectors.py
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
import yaml
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


class YamlFile(pytest.Collector):
    """Collect test cases from a .yaml file."""

    @classmethod
    def from_parent(  # always use from_parent, never __init__ directly
        cls,
        parent: pytest.Collector,
        *,
        path: Path,
    ) -> YamlFile:
        return super().from_parent(parent, path=path)  # type: ignore[return-value]

    def collect(self) -> Generator[pytest.Item, None, None]:
        data: list[dict[str, object]] = yaml.safe_load(self.path.read_text())
        for i, case in enumerate(data):
            yield YamlItem.from_parent(
                self,
                name=str(case.get("name", f"case_{i}")),
                spec=case,
            )


class YamlItem(pytest.Item):
    """Represents a single YAML test case."""

    def __init__(
        self,
        *,
        name: str,
        parent: pytest.Collector,
        spec: dict[str, object],
    ) -> None:
        super().__init__(name=name, parent=parent)
        self.spec = spec

    @classmethod
    def from_parent(  # type: ignore[override]
        cls,
        parent: pytest.Collector,
        *,
        name: str,
        spec: dict[str, object],
    ) -> YamlItem:
        return super().from_parent(parent, name=name, spec=spec)  # type: ignore[return-value]

    def runtest(self) -> None:
        """Execute the test case."""
        expected = self.spec["expected"]
        actual = eval(str(self.spec["expression"]))  # noqa: S307
        assert actual == expected, f"Expected {expected!r}, got {actual!r}"

    def repr_failure(
        self,
        excinfo: pytest.ExceptionInfo[BaseException],
    ) -> str:
        """Human-readable failure report."""
        return f"YAML test failed:\n  spec: {self.spec}\n  error: {excinfo.value}"

    def reportinfo(self) -> tuple[Path, int | None, str]:
        """Used in the test ID and in error output."""
        return self.path, None, f"yaml::{self.name}"
```

### Registering the collector via hook

```python
# in plugin.py
def pytest_collect_file(
    parent: pytest.Collector,
    file_path: Path,
) -> pytest.Collector | None:
    if file_path.suffix == ".yaml" and file_path.name.startswith("test_"):
        return YamlFile.from_parent(parent, path=file_path)
    return None
```

---

## Key rules

- **Always use `from_parent()`** — never call `__init__` directly on nodes.
  `from_parent` is the official factory that handles node registration.
- **`runtest()` raises on failure** — pytest interprets any unhandled exception
  as a test failure. `pytest.fail("reason")` is the idiomatic way to fail.
- **`repr_failure()` is optional** but strongly recommended for custom items —
  default tracebacks from non-Python sources are hard to read.
- **`reportinfo()`** must return `(path, lineno_or_None, title)` — the title
  is what appears in verbose output and node IDs.

---

## Custom `pytest_pycollect_makeitem`

Use this hook to intercept Python-file collection and wrap specific objects
in a custom `Item`:

```python
# firstresult: return None to let default collection proceed
@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makeitem(
    collector: pytest.Module | pytest.Class,
    name: str,
    obj: object,
) -> pytest.Item | pytest.Collector | list[pytest.Item | pytest.Collector] | None:
    if isinstance(obj, MyCustomTestClass):
        return MyCustomItem.from_parent(collector, name=name, obj=obj)
    return None   # fall through to default collection
```
