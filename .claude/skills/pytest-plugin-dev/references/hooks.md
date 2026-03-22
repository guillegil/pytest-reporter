# Pytest Hook Reference — Complete Lifecycle Guide

All hooks are listed in the **order they are called** during a normal pytest run.
Each entry shows the full signature, pluggy behaviour flags, available parameters,
what to return, and the most common plugin use cases.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| 🔂 | `firstresult=True` — stops at first non-`None` return; remaining impls skipped |
| 📣 | `historic=True` — replayed to late-registering plugins; incompatible with wrappers |
| ⚠️ | Raising exceptions here will abort the pytest run (outside `pytest_runtest_*`) |
| `wrapper=True` | Generator hook — `yield` to call inner chain, inspect result after |

---

## Phase 1 — Bootstrap & Startup

Called once, very early, before any user code or conftest files are parsed.
Only available to **built-in and third-party entry-point plugins** (not conftest).

---

### `pytest_load_initial_conftests`
```python
def pytest_load_initial_conftests(
    early_config: pytest.Config,
    parser: pytest.Parser,
    args: list[str],
) -> None: ...
```
Loads the initial `conftest.py` files before command-line options are parsed.
Use to register plugins or perform setup that must happen before any
configuration is read.

> **Only available to plugins registered via `pytest11` entry point.**
> Conftest files cannot implement this hook.

---

### `pytest_cmdline_preparse` *(deprecated)*
```python
def pytest_cmdline_preparse(
    config: pytest.Config,
    args: list[str],
) -> None: ...
```
Called before command-line arguments are parsed. Use to inject or rewrite
`args` before option parsing. Prefer `pytest_load_initial_conftests` for
new code.

---

### `pytest_cmdline_parse` 🔂
```python
def pytest_cmdline_parse(
    pluginmanager: pytest.PytestPluginManager,
    args: list[str],
) -> pytest.Config | None: ...
```
Return an initialised `Config` object. The default implementation does the
full option-parsing work. Rarely overridden; only useful for fully custom
runner integrations.

---

### `pytest_addoption` 📣
```python
def pytest_addoption(
    parser: pytest.Parser,
    pluginmanager: pytest.PytestPluginManager,
) -> None: ...
```
Register CLI options and `pyproject.toml` / `pytest.ini` values.
Called once at the very start of a test run.

```python
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--myopt", action="store_true", default=False)
    parser.addini("myini_key", default="value", help="...")
```

Access later via `config.getoption("--myopt")` or `config.getini("myini_key")`.

> **Must be implemented only in plugins or root-level `conftest.py`.**
> Options registered here are available to all hooks that receive `config`.

---

### `pytest_plugin_registered` 📣
```python
def pytest_plugin_registered(
    plugin: object,
    plugin_name: str,
    manager: pytest.PytestPluginManager,
) -> None: ...
```
Fired every time a new plugin is registered. Because it is `historic`, it is
also replayed immediately to any plugin that registers late. Useful for
inter-plugin coordination (e.g. checking whether `pytest-xdist` is active).

---

### `pytest_addhooks`
```python
def pytest_addhooks(
    pluginmanager: pytest.PytestPluginManager,
) -> None: ...
```
Called at plugin registration time so the plugin can declare **new hook
specifications** for other plugins to implement.

```python
def pytest_addhooks(pluginmanager: pytest.PytestPluginManager) -> None:
    from . import newhooks
    pluginmanager.add_hookspecs(newhooks)
```

---

## Phase 2 — Configuration

Called after command-line parsing, once per plugin and once per conftest file
as each is imported.

---

### `pytest_configure`
```python
def pytest_configure(config: pytest.Config) -> None: ...
```
Called after command-line options have been parsed and all plugins and initial
conftest files been loaded. The primary hook for:

- Registering custom markers (`config.addinivalue_line(...)`)
- Conditionally registering sub-plugins (`config.pluginmanager.register(...)`)
- Reading config values and storing them for later use

```python
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: mark test as slow")
    if config.getoption("--my-flag", default=False):
        config.pluginmanager.register(MySubPlugin(config), "my_sub")
```

---

### `pytest_sessionstart`
```python
def pytest_sessionstart(session: pytest.Session) -> None: ...
```
Called after the `Session` object has been created but **before** collection
starts. Use for session-wide resource setup (e.g. opening a database
connection, starting a server).

---

## Phase 3 — Collection

Pytest walks the filesystem and builds the tree of `Item` nodes.
Hooks are called depth-first as each directory and file is visited.

---

### `pytest_collection` 🔂
```python
def pytest_collection(session: pytest.Session) -> object | None: ...
```
Top-level hook that drives the entire collection phase. The default
implementation calls all the lower-level collection hooks below.
Override only if you need to replace the entire collection mechanism.

---

### `pytest_ignore_collect` 🔂
```python
def pytest_ignore_collect(
    collection_path: pathlib.Path,
    config: pytest.Config,
) -> bool | None: ...
```
Return `True` to prevent a path (file or directory) from being collected at
all. Called before any collector is created for the path.

```python
def pytest_ignore_collect(collection_path: pathlib.Path) -> bool | None:
    if collection_path.name.startswith("_generated"):
        return True
    return None
```

---

### `pytest_collect_directory` 🔂
```python
def pytest_collect_directory(
    path: pathlib.Path,
    parent: pytest.Collector,
) -> pytest.Collector | None: ...
```
Return a custom `Collector` for a directory, or `None` to use the default
`Dir` collector.

---

### `pytest_collect_file` 🔂
```python
def pytest_collect_file(
    file_path: pathlib.Path,
    parent: pytest.Collector,
) -> pytest.Collector | None: ...
```
Return a `Collector` for a file, or `None` to skip it. This is the primary
hook for **custom file type collectors** (YAML, JSON, SQL, etc.).

```python
def pytest_collect_file(
    file_path: pathlib.Path, parent: pytest.Collector
) -> pytest.Collector | None:
    if file_path.suffix == ".yaml" and file_path.name.startswith("test_"):
        return YamlFile.from_parent(parent, path=file_path)
    return None
```

---

### `pytest_pycollect_makemodule` 🔂
```python
def pytest_pycollect_makemodule(
    module_path: pathlib.Path,
    parent: pytest.Collector,
) -> pytest.Module | None: ...
```
Return a custom `Module` collector for a `.py` test file, or `None` for the
default. Use to wrap or subclass `pytest.Module`.

---

### `pytest_collectstart`
```python
def pytest_collectstart(collector: pytest.Collector) -> None: ...
```
Called when a collector starts collecting. Fired for every `Dir`, `Module`,
`Class`, etc. as recursion descends.

---

### `pytest_pycollect_makeitem` 🔂
```python
def pytest_pycollect_makeitem(
    collector: pytest.Module | pytest.Class,
    name: str,
    obj: object,
) -> pytest.Item | pytest.Collector | list[...] | None: ...
```
Called for each Python object found in a module. Return a custom `Item` or
`Collector`, or `None` to use the default.

---

### `pytest_generate_tests`
```python
def pytest_generate_tests(metafunc: pytest.Metafunc) -> None: ...
```
Called once per test function during collection to inject parametrization.
Unlike most hooks, this one is **also** discovered inside test modules and
test classes (not only in plugins and conftest).

```python
def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "env" in metafunc.fixturenames:
        metafunc.parametrize("env", ["staging", "production"])
```

---

### `pytest_make_parametrize_id` 🔂
```python
def pytest_make_parametrize_id(
    config: pytest.Config,
    val: object,
    argname: str,
) -> str | None: ...
```
Return a human-readable string ID for a parametrize value, or `None` to use
the default `repr`-based ID.

---

### `pytest_itemcollected`
```python
def pytest_itemcollected(item: pytest.Item) -> None: ...
```
Called immediately after a single `Item` is collected. Use to annotate items
(e.g. attach custom attributes) as soon as they appear.

---

### `pytest_collectreport`
```python
def pytest_collectreport(report: pytest.CollectReport) -> None: ...
```
Called after a collector finishes collecting (success or error). Receives the
`CollectReport` which includes any collection errors.

---

### `pytest_collection_modifyitems`
```python
def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None: ...
```
Called after the **entire** collection phase is done. Mutate `items` in-place
to filter, reorder, or deselect tests.

```python
@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    items[:] = sorted(items, key=lambda i: i.get_closest_marker("slow") is None)
    # fast tests first; slow tests last
```

> **Critical:** always use `items[:] = new_list`, never `items = new_list`.

---

### `pytest_collection_finish`
```python
def pytest_collection_finish(session: pytest.Session) -> None: ...
```
Called after collection is complete and `items` have been modified.
The final list of items is available on `session.items`.
Use for post-collection reporting (e.g. printing a summary of what will run).

---

### `pytest_deselected`
```python
def pytest_deselected(items: Sequence[pytest.Item]) -> None: ...
```
Called when items are deselected (via `-k`, `-m`, or
`pytest_collection_modifyitems`). May be called multiple times.

---

## Phase 4 — Test Execution

Called once per test item. The execution of each test follows a strict
**setup → call → teardown** protocol.

---

### `pytest_runtestloop` 🔂
```python
def pytest_runtestloop(session: pytest.Session) -> object | None: ...
```
Drives the loop over all collected items. The default implementation calls
`pytest_runtest_protocol` for each item. Override only to replace the entire
run loop (e.g. for parallel execution).

---

### `pytest_runtest_protocol` 🔂
```python
def pytest_runtest_protocol(
    item: pytest.Item,
    nextitem: pytest.Item | None,
) -> object | None: ...
```
Drives setup → call → teardown for a single item. `nextitem` is the next
test to run (or `None` if this is the last). The default calls the three
`pytest_runtest_logstart` / `pytest_runtest_setup` / etc. hooks in order.

---

### `pytest_runtest_logstart`
```python
def pytest_runtest_logstart(
    nodeid: str,
    location: tuple[str, int | None, str],
) -> None: ...
```
Called at the very start of running the runtest protocol for an item.
`location` is `(filename, lineno, testname)`.

---

### `pytest_runtest_setup`
```python
def pytest_runtest_setup(item: pytest.Item) -> None: ...
```
Called to perform the **setup** phase for a test item. This is where pytest
resolves and runs all fixtures with `autouse=True` or requested by the test.

> Raising here marks the test as `ERROR` (not `FAILED`).

---

### `pytest_runtest_call`
```python
def pytest_runtest_call(item: pytest.Item) -> None: ...
```
Called to **execute** the test function. The default calls `item.runtest()`.
Use a wrapper here to add retry logic, timing, or exception transformation.

```python
@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Generator[None, None, None]:
    start = time.perf_counter()
    try:
        yield   # run the test
    finally:
        item._duration = time.perf_counter() - start
```

---

### `pytest_runtest_teardown`
```python
def pytest_runtest_teardown(
    item: pytest.Item,
    nextitem: pytest.Item | None,
) -> None: ...
```
Called to perform the **teardown** phase. Fixtures are finalized here.
`nextitem` allows teardown to defer cleanup if the next test shares a
higher-scoped fixture.

---

### `pytest_runtest_makereport` 🔂
```python
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[None],
) -> pytest.TestReport | None: ...
```
Called after each phase (setup / call / teardown) to create the
`TestReport` object. Use a `wrapper=True` implementation to post-process
or enrich reports before they are passed to logging hooks.

```python
@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[None],
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if report.when == "call" and report.failed:
        report.extra_info = item.funcargs.get("request").node.name
    return report
```

---

### `pytest_runtest_logreport`
```python
def pytest_runtest_logreport(report: pytest.TestReport) -> None: ...
```
Called with the `TestReport` produced by `pytest_runtest_makereport` for
each phase. This is the primary hook for **custom reporters**.

Key `report` attributes:
- `report.nodeid` — unique test ID
- `report.when` — `"setup"` / `"call"` / `"teardown"`
- `report.outcome` — `"passed"` / `"failed"` / `"skipped"`
- `report.duration` — float seconds
- `report.longrepr` — failure detail (string or `ReprExceptionInfo`)

---

### `pytest_runtest_logfinish`
```python
def pytest_runtest_logfinish(
    nodeid: str,
    location: tuple[str, int | None, str],
) -> None: ...
```
Called at the end of running the runtest protocol for an item. Symmetric
counterpart to `pytest_runtest_logstart`.

---

## Phase 5 — Exception & Warning Handling

These hooks fire as side-effects during collection or execution.

---

### `pytest_exception_interact`
```python
def pytest_exception_interact(
    node: pytest.Item | pytest.Collector,
    call: pytest.CallInfo[Any],
    report: pytest.TestReport | pytest.CollectReport,
) -> None: ...
```
Called when an exception was raised that is **not** an internal skip/xfail.
Use for custom interactive debugging, screenshot capture, or logging.

---

### `pytest_internalerror`
```python
def pytest_internalerror(
    excrepr: pytest.ExceptionRepr,
    excinfo: pytest.ExceptionInfo[BaseException],
) -> bool | None: ...
```
Called for internal pytest errors (bugs in pytest itself or plugins).
Return `True` to suppress the default traceback output.

---

### `pytest_warning_recorded`
```python
def pytest_warning_recorded(
    warning_message: warnings.WarningMessage,
    when: str,
    nodeid: str,
    location: tuple[str, int, str] | None,
) -> None: ...
```
Called when a warning is captured by pytest's warning plugin.
`when` is `"config"`, `"collect"`, `"runtest"`, or `"env"`.

---

### `pytest_keyboard_interrupt`
```python
def pytest_keyboard_interrupt(
    excinfo: pytest.ExceptionInfo[KeyboardInterrupt],
) -> None: ...
```
Called when `KeyboardInterrupt` is raised (Ctrl-C). Use to flush buffers,
close connections, or emit a partial report before exit.

---

## Phase 6 — Reporting & Session Finish

Called after all tests have run.

---

### `pytest_terminal_summary`
```python
def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: pytest.ExitCode,
    config: pytest.Config,
) -> None: ...
```
Called to add a section to the terminal summary at the end of the run.
The primary hook for appending custom output after the standard summary.

```python
def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: pytest.ExitCode,
) -> None:
    terminalreporter.write_sep("=", "My Plugin Summary")
    terminalreporter.write_line("All done.")
```

---

### `pytest_sessionfinish`
```python
def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: pytest.ExitCode | int,
) -> None: ...
```
Called after the entire test run has finished and `exitstatus` is known.
Use to flush file reporters, close connections, or emit final metrics.

> Use `@pytest.hookimpl(trylast=True)` here so you run after built-in
> finalization that other plugins (like `pytest-cov`) depend on.

---

### `pytest_unconfigure`
```python
def pytest_unconfigure(config: pytest.Config) -> None: ...
```
Called before pytest exits — the counterpart to `pytest_configure`.
Runs even if the session errored. Use to deregister sub-plugins or clean up
global state.

---

## Phase 7 — Fixture Lifecycle Hooks

These fire as part of fixture resolution, not the main hook call chain.

---

### `pytest_fixture_setup` 🔂
```python
def pytest_fixture_setup(
    fixturedef: pytest.FixtureDef[Any],
    request: pytest.FixtureRequest,
) -> object | None: ...
```
Called just before a fixture function is executed. Return a value to skip the
actual fixture function and use the return value instead. Rarely overridden.

---

### `pytest_fixture_post_use`
```python
def pytest_fixture_post_use(
    fixturedef: pytest.FixtureDef[Any],
    request: pytest.FixtureRequest,
) -> None: ...
```
Called after a fixture is used and its finalizers have run.

> **Requires pytest ≥ 8.1.** Not available on older versions.

---

## Lifecycle Timeline (condensed)

```
pytest invoked
│
├─ BOOTSTRAP
│   ├── pytest_load_initial_conftests
│   ├── pytest_cmdline_parse          🔂
│   ├── pytest_addoption              📣
│   └── pytest_plugin_registered      📣  (fires per plugin, throughout run)
│
├─ CONFIGURATION
│   ├── pytest_configure              (per plugin + per conftest)
│   └── pytest_sessionstart
│
├─ COLLECTION
│   ├── pytest_collection             🔂  (top-level driver)
│   │   ├── pytest_ignore_collect     🔂  (per path)
│   │   ├── pytest_collect_directory  🔂  (per dir)
│   │   ├── pytest_collect_file       🔂  (per file)
│   │   ├── pytest_collectstart            (per collector)
│   │   ├── pytest_pycollect_makemodule 🔂
│   │   ├── pytest_pycollect_makeitem  🔂 (per Python object)
│   │   ├── pytest_generate_tests          (per test function)
│   │   ├── pytest_make_parametrize_id 🔂 (per param value)
│   │   ├── pytest_itemcollected           (per item)
│   │   └── pytest_collectreport           (per collector, after done)
│   ├── pytest_collection_modifyitems      (once, all items)
│   ├── pytest_deselected                  (for deselected items)
│   └── pytest_collection_finish
│
├─ EXECUTION  (repeated per Item)
│   ├── pytest_runtest_protocol       🔂
│   │   ├── pytest_runtest_logstart
│   │   │
│   │   ├── [SETUP phase]
│   │   │   ├── pytest_runtest_setup
│   │   │   │   └── pytest_fixture_setup 🔂 (per fixture)
│   │   │   ├── pytest_runtest_makereport 🔂
│   │   │   └── pytest_runtest_logreport
│   │   │
│   │   ├── [CALL phase]
│   │   │   ├── pytest_runtest_call
│   │   │   ├── pytest_runtest_makereport 🔂
│   │   │   └── pytest_runtest_logreport
│   │   │       └── pytest_exception_interact  (if exception)
│   │   │
│   │   ├── [TEARDOWN phase]
│   │   │   ├── pytest_runtest_teardown
│   │   │   │   └── pytest_fixture_post_use  (per fixture)
│   │   │   ├── pytest_runtest_makereport 🔂
│   │   │   └── pytest_runtest_logreport
│   │   │
│   │   └── pytest_runtest_logfinish
│   │
│   └── pytest_warning_recorded            (whenever a warning fires)
│
└─ SHUTDOWN
    ├── pytest_terminal_summary
    ├── pytest_sessionfinish
    └── pytest_unconfigure
```

---

## Quick-Reference: Hook → Common Use Cases

| Hook | Common plugin use cases |
|------|------------------------|
| `pytest_addoption` | Add `--my-flag`, ini keys |
| `pytest_configure` | Register markers, sub-plugins |
| `pytest_sessionstart` | Open DB / server |
| `pytest_collect_file` | Custom file type collectors |
| `pytest_generate_tests` | Dynamic parametrization from external data |
| `pytest_collection_modifyitems` | Filter, reorder, tag tests |
| `pytest_runtest_setup` | Per-test resource injection outside fixtures |
| `pytest_runtest_call` | Retry logic, timeout enforcement |
| `pytest_runtest_makereport` | Enrich reports (add screenshots, logs) |
| `pytest_runtest_logreport` | Write to file reporters, metrics |
| `pytest_exception_interact` | Capture screenshot on failure |
| `pytest_terminal_summary` | Append custom section to output |
| `pytest_sessionfinish` | Flush file reporters, emit metrics |
| `pytest_unconfigure` | Teardown global state |
| `pytest_warning_recorded` | Escalate or suppress specific warnings |
