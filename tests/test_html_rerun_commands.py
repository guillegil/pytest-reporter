"""Copy lines that run tests again with the same vectors (pytest-strategies).

pytest-strategies 4.4 adds ``rerun`` objects to its run export: unquoted
argument lists for the whole run, for one test's rows and for one row's item.
The report quotes them for a shell. With a 4.3 export (no ``rerun``) or with
the rows' ``strategy`` marks alone, it builds the commands from the node IDs
and ``--rng-seed=<seed>``; a test without strategy rows keeps its one plain
command.

The exports here are hand-built (the contract), pytest-strategies is never
needed. The JavaScript runs in Node, on the report's own functions.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter._html_builder._css import CSS
from pytest_reporter._html_builder._js import JS
from pytest_reporter._strategies import html_data, rerun_data, seed_text

if TYPE_CHECKING:
    from pytest import Pytester

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

#: A seed no JavaScript number holds: 2**53 is 9007199254740992.
BIG_SEED = 1795069805166455363
TEST = "test_rw.py::test_rw"
CWD = "/work/proj"


def _document(*, rerun: bool, seed: int = 7) -> dict[str, Any]:
    """A ``strategies.vectors.json``: of pytest-strategies 4.4 (``rerun``) or 4.3."""
    options = [f"--rng-seed={seed}", "--nsamples=4", "rw:small"]

    def row(row_id: str, outcome: str | None) -> dict[str, Any]:
        item: dict[str, Any] = {"nodeid": f"{TEST}[{row_id}]", "outcome": outcome}
        if rerun:
            item["rerun"] = {"args": [f"{TEST}[{row_id}]", *options]}
        return {
            "id": row_id,
            "kind": "random",
            "name": None,
            "index": 0,
            "enumerated": [],
            "values": {"wdata": 1},
            "items": [item],
        }

    document: dict[str, Any] = {
        "schema": 1,
        "kind": "strategy_vectors",
        "generator": {"name": "pytest-strategies", "version": "4.4.0" if rerun else "4.3.0"},
        "seed": seed,
        "nsamples": 4,
        "tests": [
            {
                "nodeid": TEST,
                "strategies": [
                    {"name": "rw", "rows": [row("rand-0", "passed"), row("rand-1", "failed")]}
                ],
            }
        ],
    }
    if rerun:
        document["rerun"] = {
            "cwd": CWD,
            "args": ["tests dir", "-k", "rw and not slow", f"--rng-seed={seed}"],
            "options": options,
        }
        document["tests"][0]["rerun"] = {"args": [TEST, *options]}
    return document


# ---------------------------------------------------------------------------
# Reading the export
# ---------------------------------------------------------------------------


def test_rerun_data_of_a_44_export() -> None:
    got = rerun_data(_document(rerun=True))
    assert got["run"] == {
        "args": ["tests dir", "-k", "rw and not slow", "--rng-seed=7"],
        "options": ["--rng-seed=7", "--nsamples=4", "rw:small"],
        "cwd": CWD,
    }
    assert got["tests"] == {TEST: {"args": [TEST, "--rng-seed=7", "--nsamples=4", "rw:small"]}}
    assert got["seed"] == "7"
    _, by_test = html_data(_document(rerun=True))
    item = by_test[TEST][0]["rows"][1]["items"][0]
    assert item == {
        "nodeid": f"{TEST}[rand-1]",
        "outcome": "failed",
        "rerun": {"args": [f"{TEST}[rand-1]", "--rng-seed=7", "--nsamples=4", "rw:small"]},
    }


def test_rerun_data_of_a_43_export_and_of_none() -> None:
    assert rerun_data(_document(rerun=False)) == {"run": None, "tests": {}, "seed": "7"}
    assert rerun_data(None) == {"run": None, "tests": {}, "seed": None}
    _, by_test = html_data(_document(rerun=False))
    assert by_test[TEST][0]["rows"][0]["items"] == [
        {"nodeid": f"{TEST}[rand-0]", "outcome": "passed"}
    ]


def test_rerun_data_keeps_arguments_as_text_and_the_note() -> None:
    document = _document(rerun=True, seed=BIG_SEED)
    # An integer among the arguments is written out exactly, never as a float
    document["rerun"]["args"] = ["--rng-seed", BIG_SEED]
    document["rerun"]["note"] = "  does not reproduce  "
    document["tests"][0]["rerun"]["note"] = "outside the rootdir"
    got = rerun_data(document)
    assert got["run"]["args"] == ["--rng-seed", str(BIG_SEED)]
    assert got["run"]["note"] == "does not reproduce"
    assert got["tests"][TEST]["note"] == "outside the rootdir"
    assert got["seed"] == str(BIG_SEED)
    assert all(isinstance(a, str) for a in got["run"]["options"])


@pytest.mark.parametrize(
    "rerun",
    [None, "pytest x", [], {}, {"args": "x"}, {"args": []}, {"args": [["x"]]}, {"args": [True]}],
)
def test_rerun_objects_of_another_shape_are_ignored(rerun: Any) -> None:  # noqa: ANN401
    document = _document(rerun=False)
    document["rerun"] = rerun
    document["tests"][0]["rerun"] = rerun
    document["tests"][0]["strategies"][0]["rows"][0]["items"][0]["rerun"] = rerun
    got = rerun_data(document)
    assert got["run"] is None
    assert got["tests"] == {}
    _, by_test = html_data(document)
    assert "rerun" not in by_test[TEST][0]["rows"][0]["items"][0]


def test_seed_text() -> None:
    assert seed_text(BIG_SEED) == str(BIG_SEED)
    assert seed_text(" 12 ") == "12"
    assert [seed_text(v) for v in (None, True, 1.5, "", [1])] == [None] * 5


# ---------------------------------------------------------------------------
# The commands (Node)
# ---------------------------------------------------------------------------

_DOM = """
function Node(tag) { this.tag = tag; this.children = []; this.className = ''; this.attrs = {}; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = v; };
Node.prototype.addEventListener = function (type) { (this.events = this.events || []).push(type); };
Object.defineProperty(Node.prototype, 'textContent', {
  get() { return this.text !== undefined ? this.text
                 : this.children.map(c => c.textContent).join(''); },
  set(v) { this.children = []; this.text = v === '' ? undefined : String(v); },
});
const document = {
  createElement: tag => new Node(tag),
  createTextNode: text => { const n = new Node('#text'); n.text = String(text); return n; },
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
function copyToClipboard() {}
function announce() {}
"""

_COMMANDS = (
    "shellQuote",
    "quoteArgs",
    "nodeCommand",
    "testCommand",
    "commandNodeid",
    "commandBaseNodeid",
    "vectorOptions",
    "plainOptions",
    "inExport",
    "exportItem",
    "hasVectors",
    "vectorCommand",
    "allVectorsCommand",
    "runAgainCommand",
    "failuresCommand",
)
_RENDERING = (
    "el",
    "capitalize",
    "commandLine",
    "setCommandLine",
    "copyButton",
    "strategyValue",
    "strategyOrigin",  # with the outcome dots that follow it
    "strategyItemEl",
    "renderStrategyRows",
)


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\nfunction ", start + 1)]


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


def _report(
    document: dict[str, Any] | None, *, marks: bool = False, seed: int = 7
) -> dict[str, Any]:
    """The report's data for one strategy test and one plain test, as the builder embeds it."""
    session, by_test = html_data(document)
    rerun = rerun_data(document)
    mark = {"strategy": "rw", "kind": "random", "seed": str(seed)} if marks else None
    run_rerun = dict(rerun["run"] or {})
    known = rerun["seed"] or (str(seed) if marks else None)
    if run_rerun or known is not None:
        run_rerun["seed"] = known
        run_rerun.setdefault("cwd", CWD)
    return {
        "cmdline": ["tests dir", "--report-dir=reports"],
        "strategies": session,
        "rerun": run_rerun or None,
        "tests": [
            {
                "base_nodeid": TEST,
                "strategies": by_test.get(TEST, []),
                "rerun": rerun["tests"].get(TEST),
                "runs": [
                    {"nodeid": f"{TEST}[rand-0]", "run_id": "01", "outcome": "passed"}
                    | {"strategy": mark},
                    {"nodeid": f"{TEST}[rand-1]", "run_id": "02", "outcome": "failed"}
                    | {"strategy": mark},
                ],
            },
            {
                "base_nodeid": "test_rw.py::test_plain",
                "strategies": [],
                "rerun": None,
                "runs": [
                    {
                        "nodeid": "test_rw.py::test_plain",
                        "run_id": "default",
                        "outcome": "failed",
                        "strategy": None,
                    }
                ],
            },
        ],
    }


_ALL = """
const [rw, plain] = DATA.tests;
console.log(JSON.stringify({
  vector: vectorCommand(rw, rw.runs[1]),
  all: allVectorsCommand(rw),
  again: runAgainCommand(),
  failures: failuresCommand([rw.runs[1], plain.runs[0]]),
  labelled: [hasVectors(rw), hasVectors(plain)],
  plain: [vectorCommand(plain, plain.runs[0]), allVectorsCommand(plain)],
}));
"""


def _commands(data: dict[str, Any]) -> dict[str, Any]:
    return _node(f"const DATA = {json.dumps(data)};\n{_ALL}", *_COMMANDS)  # type: ignore[no-any-return]


_PLAIN = [{"text": 'pytest "test_rw.py::test_plain"', "note": ""}, None]


@requires_node
@pytest.mark.parametrize(
    ("arg", "quoted"),
    [
        ("--rng-seed=1795069805166455363", "--rng-seed=1795069805166455363"),
        ("tests/test_rw.py::test_rw", "tests/test_rw.py::test_rw"),
        ("rw:small", "rw:small"),
        ("-k", "-k"),
        # [ ] are glob characters: quoted, in the double quotes cmd and PowerShell read too
        ("test_rw.py::test_rw[rand-2]", '"test_rw.py::test_rw[rand-2]"'),
        ("rw and not slow", '"rw and not slow"'),
        ("tests dir/test_a.py", '"tests dir/test_a.py"'),
        ("C:\\work\\proj", '"C:\\work\\proj"'),
        ("it's", '"it\'s"'),
        ("", '""'),
        ("a*b", '"a*b"'),
        ("a;b|c&d", '"a;b|c&d"'),
        ("~/x", '"~/x"'),
        ("=x", '"=x"'),
        ("a,b", '"a,b"'),
        # Special inside double quotes: POSIX single quotes
        ("price=$HOME", "'price=$HOME'"),
        ('say "hi"', "'say \"hi\"'"),
        ("`id`", "'`id`'"),
        ("wow!", "'wow!'"),
        ("ends\\", "'ends\\'"),
        ("a\\\\b", "'a\\\\b'"),
        ("""both ' and " $x""", """'both '\\'' and " $x'"""),
    ],
)
def test_shell_quote(arg: str, quoted: str) -> None:
    got = _node(
        f"const arg = {json.dumps(arg)};\n"
        "const got = [shellQuote(arg), quoteArgs([arg, 'x']), shellQuote(arg, true)];\n"
        "console.log(JSON.stringify(got));",
        "shellQuote",
        "quoteArgs",
    )
    always = quoted if quoted[0] in "\"'" else f'"{quoted}"'
    assert got == [quoted, f"{quoted} x", always]


@requires_node
@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_quoted_arguments_come_back_from_a_posix_shell() -> None:
    args = [
        "test_rw.py::test_rw[rand-2]",
        "a b",
        "$HOME",
        'say "hi"',
        "it's",
        "`id`",
        "ends\\",
        "a\\\\b",
        "C:\\work\\x",
        "a*b",
        "wow!",
        "",
        "~",
        "both ' and \" $x",
        "--rng-seed=1795069805166455363",
    ]
    text = _node(
        f"console.log(JSON.stringify(quoteArgs({json.dumps(args)})));", "shellQuote", "quoteArgs"
    )
    # The script goes in on stdin, as bytes: on Windows a command-line argument
    # is re-parsed (its doubled backslashes halved) before sh sees it, and text
    # mode would end the line with a carriage return
    script = f"printf '%s\\n' {text}\n".encode()
    out = subprocess.run(["sh"], input=script, capture_output=True, check=True)
    assert out.stdout.decode("utf-8").replace("\r\n", "\n").split("\n")[:-1] == args


@requires_node
def test_commands_from_a_44_export() -> None:
    got = _commands(_report(_document(rerun=True), marks=True))
    options = "--rng-seed=7 --nsamples=4 rw:small"
    assert got["vector"] == {"text": f'pytest "{TEST}[rand-1]" {options}', "note": ""}
    assert got["all"] == {"text": f"pytest {TEST} {options}", "note": ""}
    assert got["again"] == {
        "text": 'pytest "tests dir" -k "rw and not slow" --rng-seed=7',
        "note": "",
        "cwd": CWD,
    }
    assert got["failures"] == f'pytest "{TEST}[rand-1]" "test_rw.py::test_plain" {options}'
    assert got["labelled"] == [True, False]
    # A test without rows is collected under the run's options too: one line, no label
    assert got["plain"] == [
        {"text": f'pytest "test_rw.py::test_plain" {options}', "note": ""},
        None,
    ]


@requires_node
def test_an_empty_parameter_set_item_gets_the_options_it_exists_under() -> None:
    """``--vector-name=zeros`` leaves a strategy without that vector no rows.

    pytest then names the item ``[NOTSET]``; it is no row of the export and
    carries no ``strategy`` mark, and without the option it does not exist:
    ``pytest "test_rw.py::test_two[NOTSET]"`` alone ends in "not found".
    """
    document = _document(rerun=True)
    document["rerun"]["options"] = ["--rng-seed=7", "--vector-name=zeros", "-x"]
    data = _report(document)
    data["tests"][1] = {
        "base_nodeid": "test_rw.py::test_two",
        "strategies": [],
        "rerun": None,
        "runs": [
            {
                "nodeid": "test_rw.py::test_two[NOTSET]",
                "run_id": "01",
                "outcome": "skipped",
                "strategy": None,
            }
        ],
    }
    got = _commands(data)
    assert got["plain"] == [
        {
            "text": 'pytest "test_rw.py::test_two[NOTSET]" --rng-seed=7 --vector-name=zeros -x',
            "note": "",
        },
        None,
    ]


@requires_node
@pytest.mark.parametrize("rerun", [True, False])
def test_a_test_the_run_deselected_has_no_all_vectors_line(rerun: bool) -> None:
    """The export lists the tests the run selected; the report lists every collected test.

    ``-k`` left all rows of a strategy test out: there are no rows of this
    run to run again, and the function's node ID would run rows it never selected.
    """
    data = _report(_document(rerun=rerun), marks=True)
    data["tests"][0]["strategies"] = []
    data["tests"][0]["rerun"] = None
    got = _commands(data)
    assert got["labelled"] == [True, False]
    assert got["all"] is None
    # Its vector alone, under the run's options
    options = "--rng-seed=7 --nsamples=4 rw:small" if rerun else "--rng-seed=7"
    assert got["vector"]["text"] == f'pytest "{TEST}[rand-1]" {options}'


@requires_node
def test_a_note_of_the_export_goes_with_its_command() -> None:
    document = _document(rerun=True)
    document["rerun"]["note"] = "the run note"
    document["tests"][0]["rerun"]["note"] = "the test note"
    item = document["tests"][0]["strategies"][0]["rows"][1]["items"][0]
    item["rerun"] = {"args": ["-k", "test_rw and rand-1", "--rng-seed=7"], "note": "outside"}
    got = _commands(_report(document))
    assert got["vector"] == {
        "text": 'pytest -k "test_rw and rand-1" --rng-seed=7',
        "note": "outside",
    }
    assert got["all"]["note"] == "the test note"
    assert got["again"]["note"] == "the run note"


@requires_node
def test_items_without_rerun_use_the_options_of_the_export() -> None:
    document = _document(rerun=True)
    del document["tests"][0]["rerun"]
    for row in document["tests"][0]["strategies"][0]["rows"]:
        del row["items"][0]["rerun"]
    got = _commands(_report(document))
    options = "--rng-seed=7 --nsamples=4 rw:small"
    assert got["vector"]["text"] == f'pytest "{TEST}[rand-1]" {options}'
    assert got["all"]["text"] == f'pytest "{TEST}" {options}'
    assert got["plain"][0]["text"] == f'pytest "test_rw.py::test_plain" {options}'


@requires_node
@pytest.mark.parametrize("marks", [True, False])
def test_commands_from_a_43_export(marks: bool) -> None:
    """No ``rerun`` keys: the node IDs and the seed, which stays text."""
    got = _commands(_report(_document(rerun=False, seed=BIG_SEED), marks=marks, seed=BIG_SEED))
    seed = f"--rng-seed={BIG_SEED}"
    assert got["vector"] == {"text": f'pytest "{TEST}[rand-1]" {seed}', "note": ""}
    assert got["all"] == {"text": f'pytest "{TEST}" {seed}', "note": ""}
    assert got["again"] == {
        "text": f'pytest "tests dir" --report-dir=reports {seed}',
        "note": "",
        "cwd": CWD,
    }
    assert got["failures"] == f'pytest "{TEST}[rand-1]" "test_rw.py::test_plain" {seed}'
    assert got["labelled"] == [True, False]
    assert got["plain"] == _PLAIN


@requires_node
def test_commands_from_the_strategy_marks_alone() -> None:
    """pytest-strategies before 4.3 (no export): the seed of the rows' ``VectorInfo``."""
    got = _commands(_report(None, marks=True, seed=BIG_SEED))
    seed = f"--rng-seed={BIG_SEED}"
    assert got["vector"]["text"] == f'pytest "{TEST}[rand-1]" {seed}'
    assert got["all"]["text"] == f'pytest "{TEST}" {seed}'
    assert got["again"]["text"] == f'pytest "tests dir" --report-dir=reports {seed}'
    assert got["labelled"] == [True, False]
    assert got["plain"] == _PLAIN


@requires_node
def test_commands_without_pytest_strategies() -> None:
    got = _commands(_report(None))
    assert got["vector"] == {"text": f'pytest "{TEST}[rand-1]"', "note": ""}
    assert got["all"] is None
    assert got["again"] is None
    assert got["failures"] == f'pytest "{TEST}[rand-1]" "test_rw.py::test_plain"'
    assert got["labelled"] == [False, False]
    assert got["plain"] == _PLAIN


def _started_below_the_rootdir(data: dict[str, Any]) -> dict[str, Any]:
    """The same report from a run started in ``sub/``, with the tests one folder up."""
    for test in data["tests"]:
        for run in test["runs"]:
            run["cmd_nodeid"] = "../" + run["nodeid"]
    return data


@requires_node
@pytest.mark.parametrize("export", [True, False])
def test_commands_the_report_builds_name_files_from_the_invocation_folder(export: bool) -> None:
    """Started below the rootdir, a node ID names no file: commands use ``cmd_nodeid``."""
    document = _document(rerun=False, seed=7) if export else None
    got = _commands(_started_below_the_rootdir(_report(document, marks=True)))
    assert got["vector"]["text"] == f'pytest "../{TEST}[rand-1]" --rng-seed=7'
    assert got["all"]["text"] == f'pytest "../{TEST}" --rng-seed=7'
    assert got["failures"] == f'pytest "../{TEST}[rand-1]" "../test_rw.py::test_plain" --rng-seed=7'
    assert got["plain"][0] == {"text": 'pytest "../test_rw.py::test_plain"', "note": ""}


@requires_node
def test_the_arguments_of_a_44_export_are_not_rewritten() -> None:
    """Its arguments are relative to the invocation folder already."""
    got = _commands(_started_below_the_rootdir(_report(_document(rerun=True))))
    plain = _commands(_report(_document(rerun=True)))
    assert got["vector"] == plain["vector"]
    assert got["all"] == plain["all"]
    assert got["again"] == plain["again"]


@requires_node
@pytest.mark.parametrize(
    ("cmdline", "expected"),
    [
        (["--rng-seed=5", "-x"], "pytest --rng-seed=5 -x"),
        (["--rng-seed", "5"], "pytest --rng-seed 5"),
        (["-x"], f"pytest -x --rng-seed={BIG_SEED}"),
        ([], f"pytest --rng-seed={BIG_SEED}"),
    ],
)
def test_run_again_adds_the_seed_once(cmdline: list[str], expected: str) -> None:
    data = _report(_document(rerun=False, seed=BIG_SEED))
    data["cmdline"] = cmdline
    assert _commands(data)["again"]["text"] == expected


@requires_node
def test_copy_line_shows_label_folder_and_note() -> None:
    got = _node(
        "const line = commandLine({label: 'Run again with the same vectors',\n"
        "  command: {text: 'pytest -x', cwd: '/work/proj', note: 'a note'}});\n"
        "const box = findAll(line, 'detail-cmd')[0];\n"
        "const first = {label: texts(line, 'cmd-label'), code: texts(line, 'detail-cmd-code'),\n"
        "  cwd: texts(line, 'cmd-cwd'), note: texts(line, 'cmd-note'),\n"
        "  attrs: Object.assign({}, box.attrs),\n"
        "  events: box.events, hidden: findAll(line, 'cmd-hints')[0].hidden};\n"
        "setCommandLine(line, {text: 'pytest -q'});\n"
        "const plain = commandLine({ariaLabel: 'Copy command to run this test', id: 'detail-cmd',\n"
        "  command: {text: 'pytest \"t.py::test_a\"'}});\n"
        "console.log(JSON.stringify({first,\n"
        "  second: {code: texts(line, 'detail-cmd-code'), cwd: texts(line, 'cmd-cwd'),\n"
        "    note: texts(line, 'cmd-note'), hidden: findAll(line, 'cmd-hints')[0].hidden},\n"
        "  plain: {cls: plain.className, label: texts(plain, 'cmd-label'),\n"
        "    attrs: findAll(plain, 'detail-cmd')[0].attrs}}));",
        *_RENDERING,
    )
    assert got["first"] == {
        "label": ["Run again with the same vectors"],
        "code": ["pytest -x"],
        "cwd": ["Run from /work/proj"],
        # The export's note, written for the terminal, as a sentence
        "note": ["A note"],
        # Keyboard: a focusable button that copies on click, Enter and Space
        "attrs": {
            "role": "button",
            "tabindex": "0",
            "aria-label": "Copy command: Run again with the same vectors",
            "title": "pytest -x",
        },
        "events": ["click", "keydown"],
        "hidden": False,
    }
    assert got["second"] == {"code": ["pytest -q"], "cwd": [], "note": [], "hidden": True}
    assert got["plain"]["cls"] == "cmd-line"
    assert got["plain"]["label"] == []
    assert got["plain"]["attrs"]["aria-label"] == "Copy command to run this test"
    assert got["plain"]["attrs"]["id"] == "detail-cmd"


@requires_node
def test_strategy_rows_have_a_copy_button_per_item() -> None:
    document = _document(rerun=True)
    rows = document["tests"][0]["strategies"][0]["rows"]
    # One row, two test items (a second parametrization), then a row that did not run
    rows[1]["items"].append(
        {
            "nodeid": f"{TEST}[b-rand-1]",
            "outcome": "passed",
            "rerun": {"args": ["-k", "b-rand-1", "--rng-seed=7"], "note": "outside the rootdir"},
        }
    )
    rows.append({"id": "rand-2", "kind": "random", "values": {"wdata": 2}, "items": []})
    # A second row with the same note: the text is written once, under the table
    rows.append(
        {
            "id": "rand-3",
            "kind": "random",
            "values": {"wdata": 3},
            "items": [
                {
                    "nodeid": f"{TEST}[b-rand-3]",
                    "outcome": "passed",
                    "rerun": {"args": ["-k", "b-rand-3"], "note": "outside the rootdir"},
                }
            ],
        }
    )
    data = _report(document)
    got = _node(
        f"const DATA = {json.dumps(data)};\n"
        "const test = DATA.tests[0];\n"
        "const tab = renderStrategyRows(test.strategies[0], test, test.runs[0]);\n"
        "const buttons = findAll(tab, 'strategy-copy');\n"
        "console.log(JSON.stringify({\n"
        "  titles: buttons.map(b => b.attrs.title),\n"
        "  labels: buttons.map(b => b.attrs['aria-label']),\n"
        "  tags: buttons.map(b => b.tag + ':' + b.attrs.type), notes: texts(tab, 'cmd-note'),\n"
        "  marks: findAll(tab, 'strategy-note-mark').map(m => [m.textContent, m.attrs.title]),\n"
        "  last: tab.children.at(-1).className,\n"
        "  cells: findAll(tab, 'tr').slice(1).map(tr => tr.children.at(-1).textContent),\n"
        "}));",
        *_COMMANDS,
        *_RENDERING,
    )
    options = "--rng-seed=7 --nsamples=4 rw:small"
    assert got["titles"] == [
        f'pytest "{TEST}[rand-0]" {options}',
        f'pytest "{TEST}[rand-1]" {options}',
        "pytest -k b-rand-1 --rng-seed=7\nOutside the rootdir",
        "pytest -k b-rand-3\nOutside the rootdir",
    ]
    assert got["labels"] == [
        "Copy command to run row rand-0 again",
        f"Copy command to run row rand-1 ({TEST}[rand-1]) again",
        f"Copy command to run row rand-1 ({TEST}[b-rand-1]) again",
        "Copy command to run row rand-3 again",
    ]
    assert got["tags"] == ["button:button"] * 4
    # Each row the note applies to has a mark; the note itself comes once, last
    assert got["marks"] == [["*", "Outside the rootdir"]] * 2
    assert got["notes"] == ["* Outside the rootdir"]
    assert got["last"] == "cmd-note strategy-rows-note"
    assert got["cells"] == ["Passed01", "Failed02Passed*", "Not run", "Passed*"]


def test_copy_lines_are_wired_into_the_report() -> None:
    """Where the lines are: the test header, the Summary and Report tabs, the Failures panel."""
    assert "setCommandLine(detailCmdLine, vectorCommand(selectedTest, run))" in JS
    assert "label: vectors ? 'This vector' : ''" in JS
    assert "label:'All vectors of this test'" in JS
    assert JS.count("commandLine({label:'Run again with the same vectors'") == 2
    assert "const rerun = failuresCommand(items.map(i => i.run));" in JS
    assert "announce('Command copied')" in _function("copyButton")
    for rule in (".cmd-line.labeled", ".cmd-label", ".cmd-hints", ".strategy-copy:focus-visible"):
        assert rule in CSS
    printed = CSS[CSS.rindex("@media print {") :]
    assert ".strategy-copy" in printed  # the buttons are not printed, the commands are


# ---------------------------------------------------------------------------
# Through pytest, with a stand-in for pytest-strategies
# ---------------------------------------------------------------------------

_STAND_IN = '''
import json
from pathlib import Path

import pytest

DOCUMENT = json.loads({document!r})
SEED = {seed!r}


class Spec:
    @pytest.hookspec(firstresult=True)
    def pytest_strategies_export_dir(config):
        """As in pytest-strategies 4.3."""


class VectorInfo:
    def to_dict(self):
        return {{"strategy": "rw", "kind": "random", "name": None, "seed": SEED}}


def pytest_addhooks(pluginmanager):
    pluginmanager.add_hookspecs(Spec)


def pytest_addoption(parser):
    parser.addoption("--rng-seed", dest="rng_seed", default=None)
    parser.addini("strategies_export_dir", "", type="string", default="")


def pytest_configure(config):
    config.addinivalue_line("markers", "strategy(info): a strategy row")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    for item in items:
        if SEED is not None and item.name.startswith("test_rw"):
            item.add_marker(pytest.mark.strategy(VectorInfo()))


def pytest_sessionfinish(session):
    config = session.config
    folder = config.hook.pytest_strategies_export_dir(config=config)
    if DOCUMENT is not None and folder:
        folder = Path(config.rootpath, folder)
        (folder / "strategies.json").write_text(json.dumps({{"kind": "strategy_definitions"}}))
        (folder / "strategies.vectors.json").write_text(json.dumps(DOCUMENT))
'''

_TESTS = """
import pytest

@pytest.mark.parametrize("row", ["rand-0", "rand-1"])
def test_rw(row):
    assert row != "rand-1"

def test_plain():
    pass
"""

_DATA_BLOCK = '<script type="application/json" id="report-data">'


def _run(
    pytester: Pytester, document: dict[str, Any] | None, *args: str, seed: int | None = None
) -> tuple[dict[str, Any], str]:
    """Run the two tests; the report's data, and its text as embedded."""
    pytester.makeconftest(_STAND_IN.format(document=json.dumps(document), seed=seed))
    pytester.makepyfile(test_rw=_TESTS)
    result = pytester.runpytest("--report-dir=reports", "-p", "no:pytest_strategy", *args)
    result.assert_outcomes(passed=2, failed=1)
    (run_dir,) = sorted((pytester.path / "reports" / "runs").iterdir())
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    start = html.index(_DATA_BLOCK) + len(_DATA_BLOCK)
    text = html[start : html.index("</script>", start)]
    return json.loads(text), text


def _by_name(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["base_nodeid"]: t for t in data["tests"]}


def test_report_data_with_a_44_export(pytester: Pytester) -> None:
    data, _ = _run(pytester, _document(rerun=True))
    assert data["rerun"] == {
        "args": ["tests dir", "-k", "rw and not slow", "--rng-seed=7"],
        "options": ["--rng-seed=7", "--nsamples=4", "rw:small"],
        "cwd": CWD,
        "seed": "7",
    }
    tests = _by_name(data)
    assert tests[TEST]["rerun"] == {"args": [TEST, "--rng-seed=7", "--nsamples=4", "rw:small"]}
    assert tests[TEST]["strategies"][0]["rows"][0]["items"][0]["rerun"] == {
        "args": [f"{TEST}[rand-0]", "--rng-seed=7", "--nsamples=4", "rw:small"]
    }
    assert tests["test_rw.py::test_plain"]["rerun"] is None
    assert tests["test_rw.py::test_plain"]["strategies"] == []


def test_report_data_with_a_43_export_and_a_19_digit_seed(pytester: Pytester) -> None:
    data, text = _run(pytester, _document(rerun=False, seed=BIG_SEED), seed=BIG_SEED)
    # The folder pytest was started in, when the export does not say
    assert data["rerun"] == {"seed": str(BIG_SEED), "cwd": str(pytester.path)}
    tests = _by_name(data)
    assert tests[TEST]["rerun"] is None
    assert "rerun" not in tests[TEST]["strategies"][0]["rows"][0]["items"][0]
    assert [run["strategy"]["seed"] for run in tests[TEST]["runs"]] == [str(BIG_SEED)] * 2
    # Nowhere in the data is the seed a number, which JavaScript would round
    assert str(BIG_SEED) in text
    for prefix in (": ", ":", "[", ", ", ","):
        assert f"{prefix}{BIG_SEED}" not in text


@requires_node
def test_the_embedded_19_digit_seed_reaches_the_commands(pytester: Pytester) -> None:
    """End to end: the report's data, read by JavaScript as the report does."""
    _, text = _run(pytester, None, seed=BIG_SEED)
    got = _node(f"const DATA = JSON.parse({json.dumps(text)});\n{_ALL}", *_COMMANDS)
    seed = f"--rng-seed={BIG_SEED}"
    assert got["vector"]["text"] == f'pytest "{TEST}[rand-1]" {seed}'
    assert got["all"]["text"] == f'pytest "{TEST}" {seed}'
    assert got["again"]["text"].endswith(f" {seed}")
    assert got["again"]["text"].count("--rng-seed") == 1
    assert got["plain"] == _PLAIN


def test_the_run_command_keeps_a_seed_given_on_the_command_line(pytester: Pytester) -> None:
    data, _ = _run(pytester, None, "--rng-seed=5", seed=5)
    assert data["rerun"]["seed"] == "5"
    assert "--rng-seed=5" in data["cmdline"]
    assert [run["strategy"]["seed"] for run in _by_name(data)[TEST]["runs"]] == [5, 5]


def test_report_data_without_pytest_strategies(pytester: Pytester) -> None:
    data, text = _run(pytester, None)
    assert data["rerun"] is None
    assert all(t["rerun"] is None for t in data["tests"])
    assert all(run["strategy"] is None for t in data["tests"] for run in t["runs"])
    assert "--rng-seed" not in text


def test_report_data_of_a_run_started_below_the_rootdir(
    pytester: Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each run carries its node ID as a command takes it from that folder."""
    pytester.makeini("[pytest]\n")
    pytester.makepyfile(test_top="def test_a(): pass")
    sub = pytester.mkdir("sub")
    (sub / "test_low.py").write_text(
        "import pytest\n\n@pytest.mark.parametrize('n', [1, 2])\ndef test_b(n): pass\n"
    )
    monkeypatch.chdir(sub)
    result = pytester.runpytest("test_low.py", "../test_top.py", "--report-dir=../reports")
    result.assert_outcomes(passed=3)
    (run_dir,) = sorted((pytester.path / "reports" / "runs").iterdir())
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    start = html.index(_DATA_BLOCK) + len(_DATA_BLOCK)
    data = json.loads(html[start : html.index("</script>", start)])
    runs = {run["nodeid"]: run.get("cmd_nodeid") for t in data["tests"] for run in t["runs"]}
    assert runs == {
        "sub/test_low.py::test_b[1]": "test_low.py::test_b[1]",
        "sub/test_low.py::test_b[2]": "test_low.py::test_b[2]",
        "test_top.py::test_a": "../test_top.py::test_a",
    }


def test_report_data_of_a_run_started_in_the_rootdir_has_no_command_node_ids(
    pytester: Pytester,
) -> None:
    data, _ = _run(pytester, None)
    assert all("cmd_nodeid" not in run for t in data["tests"] for run in t["runs"])


def test_report_strategies_false_leaves_the_export_out(pytester: Pytester) -> None:
    pytester.makeini("[pytest]\nreport_strategies = false\n")
    data, _ = _run(pytester, _document(rerun=True))
    assert data["rerun"] is None


def test_a_real_run_of_pytest_strategies(pytester: Pytester) -> None:
    """With pytest-strategies itself (4.3 or later): the commands carry the run's seed."""
    pytest.importorskip("pytest_strategy._run_export", reason="needs pytest-strategies 4.3+")
    pytester.makepyfile(
        strategies="""
        from pytest_strategy import Parameter, RNGInteger, TestArg, register

        @register("rw")
        def rw(ctx=None):
            return Parameter(TestArg("wdata", rng_type=RNGInteger(0, 255)))
        """,
        test_rw="""
        from pytest_strategy import strategy

        @strategy("rw")
        def test_rw(wdata):
            pass

        def test_plain():
            pass
        """,
    )
    result = pytester.runpytest("--report-dir=reports", f"--rng-seed={BIG_SEED}", "--nsamples=2")
    result.assert_outcomes(passed=3)
    (run_dir,) = sorted((pytester.path / "reports" / "runs").iterdir())
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    start = html.index(_DATA_BLOCK) + len(_DATA_BLOCK)
    data = json.loads(html[start : html.index("</script>", start)])
    seed = f"--rng-seed={BIG_SEED}"
    assert data["rerun"]["seed"] == str(BIG_SEED)
    assert Path(data["rerun"]["cwd"]) == pytester.path
    test = _by_name(data)[TEST]
    assert all(run["strategy"]["seed"] == str(BIG_SEED) for run in test["runs"])
    if data["rerun"].get("args"):  # pytest-strategies 4.4+
        assert seed in data["rerun"]["args"]
        assert seed in data["rerun"]["options"]
        assert seed in test["rerun"]["args"]
        for row in test["strategies"][0]["rows"]:
            assert seed in row["items"][0]["rerun"]["args"]
    assert _by_name(data)["test_rw.py::test_plain"]["rerun"] is None


@requires_node
def test_a_run_without_strategy_rows_keeps_its_commands(pytester: Pytester) -> None:
    """pytest-strategies installed, no ``@strategy`` in the run.

    It writes its export all the same, with a time-based seed and the run's
    command: there are no vectors to bring back, so the report shows no "Run
    again with the same vectors" line and the Failures command has no seed.
    """
    document = _document(rerun=True, seed=BIG_SEED)
    document["tests"] = []
    data, text = _run(pytester, document)
    assert data["rerun"] is None
    assert data["strategies"]["tests"] == 0
    got = _node(f"const DATA = JSON.parse({json.dumps(text)});\n{_ALL}", *_COMMANDS)
    assert got["again"] is None
    assert got["failures"] == f'pytest "{TEST}[rand-1]" "test_rw.py::test_plain"'
    assert got["vector"] == {"text": f'pytest "{TEST}[rand-1]"', "note": ""}
    assert got["labelled"] == [False, False]
    assert got["plain"] == _PLAIN


def _print_rules() -> dict[str, str]:
    """The rules of the print stylesheet: each selector with its declarations."""
    start = CSS.rindex("@media print {")
    depth = 0
    for end in range(CSS.index("{", start), len(CSS)):
        depth += {"{": 1, "}": -1}.get(CSS[end], 0)
        if depth == 0:
            break
    block = CSS[CSS.index("{", start) + 1 : end]
    rules: dict[str, str] = {}
    for rule in block.split("}"):
        selectors, _, declarations = rule.partition("{")
        for selector in selectors.split(","):
            if selector.strip():
                rules[selector.strip()] = rules.get(selector.strip(), "") + declarations.strip()
    return rules


def test_print_hides_the_chrome_and_wraps_the_commands() -> None:
    """The copy lines' print rules sit beside the list of hidden parts, not inside it."""
    rules = _print_rules()
    for hidden in (
        ".skip-link",
        ".tabs",
        ".theme-toggle",
        ".tree-panel",
        ".detail-cmd-hint",
        ".strategy-copy",
        ".strip-btn",
    ):
        assert "display: none !important" in rules[hidden], hidden
        assert "white-space" not in rules[hidden], hidden
    assert "white-space: normal" in rules[".detail-cmd-code"]
    assert "display: none" not in rules[".detail-cmd-code"]
    assert rules[".run-again"] == "break-inside: avoid;"
