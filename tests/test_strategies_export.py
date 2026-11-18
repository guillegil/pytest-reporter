"""The run export of pytest-strategies (4.3+) in the report.

pytest-strategies writes ``strategies.json`` and ``strategies.vectors.json``
into the folder its ``pytest_strategies_export_dir`` hook (or its option, or
its ini setting) names. With ``--report-dir`` the reporter answers that hook
with the run folder when nobody else chose one, reads the vectors file at
session end and shows each test's strategies and rows on a Strategy tab.

The reporter never imports pytest-strategies, so most tests here use a small
stand-in plugin that asks the hook and writes the files as pytest-strategies
does. The last ones run the real plugin and skip without 4.3.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter._html_builder._js import JS
from pytest_reporter._strategies import StrategyExport, html_data

if TYPE_CHECKING:
    from pytest import Pytester

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _strategies_has_run_export() -> bool:
    if importlib.util.find_spec("pytest_strategy") is None:
        return False
    return importlib.util.find_spec("pytest_strategy._run_export") is not None


requires_run_export = pytest.mark.skipif(
    not _strategies_has_run_export(), reason="pytest-strategies 4.3+ is not installed"
)


def _document(test: str = "test_rw.py::test_rw") -> dict[str, Any]:
    """A ``strategies.vectors.json`` as pytest-strategies 4.3 writes it."""

    def row(
        row_id: str, kind: str, channel: int, wdata: int, outcome: str | None
    ) -> dict[str, Any]:
        return {
            "id": row_id,
            "kind": kind,
            "name": row_id.removeprefix("directed-") if kind == "directed" else None,
            "index": 0,
            "enumerated": ["channel"] if kind == "exhaustive" else [],
            "values": {"channel": channel, "wdata": wdata},
            "items": [{"nodeid": f"{test}[{row_id}]", "outcome": outcome}],
            "later": "a key of a later schema",
        }

    return {
        "schema": 1,
        "kind": "strategy_vectors",
        "generator": {"name": "pytest-strategies", "version": "4.3.0"},
        "seed": 1,
        "nsamples": 10,
        "tests": [
            {
                "nodeid": test,
                "strategies": [
                    {
                        "name": "rw",
                        "origin": {
                            "folder": "",
                            "file": "strategies.py",
                            "qualname": "rw",
                            "line": 4,
                        },
                        "arguments": {"device": "bpam", "width": 16},
                        "context": "976bcfdf",
                        "nsamples": {"value": "auto", "source": "Parameter(nsamples=, pinned)"},
                        "parameter": {
                            "schema": 1,
                            "arguments": [
                                {
                                    "name": "channel",
                                    "description": "Register channel",
                                    "python_type": "int",
                                    "source": "rng",
                                    "rng": {
                                        "type": "Series",
                                        "sequence": [0, 1],
                                        "skip_if_empty": None,
                                    },
                                },
                                {
                                    "name": "wdata",
                                    "description": "",
                                    "python_type": "int",
                                    "source": "rng",
                                    "rng": {
                                        "type": "RNGInteger",
                                        "min": 0,
                                        "max": 255,
                                        "predicate": False,
                                    },
                                },
                                {
                                    "name": "mode",
                                    "python_type": "str",
                                    "source": "value",
                                    "value": "x",
                                },
                            ],
                            "directed_vectors": [
                                {
                                    "name": "zeros",
                                    "id": "directed-zeros",
                                    "values": {"channel": 0, "wdata": 0},
                                }
                            ],
                            "test_vectors": [
                                {
                                    "name": "smoke",
                                    "id": "test-smoke",
                                    "values": {"channel": 1, "wdata": 1},
                                }
                            ],
                            "constraints": [
                                {"name": "aligned", "enabled": True},
                                {"name": "small", "enabled": False},
                            ],
                            "nsamples": "auto",
                            "pin_nsamples": True,
                        },
                        "rows": [
                            row("directed-zeros", "directed", 0, 0, "passed"),
                            row("channel=0", "exhaustive", 0, 51, "failed"),
                            row("channel=1", "exhaustive", 1, 204, None),
                        ],
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


def test_html_data_groups_strategies_by_test() -> None:
    session, by_test = html_data(_document())
    assert session == {
        "generator": {"name": "pytest-strategies", "version": "4.3.0"},
        "seed": 1,
        "nsamples": 10,
        "tests": 1,
        "strategies": 1,
        "rows": 3,
        "files": ["strategies.json", "strategies.vectors.json"],
    }
    (strategy,) = by_test["test_rw.py::test_rw"]
    assert strategy["name"] == "rw"
    assert strategy["nsamples"] == {"value": "auto", "source": "Parameter(nsamples=, pinned)"}
    assert strategy["parameter"]["pin_nsamples"] is True
    assert [r["id"] for r in strategy["rows"]] == ["directed-zeros", "channel=0", "channel=1"]
    assert strategy["rows"][1] == {
        "id": "channel=0",
        "kind": "exhaustive",
        "name": None,
        "index": 0,
        "enumerated": ["channel"],
        "values": {"channel": 0, "wdata": 51},
        "items": [{"nodeid": "test_rw.py::test_rw[channel=0]", "outcome": "failed"}],
    }


def test_html_data_without_a_document_or_with_odd_entries() -> None:
    assert html_data(None) == (None, {})
    document = _document()
    document["tests"] += [
        "not a test",
        {"nodeid": 5, "strategies": []},
        {"nodeid": "t.py::test_none", "strategies": []},
        {"nodeid": "t.py::test_error", "strategies": [{"name": "boom", "error": {"type": "E"}}]},
    ]
    session, by_test = html_data(document)
    assert session is not None
    assert (session["tests"], session["strategies"], session["rows"]) == (2, 2, 3)
    assert by_test["t.py::test_error"] == [
        {
            "name": "boom",
            "origin": None,
            "arguments": None,
            "context": None,
            "nsamples": None,
            "parameter": None,
            "error": {"type": "E"},
            "rows": [],
        }
    ]
    assert "t.py::test_none" not in by_test


class _Config:
    """The parts of ``pytest.Config`` that ``StrategyExport`` reads."""

    def __init__(self, root: Path, *, option: str | None = None, **ini: object) -> None:
        self.rootpath = root / "root"
        self.invocation_params = type("P", (), {"dir": root / "cwd"})()
        self._option = option
        self._ini = {"report_strategies": True, **ini}

    def getoption(self, name: str, default: object = None) -> object:
        return self._option if name == "strategy_export" else default

    def getini(self, name: str) -> object:
        if name not in self._ini:
            raise ValueError(name)
        return self._ini[name]


def _export(tmp_path: Path, **kw: Any) -> StrategyExport:  # noqa: ANN401
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    return StrategyExport(_Config(tmp_path, **kw), run_dir)  # type: ignore[arg-type]


def test_answer_gives_the_run_folder_only_when_no_folder_is_chosen(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    export = _export(tmp_path, strategies_export_dir="")
    assert export.answer(None) == str(run_dir)
    assert export.folder() == run_dir

    hooked = _export(tmp_path, strategies_export_dir="")
    assert hooked.answer(Path("out")) == Path("out")  # another implementation chose
    assert hooked.folder() == tmp_path / "root" / "out"

    ini = _export(tmp_path, strategies_export_dir="from_ini")
    assert ini.answer(None) is None  # pytest-strategies then reads its ini option
    assert ini.folder() == tmp_path / "root" / "from_ini"

    option = _export(tmp_path, option="from_option", strategies_export_dir="from_ini")
    assert option.folder() == tmp_path / "cwd" / "from_option"  # the hook is not asked

    off = _export(tmp_path, report_strategies=False, strategies_export_dir="")
    assert off.answer(None) is None
    assert off.folder() is None

    # pytest-strategies before 4.3 (no hook call, no ini option), or not installed
    assert _export(tmp_path).folder() is None


def test_load_reads_the_run_folder(tmp_path: Path) -> None:
    export = _export(tmp_path, strategies_export_dir="")
    assert export.load(time.time()) is None  # the hook was never called
    export.answer(None)
    assert export.load(time.time()) is None  # nothing was written
    path = tmp_path / "run" / "strategies.vectors.json"
    path.write_text(json.dumps(_document()), encoding="utf-8")
    loaded = export.load(time.time() + 3600)  # the run folder is this run's: no age check
    assert loaded is not None and loaded["seed"] == 1


@pytest.mark.parametrize(
    "text",
    ["{not json", "[]", '{"kind": "strategies", "tests": []}', '{"kind": "strategy_vectors"}'],
)
def test_load_ignores_what_is_not_the_vectors_document(tmp_path: Path, text: str) -> None:
    export = _export(tmp_path, strategies_export_dir="")
    export.answer(None)
    (tmp_path / "run" / "strategies.vectors.json").write_text(text, encoding="utf-8")
    with (
        pytest.warns(UserWarning, match="unreadable") if text.startswith("{not") else _no_warning()
    ):
        assert export.load(time.time()) is None


class _no_warning:  # noqa: N801
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None


def test_load_copies_a_fresh_export_from_another_folder(tmp_path: Path) -> None:
    export = _export(tmp_path, option="out")
    folder = tmp_path / "cwd" / "out"
    folder.mkdir(parents=True)
    (folder / "strategies.json").write_text("{}", encoding="utf-8")
    (folder / "strategies.vectors.json").write_text(json.dumps(_document()), encoding="utf-8")

    # Files of an earlier session are not this run's
    stale = time.time() - 3600
    for name in ("strategies.json", "strategies.vectors.json"):
        os.utime(folder / name, (stale, stale))
    assert export.load(time.time()) is None
    assert not (tmp_path / "run" / "strategies.vectors.json").exists()

    now = time.time()
    for name in ("strategies.json", "strategies.vectors.json"):
        os.utime(folder / name, (now, now))
    assert export.load(now - 1) is not None
    assert (tmp_path / "run" / "strategies.json").read_text(encoding="utf-8") == "{}"
    assert (
        json.loads((tmp_path / "run" / "strategies.vectors.json").read_text("utf-8")) == _document()
    )


# ---------------------------------------------------------------------------
# Through pytest, with a stand-in for pytest-strategies
# ---------------------------------------------------------------------------

_STAND_IN = '''
import json
from pathlib import Path

import pytest

DOCUMENT = json.loads({document!r})


class Spec:
    @pytest.hookspec(firstresult=True)
    def pytest_strategies_export_dir(config):
        """As in pytest-strategies 4.3."""


def pytest_addhooks(pluginmanager):
    pluginmanager.add_hookspecs(Spec)


def pytest_addoption(parser):
    parser.addoption("--strategy-export", dest="strategy_export", default=None)
    parser.addini("strategies_export_dir", "", type="string", default="")


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    config = session.config
    option = config.getoption("strategy_export")
    if option:
        folder = Path(config.invocation_params.dir, option)
    else:
        hooked = config.hook.pytest_strategies_export_dir(config=config)
        ini = config.getini("strategies_export_dir")
        if hooked is not None and str(hooked) != "":
            folder = Path(config.rootpath, hooked)
        elif ini:
            folder = Path(config.rootpath, ini)
        else:
            folder = None
    config._export_folder = folder


def pytest_sessionfinish(session):
    folder = session.config._export_folder
    if folder is not None:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "strategies.json").write_text(json.dumps({{"kind": "strategy_definitions"}}))
        (folder / "strategies.vectors.json").write_text(json.dumps(DOCUMENT))
'''

_TEST = """
import pytest

@pytest.mark.parametrize("row", ["directed-zeros", "channel=0", "channel=1"])
def test_rw(row):
    assert row != "channel=0"
"""

_DATA_BLOCK = '<script type="application/json" id="report-data">'


def _run_dir(pytester: Pytester) -> Path:
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def _data(pytester: Pytester) -> dict[str, Any]:
    html = (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")
    start = html.index(_DATA_BLOCK) + len(_DATA_BLOCK)
    return json.loads(html[start : html.index("</script>", start)])  # type: ignore[no-any-return]


def _stand_in(pytester: Pytester, extra: str = "") -> None:
    pytester.makeconftest(_STAND_IN.format(document=json.dumps(_document())) + extra)
    pytester.makepyfile(test_rw=_TEST)


def _run(pytester: Pytester, *args: str) -> None:
    result = pytester.runpytest("--report-dir=reports", "-p", "no:pytest_strategy", *args)
    result.assert_outcomes(passed=2, failed=1)


def test_export_goes_to_the_run_folder(pytester: Pytester) -> None:
    _stand_in(pytester)
    _run(pytester)
    run_dir = _run_dir(pytester)
    assert (run_dir / "strategies.json").is_file()
    assert json.loads((run_dir / "strategies.vectors.json").read_text("utf-8")) == _document()
    # ... and into the copy of the latest run
    assert (pytester.path / "reports" / "01_latest" / "strategies.vectors.json").is_file()

    data = _data(pytester)
    assert data["strategies"]["generator"] == {"name": "pytest-strategies", "version": "4.3.0"}
    assert (data["strategies"]["tests"], data["strategies"]["rows"]) == (1, 3)
    (test,) = data["tests"]
    (strategy,) = test["strategies"]
    assert strategy["name"] == "rw"
    assert strategy["nsamples"]["source"] == "Parameter(nsamples=, pinned)"
    # Each row's items are this test's runs, by node ID
    nodeids = {run["nodeid"] for run in test["runs"]}
    assert {i["nodeid"] for row in strategy["rows"] for i in row["items"]} == nodeids


def test_a_folder_the_user_chose_is_kept_and_copied(pytester: Pytester) -> None:
    _stand_in(pytester)
    _run(pytester, "--strategy-export=out")
    assert (pytester.path / "out" / "strategies.vectors.json").is_file()
    run_dir = _run_dir(pytester)
    assert (run_dir / "strategies.json").is_file()
    assert (run_dir / "strategies.vectors.json").is_file()
    assert _data(pytester)["tests"][0]["strategies"][0]["name"] == "rw"


def test_another_hook_implementation_wins(pytester: Pytester) -> None:
    hook = """

def pytest_strategies_export_dir(config):
    return "hooked"
"""
    _stand_in(pytester, hook)
    _run(pytester)
    assert (pytester.path / "hooked" / "strategies.vectors.json").is_file()
    assert (_run_dir(pytester) / "strategies.vectors.json").is_file()  # copied
    assert _data(pytester)["strategies"]["rows"] == 3


def test_the_ini_option_wins(pytester: Pytester) -> None:
    _stand_in(pytester)
    pytester.makeini("[pytest]\nstrategies_export_dir = from_ini\n")
    _run(pytester)
    assert (pytester.path / "from_ini" / "strategies.vectors.json").is_file()
    assert _data(pytester)["strategies"]["rows"] == 3


def test_report_strategies_false_turns_it_off(pytester: Pytester) -> None:
    _stand_in(pytester)
    pytester.makeini("[pytest]\nreport_strategies = false\n")
    _run(pytester)
    assert not (_run_dir(pytester) / "strategies.vectors.json").exists()
    data = _data(pytester)
    assert data["strategies"] is None
    assert data["tests"][0]["strategies"] == []


def test_no_export_without_pytest_strategies(pytester: Pytester) -> None:
    pytester.makepyfile(test_rw=_TEST)
    _run(pytester)
    assert not (_run_dir(pytester) / "strategies.vectors.json").exists()
    data = _data(pytester)
    assert data["strategies"] is None
    assert data["tests"][0]["strategies"] == []


def test_an_unreadable_export_does_not_break_the_report(pytester: Pytester) -> None:
    _stand_in(pytester)
    conftest = pytester.path / "conftest.py"
    conftest.write_text(
        conftest.read_text().replace("json.dumps(DOCUMENT)", "'{not json'"), encoding="utf-8"
    )
    _run(pytester)
    assert _data(pytester)["strategies"] is None
    assert len(_data(pytester)["tests"][0]["runs"]) == 3


# ---------------------------------------------------------------------------
# The Strategy tab (Node)
# ---------------------------------------------------------------------------

_DOM = """
const window = {};
function Node(tag) { this.tag = tag; this.children = []; this.className = ''; this.attrs = {}; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = v; };
Node.prototype.addEventListener = function () {};
Node.prototype.remove = function () {};
Object.defineProperty(Node.prototype, 'textContent', {
  get() { return this.text !== undefined ? this.text
                 : this.children.map(c => c.textContent).join(''); },
  set(v) { this.text = String(v); this.children = []; },
});
const document = {
  createElement: tag => new Node(tag),
  createTextNode: text => { const n = new Node('#text'); n.text = String(text); return n; },
  createDocumentFragment: () => new Node('#fragment'),
};
function findAll(node, sel, out) {
  out = out || [];
  if (node.tag === sel || (' ' + node.className + ' ').includes(' ' + sel + ' ')) out.push(node);
  node.children.forEach(c => findAll(c, sel, out));
  return out;
}
const texts = (node, sel) => findAll(node, sel).map(n => n.textContent);
const STRATEGY_ROWS_SHOWN = 100;
function showRunDetail() {}
"""


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    end = JS.index("\nfunction ", start + 1)
    return JS[start:end]


def _node(script: str, *functions: str) -> Any:  # noqa: ANN401
    source = "\n".join([_DOM, *(_function(n) for n in functions), script])
    out = subprocess.run(
        ["node", "-"],
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


_STRATEGY_FUNCTIONS = (
    "el",
    "capitalize",
    "testStrategies",
    "strategyValue",
    "strategyDrawnFrom",
    "samplesSource",
    "samplesEl",
    "strategyOrigin",
    "strategyItemEl",
    "renderStrategyRows",
    "renderStrategy",
    "renderStrategies",
)


@requires_node
def test_strategy_tab_text() -> None:
    session, by_test = html_data(_document())
    test = {
        "strategies": by_test["test_rw.py::test_rw"],
        "runs": [
            {"nodeid": "test_rw.py::test_rw[directed-zeros]", "run_id": "01", "outcome": "passed"},
            # Passed on a retry: the report's outcome counts, not the export's "failed"
            {"nodeid": "test_rw.py::test_rw[channel=0]", "run_id": "02", "outcome": "passed"},
        ],
    }
    got = _node(
        f"const DATA = {{strategies: {json.dumps(session)}}};\n"
        f"const test = {json.dumps(test)};\n"
        "const tab = renderStrategies(test, test.runs[1]);\n"
        "const rows = findAll(findAll(tab, 'strategy-rows')[0], 'tr');\n"
        "console.log(JSON.stringify({\n"
        "  name: texts(tab, 'strategy-name'), origin: texts(tab, 'strategy-origin'),\n"
        "  info: texts(tab, 'info-label').map((l, i) => [l, texts(tab, 'info-value')[i]]),\n"
        "  pin: texts(tab, 'strategy-pin'),\n"
        "  tables: findAll(tab, 'table').map(t => findAll(t, 'tr').map(\n"
        "    tr => tr.children.map(c => c.textContent))),\n"
        "  current: rows.map(tr => tr.className),\n"
        "  chips: texts(tab, 'strategy-chip'), idle: texts(tab, 'strategy-idle'),\n"
        "  links: findAll(tab, 'strategy-item-link').length,\n"
        "}));",
        *_STRATEGY_FUNCTIONS,
    )
    assert got["name"] == ["rw"]
    assert got["origin"] == ["strategies.py:4"]
    assert got["info"] == [
        ["Samples", "autopinnedpinned by the strategy"],
        ["@strategy", 'device="bpam", width=16'],
        ["Context", "976bcfdf"],
        ["Seed", "1"],
    ]
    assert got["pin"] == ["pinned"]
    arguments, rows = got["tables"]
    assert arguments == [
        ["Name", "Type", "Drawn from", "Description"],
        ["channel", "int", "Series(sequence=[0, 1])", "Register channel"],
        ["wdata", "int", "RNGInteger(min=0, max=255)", ""],
        ["mode", "str", '"x"', ""],
    ]
    assert rows == [
        ["Row", "Kind", "channel", "wdata", "Outcome"],
        ["directed-zeros", "directed", "0", "0", "Passed01"],
        ["channel=0", "exhaustive", "0", "51", "Passed02"],
        ["channel=1", "exhaustive", "1", "204", "Not run"],
    ]
    assert got["current"] == ["", "", "current", ""]  # the header, then the rows
    assert got["chips"] == ["aligned", "small (off)"]
    assert got["idle"] == ["Defined but not run in this session: test-smoke"]
    assert got["links"] == 2  # the rows whose item is one of this test's runs


@requires_node
def test_strategy_values_and_sources() -> None:
    values = [
        None,
        True,
        "a",
        1.5,
        [1, "b"],
        {"$repr": "Addr(3)", "$type": "Addr"},
        {"$enum": "Color", "member": "RED"},
        {"$float": "nan"},
        {"other": 1},
    ]
    sources = [
        "Parameter(nsamples=, pinned)",
        "Parameter(nsamples=)",
        "--nsamples",
        "default",
        "Parameter(nsamples=, pinned), no Series/RNGSequence for auto",
        "something new",
    ]
    got = _node(
        f"console.log(JSON.stringify([{json.dumps(values)}.map(strategyValue), "
        f"{json.dumps(sources)}.map(samplesSource)]));",
        "strategyValue",
        "samplesSource",
    )
    assert got[0] == [
        "None",
        "True",
        '"a"',
        "1.5",
        '[1, "b"]',
        "Addr(3)",
        "Color.RED",
        "nan",
        '{"other":1}',
    ]
    assert got[1] == [
        "pinned by the strategy",
        "set by the strategy",
        "from --nsamples",
        "the default",
        "pinned by the strategy; no Series or RNGSequence to enumerate",
        "something new",
    ]


@requires_node
def test_tree_shows_the_tests_of_a_single_file() -> None:
    """Every test in one file: the file is the tree's only top-level row (the
    common prefix used to swallow it, leaving the tree empty)."""
    tests = [
        {"aggregate": {"file": "tests/test_rw.py", "class_name": None}, "id": "a"},
        {"aggregate": {"file": "tests/test_rw.py", "class_name": None}, "id": "b"},
    ]
    two_files = tests + [{"aggregate": {"file": "tests/test_other.py", "class_name": None}}]
    one_class = [{"aggregate": {"file": "tests/test_rw.py", "class_name": "TestRw"}}] * 2
    got = _node(
        "const top = tests => treeTopLevel(compactTree(buildTree(tests)))\n"
        "  .map(([name, node]) => [name, node.tests.length]);\n"
        f"console.log(JSON.stringify([top({json.dumps(tests)}), top({json.dumps(two_files)}), "
        f"top({json.dumps(one_class)})]));",
        "buildTree",
        "commonPrefixStrip",
        "collapseChains",
        "flagSingleFnMerges",
        "compactTree",
        "treeTopLevel",
    )
    assert got == [
        [["test_rw.py", 2]],
        [["test_rw.py", 2], ["test_other.py", 1]],
        [["TestRw", 2]],
    ]


# ---------------------------------------------------------------------------
# With pytest-strategies itself
# ---------------------------------------------------------------------------

_STRATEGIES = """
from pytest_strategy import Parameter, RNGInteger, Series, TestArg, register

@register("rw")
def rw(ctx=None, width=8):
    return Parameter(
        TestArg("channel", rng_type=Series([0, 1, 2])),
        TestArg("wdata", rng_type=RNGInteger(0, (1 << width) - 1)),
        directed_vectors={"zeros": (0, 0)},
        nsamples="auto",
        pin_nsamples=True,
    )
"""

_STRATEGY_TEST = """
from pytest_strategy import strategy

@strategy("rw", width=16)
def test_rw(channel, wdata):
    assert channel != 1

def test_plain():
    pass
"""


@requires_run_export
def test_real_export_reaches_the_report(pytester: Pytester) -> None:
    pytester.makepyfile(strategies=_STRATEGIES, test_rw=_STRATEGY_TEST)
    result = pytester.runpytest("--report-dir=reports", "--rng-seed=7", "--nsamples=50")
    result.assert_outcomes(passed=4, failed=1)
    run_dir = _run_dir(pytester)
    assert json.loads((run_dir / "strategies.json").read_text("utf-8"))["kind"] == (
        "strategy_definitions"
    )

    data = _data(pytester)
    assert data["strategies"]["seed"] == 7
    assert (data["strategies"]["tests"], data["strategies"]["rows"]) == (1, 4)
    by_name = {t["base_nodeid"]: t for t in data["tests"]}
    assert by_name["test_rw.py::test_plain"]["strategies"] == []
    test = by_name["test_rw.py::test_rw"]
    (strategy,) = test["strategies"]
    assert strategy["name"] == "rw"
    assert strategy["arguments"] == {"width": 16}
    # Pinned: --nsamples=50 does not change the count
    assert strategy["nsamples"] == {"value": "auto", "source": "Parameter(nsamples=, pinned)"}
    assert [(r["id"], r["kind"]) for r in strategy["rows"]] == [
        ("directed-zeros", "directed"),
        ("channel=0", "exhaustive"),
        ("channel=1", "exhaustive"),
        ("channel=2", "exhaustive"),
    ]
    outcomes = {run["nodeid"]: run["outcome"] for run in test["runs"]}
    for row in strategy["rows"]:
        (item,) = row["items"]
        assert item["outcome"] == outcomes[item["nodeid"]]


@requires_run_export
def test_real_export_to_a_chosen_folder(pytester: Pytester) -> None:
    pytester.makepyfile(strategies=_STRATEGIES, test_rw=_STRATEGY_TEST)
    result = pytester.runpytest("--report-dir=reports", "--strategy-export=out")
    result.assert_outcomes(passed=4, failed=1)
    assert (pytester.path / "out" / "strategies.vectors.json").is_file()
    assert (_run_dir(pytester) / "strategies.vectors.json").is_file()
    assert _data(pytester)["strategies"]["rows"] == 4
