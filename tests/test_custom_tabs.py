"""Custom HTML tabs: the ``report_tabs`` fixture, the ``pytest_reporter_test_tabs``
hook, what is saved in the run folder and what reaches the HTML report."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter import ReportTabs
from pytest_reporter._html_builder._js import JS
from pytest_reporter._tabs import collect_tabs

if TYPE_CHECKING:
    from pytest import Pytester


def _run_dir(pytester: Pytester) -> Path:
    return sorted((pytester.path / "reports" / "runs").iterdir())[-1]


def _report_data(pytester: Pytester) -> dict[str, Any]:
    html = (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="report-data">(.*?)</script>', html, re.DOTALL
    )
    assert match
    return json.loads(match.group(1))  # type: ignore[no-any-return]


def _runs(pytester: Pytester) -> dict[str, dict[str, Any]]:
    return {run["nodeid"]: run for test in _report_data(pytester)["tests"] for run in test["runs"]}


# --- ReportTabs ---------------------------------------------------------


def test_add_saves_files_and_manifest(tmp_path: Path) -> None:
    tabs = ReportTabs(tmp_path / "tabs")
    tabs.add("Waveform", "<p>one</p>")
    tabs.add("  Eye   diagram ", "<p>two</p>", scripts=True, height=300)
    assert tabs.titles == ["Waveform", "Eye diagram"]
    manifest = json.loads((tmp_path / "tabs" / "tabs.json").read_text())
    assert manifest == {
        "tabs": [
            {"title": "Waveform", "file": "01_waveform.html", "scripts": False, "height": None},
            {"title": "Eye diagram", "file": "02_eye_diagram.html", "scripts": True, "height": 300},
        ]
    }
    assert (tmp_path / "tabs" / "02_eye_diagram.html").read_text() == "<p>two</p>"
    assert collect_tabs(tmp_path / "tabs") == [
        {"title": "Waveform", "scripts": False, "height": None, "html": "<p>one</p>"},
        {"title": "Eye diagram", "scripts": True, "height": 300, "html": "<p>two</p>"},
    ]


def test_content_from_file_and_repr_html(tmp_path: Path) -> None:
    class Styled:
        def _repr_html_(self) -> str:
            return "<table></table>"

    source = tmp_path / "eye.html"
    source.write_text("<h1>é</h1>", encoding="utf-8")
    tabs = ReportTabs(tmp_path / "tabs")
    tabs.add("File", source)
    tabs.add("Object", Styled())
    assert [t["html"] for t in collect_tabs(tmp_path / "tabs")] == ["<h1>é</h1>", "<table></table>"]


@pytest.mark.parametrize(
    ("title", "error"),
    [
        ("", ValueError),
        ("   ", ValueError),
        ("x" * 41, ValueError),
        ("Summary", ValueError),
        ("checks", ValueError),
        ("RETRIES", ValueError),
        ("waveform", ValueError),  # repeated, compared without case
        (3, TypeError),
    ],
)
def test_bad_titles(title: object, error: type[Exception]) -> None:
    tabs = ReportTabs()  # checked without --report-dir too
    tabs.add("Waveform", "<p></p>")
    with pytest.raises(error):
        tabs.add(title, "<p></p>")
    assert tabs.titles == ["Waveform"]


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"content": 3}, TypeError),
        ({"content": b"<p></p>"}, TypeError),
        ({"content": "x", "scripts": 1}, TypeError),
        ({"content": "x", "height": 0}, ValueError),
        ({"content": "x", "height": 1.5}, TypeError),
        ({"content": "x", "height": True}, TypeError),
        ({"content": Path("no/such/file.html")}, OSError),
    ],
)
def test_bad_arguments(kwargs: dict[str, Any], error: type[Exception]) -> None:
    tabs = ReportTabs()
    with pytest.raises(error):
        tabs.add("Tab", **kwargs)
    assert tabs.titles == []


def test_collect_survives_broken_folder(tmp_path: Path) -> None:
    assert collect_tabs(tmp_path / "missing") == []
    (tmp_path / "tabs.json").write_text("{not json")
    with pytest.warns(UserWarning, match="tabs skipped"):
        assert collect_tabs(tmp_path) == []
    # a listed file that is gone, and a path that leaves the folder
    (tmp_path / "secret.html").write_text("secret")
    inner = tmp_path / "tabs"
    inner.mkdir()
    (inner / "01_ok.html").write_text("ok")
    (inner / "tabs.json").write_text(
        json.dumps(
            {
                "tabs": [
                    {"title": "Gone", "file": "gone.html"},
                    {"title": "Out", "file": "../secret.html"},
                    {"title": "Ok", "file": "01_ok.html", "height": "tall"},
                    "nonsense",
                ]
            }
        )
    )
    with pytest.warns(UserWarning, match="tab skipped"):
        tabs = collect_tabs(inner)
    assert tabs == [{"title": "Ok", "scripts": False, "height": None, "html": "ok"}]


# --- In a test run ------------------------------------------------------


def test_fixture_and_hook_tabs_reach_the_report(pytester: Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def bench():
            state = {"alive": True}
            yield state
            state["alive"] = False

        def pytest_reporter_test_tabs(item, tabs):
            bench = item.funcargs.get("bench")
            tabs.add("Bench log", f"<p>{item.name} alive={bench and bench['alive']}</p>")
        """
    )
    pytester.makepyfile(
        """
        def test_one(report_tabs, bench):
            report_tabs.add("Waveform", "<h1>wave</h1><script>x</script>")
            report_tabs.add("Plot", "<div></div>", scripts=True, height=250)

        def test_two():
            pass
        """
    )
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=2)
    runs = _runs(pytester)
    one = runs["test_fixture_and_hook_tabs_reach_the_report.py::test_one"]["tabs"]
    assert one == [
        {
            "title": "Waveform",
            "scripts": False,
            "height": None,
            "html": "<h1>wave</h1><script>x</script>",
        },
        {"title": "Plot", "scripts": True, "height": 250, "html": "<div></div>"},
        # the hook runs before the fixtures are torn down
        {
            "title": "Bench log",
            "scripts": False,
            "height": None,
            "html": "<p>test_one alive=True</p>",
        },
    ]
    two = runs["test_fixture_and_hook_tabs_reach_the_report.py::test_two"]["tabs"]
    assert [t["title"] for t in two] == ["Bench log"]
    # the tab's markup never reaches the report as markup
    html = (_run_dir(pytester) / "report.html").read_text(encoding="utf-8")
    assert "<h1>wave</h1>" not in html
    tabs_dir = next(_run_dir(pytester).glob("tests/**/test_one/default/tabs"))
    assert sorted(p.name for p in tabs_dir.iterdir()) == [
        "01_waveform.html",
        "02_plot.html",
        "03_bench_log.html",
        "tabs.json",
    ]


def test_without_report_dir_nothing_is_saved(pytester: Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        def test_one(report_tabs):
            report_tabs.add("Waveform", "<p></p>")
            with pytest.raises(ValueError):
                report_tabs.add("Summary", "<p></p>")
            assert report_tabs.titles == ["Waveform"]
        """
    )
    pytester.runpytest().assert_outcomes(passed=1)
    assert not list(pytester.path.rglob("tabs.json"))


def test_a_raising_hook_is_a_warning(pytester: Pytester) -> None:
    pytester.makeconftest(
        """
        def pytest_reporter_test_tabs(item, tabs):
            tabs.add("Artifacts", "<p></p>")
        """
    )
    pytester.makepyfile("def test_one(): pass")
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(
        ["*pytest_reporter_test_tabs of * failed and was skipped: ValueError*"]
    )
    assert _runs(pytester)["test_a_raising_hook_is_a_warning.py::test_one"]["tabs"] == []


def test_each_retry_attempt_has_its_own_tabs(pytester: Pytester) -> None:
    pytester.makepyfile(
        """
        calls = []

        def test_flaky(report_tabs):
            calls.append(1)
            report_tabs.add("Attempt", f"<p>attempt {len(calls)}</p>")
            assert len(calls) == 2
        """
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=2").assert_outcomes(passed=1)
    run = _runs(pytester)["test_each_retry_attempt_has_its_own_tabs.py::test_flaky"]
    assert [t["html"] for t in run["tabs"]] == ["<p>attempt 1</p>"]
    assert [t["html"] for t in run["retry_attempts"][0]["tabs"]] == ["<p>attempt 2</p>"]


def test_parametrized_runs_keep_their_tabs_apart(pytester: Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize("n", [1, 2])
        def test_p(report_tabs, n):
            report_tabs.add("N", f"<p>{n}</p>")
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=2)
    assert [r["tabs"][0]["html"] for r in _runs(pytester).values()] == ["<p>1</p>", "<p>2</p>"]


def test_one_raising_implementation_costs_only_its_own_tabs(pytester: Pytester) -> None:
    pytester.makeconftest(
        """
        class Other:
            def pytest_reporter_test_tabs(self, tabs):
                tabs.add("Summary", "<p></p>")

        def pytest_configure(config):
            config.pluginmanager.register(Other(), "other")

        def pytest_reporter_test_tabs(item, tabs):
            tabs.add("Mine", "<p>mine</p>")
        """
    )
    pytester.makepyfile("def test_one(): pass")
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*pytest_reporter_test_tabs of other failed*ValueError*"])
    tabs = _runs(pytester)["test_one_raising_implementation_costs_only_its_own_tabs.py::test_one"]
    assert [t["title"] for t in tabs["tabs"]] == ["Mine"]


@pytest.mark.parametrize("call", ["pytest.skip('no tabs')", "pytest.fail('bad tab')"])
def test_skip_or_fail_in_the_hook_never_reaches_the_test(pytester: Pytester, call: str) -> None:
    pytester.makeconftest(
        f"""
        import pytest

        @pytest.fixture
        def res():
            yield 1

        def pytest_reporter_test_tabs(item, tabs):
            if item.name == "test_a":
                {call}
        """
    )
    pytester.makepyfile(
        """
        def test_a(res): pass
        def test_b(res): pass
        """
    )
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=2)
    result.stdout.fnmatch_lines(["*pytest_reporter_test_tabs of * failed and was skipped*"])


def test_a_file_that_is_not_utf8_is_still_a_tab(tmp_path: Path) -> None:
    source = tmp_path / "latin.html"
    source.write_bytes("<p>é</p>".encode("latin-1"))
    tabs = ReportTabs(tmp_path / "tabs")
    tabs.add("File", source)
    assert collect_tabs(tmp_path / "tabs")[0]["html"] == "<p>\ufffd</p>"


def test_a_rerun_by_another_plugin_starts_without_tabs(pytester: Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest
        from _pytest.runner import runtestprotocol

        @pytest.hookimpl(tryfirst=True)
        def pytest_runtest_protocol(item, nextitem):
            item.ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
            runtestprotocol(item, nextitem=nextitem, log=False)
            for report in runtestprotocol(item, nextitem=nextitem, log=False):
                item.ihook.pytest_runtest_logreport(report=report)
            item.ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)
            return True
        """
    )
    pytester.makepyfile(
        """
        calls = []

        def test_y(report_tabs):
            calls.append(1)
            if len(calls) == 1:
                report_tabs.add("First only", "<p>stale</p>")
        """
    )
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    assert (
        _runs(pytester)["test_a_rerun_by_another_plugin_starts_without_tabs.py::test_y"]["tabs"]
        == []
    )


# --- The report's script ------------------------------------------------


def test_frames_are_sandboxed() -> None:
    # scripts only on request, and never together with same-origin
    assert "sandbox: tab.scripts ? 'allow-scripts' : 'allow-same-origin'" in JS
    assert "allow-scripts allow-same-origin" not in JS
    assert "allow-same-origin allow-scripts" not in JS
    assert "frame.srcdoc = doc.html" in JS


def test_custom_tabs_come_after_the_reports_own() -> None:
    body = JS[JS.index("function subTabNames") : JS.index("function customTabs")]
    assert body.index("'Retries'") < body.index("customTabs(run).forEach")


def test_the_height_script_comes_before_the_tabs_markup() -> None:
    body = JS[JS.index("function customTabDoc") : JS.index("function renderCustomTab")]
    assert "script + '</head><body>' + html" in body


requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\nfunction ", start + 1)]


def _node(script: str, *functions: str) -> Any:  # noqa: ANN401
    out = subprocess.run(
        ["node", "-"],
        input="\n".join([*(_function(n) for n in functions), script]),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@requires_node
def test_a_whole_document_is_told_from_a_fragment() -> None:
    cases = [
        "<!doctype html><p>x</p>",
        "<html><body></body></html>",
        "\n <!-- c -->\n<HTML lang=en>",
        "<p>x</p>",
        "<pre>&lt;x&gt;</pre><script>const s = '<!DOCTYPE html><html>';</script>",
        "<p>write <html> first</p>",
        "",
    ]
    got = _node(
        f"console.log(JSON.stringify({json.dumps(cases)}.map(customTabIsWhole)));",
        "customTabIsWhole",
    )
    assert got == [True, True, True, False, False, False, False]


@requires_node
def test_custom_tabs_skip_bad_and_reserved_titles() -> None:
    tabs = [
        {"title": "Wave"},
        {"title": "summary"},
        {"title": "wave"},
        {"title": ""},
        {"title": 3},
        None,
        {"title": "Plot"},
    ]
    got = _node(
        f"console.log(JSON.stringify([customTabs({{tabs: {json.dumps(tabs)}}}).map(t => t.title),"
        " customTabs({}), customTabs(null)]));",
        "customTabs",
    )
    assert got == [["Wave", "Plot"], [], []]


@requires_node
def test_frame_height_stops_following_a_document_that_follows_it() -> None:
    script = """
    let t = 0;
    globalThis.performance = {now: () => t};
    const CUSTOM_TAB_DEFAULT_PX = 480, CUSTOM_TAB_MAX_PX = 20000;
    const loop = {style: {height: '480px'}, offsetHeight: 0, clientHeight: 0};
    for (let i = 1; i <= 40; i++) { t += 16; customTabHeight(loop, 480 + 16 * i); }
    // content that grows now and then (images loading) is still followed
    const slow = {style: {height: '480px'}, offsetHeight: 0, clientHeight: 0};
    for (let i = 1; i <= 40; i++) { t += 500; customTabHeight(slow, 480 + 16 * i); }
    // the frame's own border is part of its height
    const edged = {style: {height: '480px'}, offsetHeight: 102, clientHeight: 100};
    customTabHeight(edged, 300);
    console.log(JSON.stringify([loop.style.height, slow.style.height, edged.style.height]));
    """
    assert _node(script, "customTabHeight") == ["480px", "1120px", "302px"]
