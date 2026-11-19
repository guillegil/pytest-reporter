"""Bench provenance: ``report_bench``, ``pytest_reporter_bench`` and what they produce.

``BenchInfo`` records devices, instruments and other facts of the setup. The
reporter writes them to ``bench.json``, to ``junit.xml`` as properties and to
the HTML report (``DATA.bench``, each run's ``bench_changes``). The renderers
run under Node with a minimal DOM (text only), as the card tests do.
"""

from __future__ import annotations

import datetime
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any

import pytest

from pytest_reporter import BenchInfo, _bench
from pytest_reporter._html_builder._css import CSS
from pytest_reporter._html_builder._js import JS

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import Pytester

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

IDN = "Keysight Technologies,34465A,MY53001234,A.03.01-03.15"
TODAY = datetime.date(2026, 11, 19)


def _recording(running: tuple[str | None, int] = (None, 0)) -> BenchInfo:
    return _bench.recording(lambda: running)


# ---------------------------------------------------------------------------
# BenchInfo
# ---------------------------------------------------------------------------


def test_sections_devices_and_instruments() -> None:
    bench = _recording()
    bench.set("Fixture board", "FB-12")
    bench.set("Ambient", "23.5 °C", section="Environment")
    bench.update({"Site": "Lab 2", "Rack": 4, "Shielded": True, "Gain": 1.5})
    bench.device("DUT", serial="SN-0042", firmware="2.3.1", hardware="rev C", lot="2231")
    bench.instrument("DMM", idn=IDN, calibrated="2026-03-02", cal_due="2027-03-02")
    document = bench.document(TODAY)
    assert document["run_date"] == "2026-11-19"
    assert document["sections"] == {
        "Bench": {
            "Fixture board": "FB-12",
            "Site": "Lab 2",
            "Rack": 4,
            "Shielded": True,
            "Gain": 1.5,
        },
        "Environment": {"Ambient": "23.5 °C"},
    }
    assert document["devices"] == [
        {
            "name": "DUT",
            "serial": "SN-0042",
            "firmware": "2.3.1",
            "hardware": "rev C",
            "lot": "2231",
        }
    ]
    assert document["instruments"] == [
        {
            "name": "DMM",
            "idn": IDN,
            "manufacturer": "Keysight Technologies",
            "model": "34465A",
            "serial": "MY53001234",
            "firmware": "A.03.01-03.15",
            "calibrated": "2026-03-02",
            "cal_due": "2027-03-02",
            "overdue": False,
        }
    ]
    assert document["changes"] == []
    assert document["metadata"] == {}
    json.dumps(document)


def test_idn_parts_yield_to_explicit_values() -> None:
    bench = _recording()
    bench.instrument("DMM", idn=IDN, serial="ASSET-7", model="34465A (opt. DIG)")
    bench.instrument("Probe", idn="P6139B")  # not four parts: kept, not split
    bench.instrument("Scope", idn="Tektronix,,C012345,")  # blank parts are left out
    dmm, probe, scope = bench.document(TODAY)["instruments"]
    assert dmm["serial"] == "ASSET-7"
    assert dmm["model"] == "34465A (opt. DIG)"
    assert dmm["manufacturer"] == "Keysight Technologies"
    assert dmm["idn"] == IDN
    assert probe == {"name": "Probe", "idn": "P6139B", "overdue": False}
    assert scope == {
        "name": "Scope",
        "idn": "Tektronix,,C012345,",
        "manufacturer": "Tektronix",
        "serial": "C012345",
        "overdue": False,
    }


def test_dates_are_stored_as_iso_text() -> None:
    bench = _recording()
    bench.set("Built", datetime.date(2026, 1, 2))
    bench.set("Started", datetime.datetime(2026, 1, 2, 3, 4, 5))
    bench.instrument(
        "PSU",
        calibrated=datetime.datetime(2026, 6, 10, 9, 30),
        cal_due=datetime.date(2027, 6, 10),
    )
    document = bench.document(TODAY)
    assert document["sections"]["Bench"] == {
        "Built": "2026-01-02",
        "Started": "2026-01-02T03:04:05",
    }
    assert document["instruments"][0]["calibrated"] == "2026-06-10"
    assert document["instruments"][0]["cal_due"] == "2027-06-10"


def test_none_stores_nothing_and_removes_nothing() -> None:
    bench = _recording()
    bench.device("DUT", serial="SN-1", firmware=None)
    bench.device("DUT", serial=None, firmware="2.0")
    bench.set("Site", None)
    bench.device("Spare")
    document = bench.document(TODAY)
    assert document["devices"] == [{"name": "DUT", "serial": "SN-1", "firmware": "2.0"}]
    assert document["sections"] == {}
    assert document["changes"] == []
    assert bench.changes() == []


def test_a_float_json_cannot_hold_is_text() -> None:
    bench = _recording()
    bench.set("Leak", float("inf"))
    assert bench.document(TODAY)["sections"]["Bench"]["Leak"] == "inf"


def test_overdue_is_before_the_day_of_the_run() -> None:
    bench = _recording()
    bench.instrument("Late", cal_due="2026-11-18")
    bench.instrument("Today", cal_due="2026-11-19")
    bench.instrument("Undated")
    assert bench.overdue(TODAY) == [("Late", "2026-11-18")]
    flags = {i["name"]: i["overdue"] for i in bench.document(TODAY)["instruments"]}
    assert flags == {"Late": True, "Today": False}
    assert _bench.overdue_message("Late", "2026-11-18") == (
        "pytest-reporter: instrument 'Late' calibration was due 2026-11-18"
    )


def test_a_changed_value_is_a_change_of_the_running_test() -> None:
    running: list[tuple[str | None, int]] = [(None, 0)]
    bench = _bench.recording(lambda: running[0])
    bench.device("DUT", serial="SN-0042", firmware="2.3.1")
    bench.set("Ambient", "23.5 °C", section="Environment")
    bench.device("DUT", serial="SN-0042")  # the same value: no change
    running[0] = ("test_a.py::test_swap", 0)
    bench.device("DUT", serial="SN-0043")
    running[0] = ("test_a.py::test_swap", 2)
    bench.set("Ambient", "24.1 °C", section="Environment")
    running[0] = (None, 0)
    bench.instrument("DMM", cal_due="2027-01-01")
    bench.instrument("DMM", cal_due="2028-01-01")
    changes = bench.changes()
    assert [
        (c["nodeid"], c["attempt"], c["kind"], c["name"], c["label"], c["old"], c["new"])
        for c in changes
    ] == [
        ("test_a.py::test_swap", 0, "device", "DUT", "serial", "SN-0042", "SN-0043"),
        ("test_a.py::test_swap", 2, "section", "Environment", "Ambient", "23.5 °C", "24.1 °C"),
        (None, 0, "instrument", "DMM", "cal_due", "2027-01-01", "2028-01-01"),
    ]
    assert all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z", c["at"]) for c in changes)
    assert len(bench.changes("test_a.py::test_swap")) == 2
    assert [c["label"] for c in bench.changes("test_a.py::test_swap", 2)] == ["Ambient"]
    assert bench.changes("test_a.py::test_other") == []
    assert bench.document(TODAY)["devices"][0]["serial"] == "SN-0043"
    assert _bench.change_text(changes[0]) == "device DUT serial: SN-0042 -> SN-0043"
    assert _bench.change_text(changes[1]) == ("Environment / Ambient: 23.5 °C -> 24.1 °C (retry 2)")


def test_one_and_true_are_different_facts() -> None:
    bench = _recording()
    bench.set("Channels", 1)
    bench.set("Channels", True)
    bench.set("Channels", True)
    assert [(c["old"], c["new"]) for c in bench.changes()] == [(1, True)]


@pytest.mark.parametrize(
    ("call", "error", "words"),
    [
        (lambda b: b.set("", "x"), ValueError, "label must not be blank"),
        (lambda b: b.set("   ", "x"), ValueError, "label must not be blank"),
        (lambda b: b.set(3, "x"), TypeError, "label must be a str, not int"),
        (lambda b: b.set("Site", "x", section=" "), ValueError, "section must not be blank"),
        (lambda b: b.set("Site", "x", section=None), TypeError, "section must be a str"),
        (lambda b: b.set("Site", ["Lab"]), TypeError, "the value of 'Site' must be a str, int"),
        (lambda b: b.set("Site", object()), TypeError, "not object"),
        (lambda b: b.update([("Site", "Lab")]), TypeError, "values must be a mapping, not list"),
        (lambda b: b.update({1: "x"}), TypeError, "label must be a str"),
        (lambda b: b.device(""), ValueError, "name must not be blank"),
        (lambda b: b.device(None), TypeError, "name must be a str, not NoneType"),
        (lambda b: b.device("DUT", serial={"a": 1}), TypeError, "serial of 'DUT' must be"),
        (lambda b: b.device("DUT", lot=b"22"), TypeError, "lot of 'DUT' must be"),
        (lambda b: b.instrument(" "), ValueError, "name must not be blank"),
        (lambda b: b.instrument("DMM", idn=5), TypeError, "idn must be a str, not int"),
        (
            lambda b: b.instrument("DMM", cal_due="next March"),
            ValueError,
            "cal_due must be a date as YYYY-MM-DD, not 'next March'",
        ),
        (lambda b: b.instrument("DMM", cal_due="2026-02-30"), ValueError, "cal_due must be"),
        (lambda b: b.instrument("DMM", cal_due="20260302"), ValueError, "cal_due must be"),
        (lambda b: b.instrument("DMM", calibrated=20260302), TypeError, "calibrated must be"),
        (lambda b: b.instrument("DMM", asset=("a",)), TypeError, "asset of 'DMM' must be"),
    ],
)
@pytest.mark.parametrize("saves", [True, False], ids=["report-dir", "no-report-dir"])
def test_usage_errors(call: Any, error: type[Exception], words: str, saves: bool) -> None:  # noqa: ANN401
    """A wrong call raises where it is made, also when nothing is saved."""
    bench = _recording() if saves else BenchInfo()
    with pytest.raises(error, match=re.escape(words)):
        call(bench)
    assert bench.empty


def test_without_report_dir_nothing_is_kept() -> None:
    bench = BenchInfo()
    bench.set("Site", "Lab 2")
    bench.device("DUT", serial="SN-1")
    bench.device("DUT", serial="SN-2")
    bench.instrument("DMM", idn=IDN, cal_due="2020-01-01")
    assert bench.empty
    assert bench.changes() == []
    assert bench.overdue(TODAY) == []
    assert _bench.is_empty(bench.document(TODAY))
    assert _bench.html_data(bench.document(TODAY)) is None


def test_junit_properties_in_order_with_the_old_metadata() -> None:
    bench = _recording()
    bench.set("Site", "Lab 2")
    bench.set("Ambient", "23.5 °C", section="Environment")
    bench.device("DUT", serial="SN-0042", shielded=True)
    bench.instrument("DMM", cal_due="2020-01-01")
    document = bench.document(TODAY, {"CI": {"Build": "42"}, "Empty": {}})
    assert document["metadata"] == {"CI": {"Build": "42"}}
    assert _bench.junit_properties(document) == [
        ("bench.Bench.Site", "Lab 2"),
        ("bench.Environment.Ambient", "23.5 °C"),
        ("bench.device.DUT.serial", "SN-0042"),
        ("bench.device.DUT.shielded", "true"),
        ("bench.instrument.DMM.cal_due", "2020-01-01"),
        ("bench.instrument.DMM.overdue", "true"),
        ("metadata.CI.Build", "42"),
    ]


def test_text_xml_cannot_hold_is_replaced() -> None:
    bench = _recording()
    bench.instrument("DMM", idn="ACME,X1\x00\x1b[0m,7,1.0\ufffe")
    properties = dict(_bench.junit_properties(bench.document(TODAY)))
    assert properties["bench.instrument.DMM.idn"] == "ACME,X1??[0m,7,1.0?"
    assert _bench.xml_text("tab\there\nand é 🔧") == "tab\there\nand é 🔧"


def test_html_data_keeps_big_integers_exact_and_leaves_metadata_out() -> None:
    bench = _recording()
    bench.set("Base address", 2**64 - 1)
    bench.set("Slot", 3)
    data = _bench.html_data(bench.document(TODAY, {"CI": {"Build": "42"}}))
    assert data is not None
    assert data["sections"]["Bench"] == {
        "Base address": {"$repr": "18446744073709551615"},
        "Slot": 3,
    }
    assert "metadata" not in data
    assert _bench.html_data(_recording().document(TODAY, {"CI": {"Build": "42"}})) is None


def test_bench_info_is_exported_and_described() -> None:
    import pytest_reporter

    assert "BenchInfo" in pytest_reporter.__all__
    bench = _recording()
    bench.device("DUT", serial="SN-1")
    assert repr(bench) == "<BenchInfo: 1 devices, 0 instruments, 0 rows>"
    for method in (BenchInfo.set, BenchInfo.update, BenchInfo.device, BenchInfo.instrument):
        assert method.__doc__ and "Args:" in method.__doc__ and "Raises:" in method.__doc__


# ---------------------------------------------------------------------------
# The plugin, end to end
# ---------------------------------------------------------------------------

CONFTEST = f"""
import pytest

def pytest_reporter_bench(config, bench):
    bench.set("Site", "Lab 2")

@pytest.fixture(scope="session", autouse=True)
def bench(report_bench):
    report_bench.device("DUT", serial="SN-0042", firmware="2.3.1", hardware="rev C")
    report_bench.instrument("DMM", idn="{IDN}", calibrated="2025-03-02", cal_due="2026-03-02")
    report_bench.instrument("PSU", cal_due="2999-01-01")
    report_bench.set("Fixture board", "FB-12")
    report_bench.set("Ambient", "23.5 °C", section="Environment")
"""

TESTS = """
def test_first():
    pass

def test_second_board(report_bench):
    report_bench.device("DUT", serial="SN-0043")

def test_last():
    pass
"""


def _run_dir(pytester: Pytester) -> Path:
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    assert runs, "no run folder"
    return runs[-1]


def _data(run_dir: Path) -> dict[str, Any]:
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="report-data">(.*?)</script>', html, re.DOTALL
    )
    assert match
    data: dict[str, Any] = json.loads(match.group(1))
    return data


def _properties(element: ET.Element) -> list[ET.Element]:
    found = element.find("properties")
    return [] if found is None else list(found)


def _runs(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {run["nodeid"]: run for test in data["tests"] for run in test["runs"]}


def test_bench_json_junit_and_report_data(pytester: Pytester) -> None:
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(test_b=TESTS)
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=3, warnings=1)
    result.stdout.fnmatch_lines(
        [
            "*UserWarning: pytest-reporter: instrument 'DMM' calibration was due 2026-03-02",
            "*Bench: instrument 'DMM' calibration was due 2026-03-02",
        ]
    )
    assert result.stdout.str().count("UserWarning: pytest-reporter: instrument") == 1
    run_dir = _run_dir(pytester)

    document = json.loads((run_dir / "bench.json").read_text(encoding="utf-8"))
    assert document["run_date"] == datetime.date.today().isoformat()
    assert document["sections"] == {
        "Bench": {"Site": "Lab 2", "Fixture board": "FB-12"},
        "Environment": {"Ambient": "23.5 °C"},
    }
    assert document["devices"] == [
        {"name": "DUT", "serial": "SN-0043", "firmware": "2.3.1", "hardware": "rev C"}
    ]
    dmm, psu = document["instruments"]
    assert (dmm["name"], dmm["model"], dmm["cal_due"], dmm["overdue"]) == (
        "DMM",
        "34465A",
        "2026-03-02",
        True,
    )
    assert psu == {"name": "PSU", "cal_due": "2999-01-01", "overdue": False}
    (change,) = document["changes"]
    assert {k: change[k] for k in ("nodeid", "attempt", "kind", "name", "label", "old", "new")} == {
        "nodeid": "test_b.py::test_second_board",
        "attempt": 0,
        "kind": "device",
        "name": "DUT",
        "label": "serial",
        "old": "SN-0042",
        "new": "SN-0043",
    }
    assert document["metadata"] == {}
    # 01_latest is a copy of the run folder
    latest = pytester.path / "reports" / "01_latest" / "bench.json"
    assert json.loads(latest.read_text(encoding="utf-8")) == document

    suite = ET.parse(run_dir / "junit.xml").getroot().find("testsuite")
    assert suite is not None
    # The junit schema: a testsuite's properties come before its testcases
    assert [child.tag for child in suite][:2] == ["properties", "testcase"]
    properties = [(p.get("name"), p.get("value")) for p in _properties(suite)]
    assert properties[:5] == [
        ("bench.Bench.Site", "Lab 2"),
        ("bench.Bench.Fixture board", "FB-12"),
        ("bench.Environment.Ambient", "23.5 °C"),
        ("bench.device.DUT.serial", "SN-0043"),
        ("bench.device.DUT.firmware", "2.3.1"),
    ]
    assert ("bench.instrument.DMM.overdue", "true") in properties
    assert ("bench.instrument.DMM.idn", IDN) in properties
    cases = {case.get("name"): case for case in suite.findall("testcase")}
    changed = cases["test_second_board"].find("properties")
    assert changed is not None
    assert [(p.get("name"), p.get("value")) for p in changed] == [
        ("bench.changed", "device DUT serial: SN-0042 -> SN-0043")
    ]
    assert cases["test_first"].find("properties") is None

    data = _data(run_dir)
    assert data["bench"]["devices"] == document["devices"]
    assert data["bench"]["instruments"] == document["instruments"]
    assert data["bench"]["sections"] == document["sections"]
    assert data["bench"]["changes"] == document["changes"]
    assert "metadata" not in data["bench"]
    runs = _runs(data)
    assert [c["new"] for c in runs["test_b.py::test_second_board"]["bench_changes"]] == ["SN-0043"]
    assert runs["test_b.py::test_first"]["bench_changes"] == []
    assert runs["test_b.py::test_last"]["bench_changes"] == []


def test_nothing_recorded_writes_no_file(pytester: Pytester) -> None:
    pytester.makepyfile("def test_one(): pass")
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1)
    run_dir = _run_dir(pytester)
    assert not (run_dir / "bench.json").exists()
    assert _data(run_dir)["bench"] is None
    suite = ET.parse(run_dir / "junit.xml").getroot().find("testsuite")
    assert suite is not None and suite.find("properties") is None
    assert "Bench:" not in result.stdout.str()


def test_old_metadata_is_folded_in(pytester: Pytester) -> None:
    """``report_metadata`` and the metadata hook reach bench.json and junit.xml too."""
    pytester.makeconftest(
        """
        import pytest

        def pytest_reporter_metadata():
            return {"CI": {"Build": "42"}}

        @pytest.fixture(scope="session", autouse=True)
        def _meta(report_metadata):
            report_metadata.setdefault("DUT", {})["Serial"] = "SN-001"
        """
    )
    pytester.makepyfile("def test_one(): pass")
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    run_dir = _run_dir(pytester)
    document = json.loads((run_dir / "bench.json").read_text(encoding="utf-8"))
    assert document["metadata"] == {"CI": {"Build": "42"}, "DUT": {"Serial": "SN-001"}}
    assert document["devices"] == [] and document["sections"] == {}
    suite = ET.parse(run_dir / "junit.xml").getroot().find("testsuite")
    assert suite is not None
    assert [(p.get("name"), p.get("value")) for p in _properties(suite)] == [
        ("metadata.CI.Build", "42"),
        ("metadata.DUT.Serial", "SN-001"),
    ]
    data = _data(run_dir)
    # The System Data panel still shows them; the Bench section has nothing to show
    assert data["system_metadata"] == document["metadata"]
    assert data["bench"] is None
    assert "System Data" in (run_dir / "report.html").read_text(encoding="utf-8")


def test_changes_belong_to_the_retry_attempt_that_made_them(pytester: Pytester) -> None:
    pytester.makeconftest(
        """
        def pytest_reporter_bench(config, bench):
            bench.device("DUT", serial="SN-0")
        """
    )
    pytester.makepyfile(
        test_r="""
        TRIES = []

        def test_flaky(report_bench):
            TRIES.append(1)
            report_bench.device("DUT", serial=f"SN-{len(TRIES)}")
            assert len(TRIES) == 3

        def test_after():
            pass
        """
    )
    pytester.runpytest("--report-dir=reports", "--report-retries=3").assert_outcomes(passed=2)
    run_dir = _run_dir(pytester)
    document = json.loads((run_dir / "bench.json").read_text(encoding="utf-8"))
    assert [(c["attempt"], c["old"], c["new"]) for c in document["changes"]] == [
        (0, "SN-0", "SN-1"),
        (1, "SN-1", "SN-2"),
        (2, "SN-2", "SN-3"),
    ]
    assert {c["nodeid"] for c in document["changes"]} == {"test_r.py::test_flaky"}
    run = _runs(_data(run_dir))["test_r.py::test_flaky"]
    assert [c["new"] for c in run["bench_changes"]] == ["SN-1"]
    attempts = {a["attempt"]: a for a in run["retry_attempts"]}
    assert [c["new"] for c in attempts["01"]["bench_changes"]] == ["SN-2"]
    assert [c["new"] for c in attempts["02"]["bench_changes"]] == ["SN-3"]
    suite = ET.parse(run_dir / "junit.xml").getroot().find("testsuite")
    assert suite is not None
    case = next(c for c in suite.findall("testcase") if c.get("name") == "test_flaky")
    properties = [(p.get("name"), p.get("value")) for p in _properties(case)]
    assert properties == [
        ("bench.changed", "device DUT serial: SN-0 -> SN-1"),
        ("bench.changed", "device DUT serial: SN-1 -> SN-2 (retry 1)"),
        ("bench.changed", "device DUT serial: SN-2 -> SN-3 (retry 2)"),
        ("retries", "2"),
        ("original_outcome", "failed"),
    ]


def test_a_change_in_fixture_teardown_belongs_to_its_test(pytester: Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest

        def pytest_reporter_bench(config, bench):
            bench.set("Relay", "open")

        @pytest.fixture
        def relay(report_bench):
            report_bench.set("Relay", "closed")
            yield
            report_bench.set("Relay", "open")
        """
    )
    pytester.makepyfile(test_t="def test_one(relay): pass\ndef test_two(): pass\n")
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=2)
    document = json.loads((_run_dir(pytester) / "bench.json").read_text(encoding="utf-8"))
    assert [(c["nodeid"], c["new"]) for c in document["changes"]] == [
        ("test_t.py::test_one", "closed"),
        ("test_t.py::test_one", "open"),
    ]


def test_usage_error_fails_the_test_with_and_without_report_dir(pytester: Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        def test_blank(report_bench):
            with pytest.raises(ValueError, match="label must not be blank"):
                report_bench.set(" ", "x")
            with pytest.raises(TypeError, match="must be a str, int, float, bool"):
                report_bench.device("DUT", serial=[1])
            with pytest.raises(ValueError, match="cal_due must be a date"):
                report_bench.instrument("DMM", cal_due="soon")

        def test_unchecked(report_bench):
            report_bench.set("", "x")
        """
    )
    for args in (["--report-dir=reports"], []):
        result = pytester.runpytest(*args)
        result.assert_outcomes(passed=1, failed=1)
        result.stdout.fnmatch_lines(["*ValueError: label must not be blank*"])
    assert not (_run_dir(pytester) / "bench.json").exists()


def test_without_report_dir_the_fixture_saves_nothing(pytester: Pytester) -> None:
    pytester.makeconftest(
        """
        CALLED = []

        def pytest_reporter_bench(config, bench):
            CALLED.append(1)

        def pytest_sessionfinish(session):
            assert CALLED == [], "the hook is only called with --report-dir"
        """
    )
    pytester.makepyfile(
        """
        from pytest_reporter import BenchInfo

        def test_one(report_bench):
            assert isinstance(report_bench, BenchInfo)
            report_bench.instrument("DMM", cal_due="2000-01-01")
            assert report_bench.empty
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    assert "calibration was due" not in result.stdout.str()
    assert not (pytester.path / "reports").exists()


def test_a_raising_hook_is_a_warning_and_the_others_still_record(pytester: Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest

        pytest_plugins = ["other_bench"]

        def pytest_reporter_bench(config, bench):
            bench.set("Before", "kept")
            raise RuntimeError("no bus")
        """
    )
    pytester.makepyfile(
        other_bench="""
        import pytest

        def pytest_reporter_bench(bench):
            bench.set("Site", "Lab 2")

        class Skipper:
            def pytest_reporter_bench(self, config, bench):
                pytest.skip("not here")

        def pytest_configure(config):
            config.pluginmanager.register(Skipper(), "skipper")
        """
    )
    pytester.makepyfile("def test_one(): pass")
    result = pytester.runpytest("--report-dir=reports")
    result.assert_outcomes(passed=1, warnings=2)
    result.stdout.fnmatch_lines(
        [
            "*pytest-reporter: pytest_reporter_bench of skipper failed and was skipped: "
            "Skipped: not here",
            "*pytest-reporter: pytest_reporter_bench of * failed and was skipped: "
            "RuntimeError: no bus",
        ]
    )
    document = json.loads((_run_dir(pytester) / "bench.json").read_text(encoding="utf-8"))
    assert document["sections"] == {"Bench": {"Site": "Lab 2", "Before": "kept"}}


def test_overdue_never_changes_an_outcome_even_with_warnings_as_errors(
    pytester: Pytester,
) -> None:
    pytester.makeconftest(
        """
        def pytest_reporter_bench(config, bench):
            bench.instrument("DMM", cal_due="2001-02-03")
        """
    )
    pytester.makepyfile("def test_one(): pass")
    result = pytester.runpytest("--report-dir=reports", "-W", "error")
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*Bench: instrument 'DMM' calibration was due 2001-02-03"])
    run_dir = _run_dir(pytester)
    assert (run_dir / "report.html").exists()
    assert json.loads((run_dir / "bench.json").read_text(encoding="utf-8"))["instruments"][0][
        "overdue"
    ]


def test_bench_json_is_written_when_the_html_build_fails(pytester: Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest_reporter.reporter as rr

        def _boom(*args, **kwargs):
            raise RuntimeError("no report today")

        def pytest_configure(config):
            rr.build_html_data = _boom

        def pytest_reporter_bench(config, bench):
            bench.device("DUT", serial="SN-0042")
        """
    )
    pytester.makepyfile("def test_one(): pass")
    # A subprocess: the patch must not outlive this test
    result = pytester.runpytest_subprocess("--report-dir=reports")
    result.assert_outcomes(passed=1, warnings=1)
    run_dir = _run_dir(pytester)
    document = json.loads((run_dir / "bench.json").read_text(encoding="utf-8"))
    assert document["devices"] == [{"name": "DUT", "serial": "SN-0042"}]
    junit = (run_dir / "junit.xml").read_text(encoding="utf-8")
    assert 'name="bench.device.DUT.serial" value="SN-0042"' in junit
    assert (pytester.path / "reports" / "01_latest" / "bench.json").exists()


def test_untrusted_text_stays_text_in_the_report(pytester: Pytester) -> None:
    """An instrument's reply is data: never markup, in the page or in junit.xml."""
    pytester.makeconftest(
        """
        def pytest_reporter_bench(config, bench):
            bench.instrument("DMM", idn="<img src=x onerror=alert(1)></script>,M&M,\\"7\\",1")
            bench.set("Big", 2**64)
        """
    )
    pytester.makepyfile("def test_one(): pass")
    pytester.runpytest("--report-dir=reports").assert_outcomes(passed=1)
    run_dir = _run_dir(pytester)
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "<img src=x" not in html
    data = _data(run_dir)
    assert (
        data["bench"]["instruments"][0]["manufacturer"] == "<img src=x onerror=alert(1)></script>"
    )
    assert data["bench"]["sections"]["Bench"]["Big"] == {"$repr": "18446744073709551616"}
    assert (
        json.loads((run_dir / "bench.json").read_text(encoding="utf-8"))["sections"]["Bench"]["Big"]
        == 2**64
    )
    suite = ET.parse(run_dir / "junit.xml").getroot().find("testsuite")
    assert suite is not None
    values = {p.get("name"): p.get("value") for p in _properties(suite)}
    assert values["bench.instrument.DMM.model"] == "M&M"
    assert values["bench.Bench.Big"] == "18446744073709551616"


# ---------------------------------------------------------------------------
# The report's renderers (Node)
# ---------------------------------------------------------------------------

_DOM = """
const window = {};
function Node(tag) {
  this.tag = tag; this.children = []; this.className = ''; this.attrs = {}; this.listeners = {};
}
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
Node.prototype.addEventListener = function (k, f) { this.listeners[k] = f; };
Object.defineProperty(Node.prototype, 'firstChild', { get() { return this.children[0] || null; } });
Object.defineProperty(Node.prototype, 'textContent', {
  get() { return this.text !== undefined ? this.text
                 : this.children.map(c => c.textContent).join(''); },
  set(v) { this.text = String(v); this.children = []; },
});
Object.defineProperty(Node.prototype, 'innerHTML', { set(v) { this.html = String(v); } });
const document = {
  createElement: tag => new Node(tag),
  createElementNS: (ns, tag) => new Node(tag),
  createTextNode: text => { const n = new Node('#text'); n.text = String(text); return n; },
  getElementById: () => null,
};
function findAll(node, cls, out) {
  out = out || [];
  if ((' ' + node.className + ' ').includes(' ' + cls + ' ')) out.push(node);
  node.children.forEach(c => findAll(c, cls, out));
  return out;
}
function byTag(node, tag, out) {
  out = out || [];
  if (node.tag === tag) out.push(node);
  node.children.forEach(c => byTag(c, tag, out));
  return out;
}
const texts = (node, cls) => findAll(node, cls).map(n => n.textContent);
let _n = 0;
function uid(prefix) { return prefix + (++_n); }
const opened = [];
function openRunInTests(test, run) { opened.push(run.nodeid); }
function switchTab(name) { opened.push('tab:' + name); }
"""

_FUNCTIONS = (
    "el",
    "srText",
    "benchValue",
    "benchKeyLabel",
    "overdueInstruments",
    "benchColumns",
    "benchCellClass",
    "renderBenchTable",
    "benchChangeWhat",
    "benchChangeEl",
    "openBenchTest",
    "renderBenchChanges",
    "renderBenchSection",
    "renderBenchNotice",
    "stickyTop",
    "showBenchSection",
)


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    end = JS.index("\nfunction ", start + 1)
    return JS[start:end].split("\n// ───")[0]


def _node(data: dict[str, Any], script: str) -> Any:  # noqa: ANN401
    source = "\n".join(
        [
            _DOM,
            f"const DATA = {json.dumps(data)};",
            *(_function(n) for n in _FUNCTIONS),
            script,
        ]
    )
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


CHANGE = {
    "at": "2026-11-19T15:43:56.862606Z",
    "nodeid": "test_b.py::test_second_board",
    "attempt": 0,
    "kind": "device",
    "name": "DUT",
    "label": "serial",
    "old": "SN-0042",
    "new": "SN-0043",
}

BENCH: dict[str, Any] = {
    "run_date": "2026-11-19",
    "sections": {
        "Bench": {"Site": "Lab 2", "Base": {"$repr": "18446744073709551615"}, "Shielded": True},
        "Environment": {"Ambient": "23.5 °C"},
    },
    "devices": [{"name": "DUT", "serial": "SN-0043", "firmware": "2.3.1", "lot_code": "2231"}],
    "instruments": [
        {
            "name": "DMM",
            "idn": IDN,
            "manufacturer": "Keysight Technologies",
            "model": "34465A",
            "serial": "MY53001234",
            "firmware": "A.03.01-03.15",
            "calibrated": "2025-03-02",
            "cal_due": "2026-03-02",
            "overdue": True,
        },
        {"name": "PSU", "cal_due": "2027-06-10", "overdue": False, "asset": "LAB-0031"},
    ],
    "changes": [
        CHANGE,
        {**CHANGE, "attempt": 2, "kind": "section", "name": "Environment", "label": "Ambient"},
        {**CHANGE, "nodeid": None, "old": "<b>x</b>", "new": 7},
    ],
}

_TESTS = [{"runs": [{"nodeid": "test_b.py::test_second_board"}]}]


@requires_node
def test_bench_section_shows_devices_instruments_rows_and_history() -> None:
    out = _node(
        {"bench": BENCH, "tests": _TESTS},
        """
        const s = renderBenchSection();
        const tables = byTag(s, 'table');
        const cells = t => byTag(t, 'tr').map(r => r.children.map(c => c.textContent));
        const history = byTag(s, 'details')[0];
        byTag(history, 'button')[0].listeners.click();
        console.log(JSON.stringify({
          id: s.attrs.id,
          groups: texts(s, 'bench-group-title'),
          devices: cells(tables[0]), instruments: cells(tables[1]),
          overdueRows: findAll(s, 'overdue').filter(n => n.tag === 'tr').length,
          labels: byTag(tables[1], 'td').slice(0, 3).map(c => c.attrs['data-label']),
          rows: findAll(s, 'report-info-row').map(r => r.children.map(c => c.textContent)),
          summary: byTag(history, 'summary')[0].textContent,
          open: history.attrs.open ?? null,
          changes: byTag(history, 'li').map(li => li.children.map(c => c.textContent)),
          opened: opened,
        }));
        """,
    )
    assert out["id"] == "bench-section"
    assert out["groups"] == ["Devices", "Instruments", "Bench", "Environment"]
    assert out["devices"] == [
        ["Name", "Serial", "Firmware", "Lot code"],
        ["DUT", "SN-0043", "2.3.1", "2231"],
    ]
    # Maker and model share a column; the raw reply is left out when it was split
    assert out["instruments"] == [
        ["Name", "Model", "Serial", "Calibrated", "Cal due", "Firmware", "Asset"],
        [
            "DMM",
            "Keysight Technologies 34465A",
            "MY53001234",
            "2025-03-02",
            "2026-03-02overdue",
            "A.03.01-03.15",
            "\u2014",
        ],
        ["PSU", "\u2014", "\u2014", "\u2014", "2027-06-10", "\u2014", "LAB-0031"],
    ]
    assert out["overdueRows"] == 1
    assert out["labels"] == ["Model", "Serial", "Calibrated"]
    assert out["rows"] == [
        ["Site", "Lab 2"],
        ["Base", "18446744073709551615"],
        ["Shielded", "yes"],
        ["Ambient", "23.5 °C"],
    ]
    assert out["summary"] == "Change history (3)"
    assert out["open"] is None  # closed until asked for
    assert out["changes"] == [
        [
            "DUT serial",
            "SN-0042\u2192 changed to SN-0043",
            "test_b.py::test_second_board",
            "15:43:56 UTC",
        ],
        [
            "Environment / Ambient",
            "SN-0042\u2192 changed to SN-0043",
            "test_b.py::test_second_board, retry 2",
            "15:43:56 UTC",
        ],
        ["DUT serial", "<b>x</b>\u2192 changed to 7", "between tests", "15:43:56 UTC"],
    ]
    assert out["opened"] == ["test_b.py::test_second_board"]


@requires_node
def test_an_unsplit_idn_gets_its_own_column() -> None:
    bench = {"instruments": [{"name": "Probe", "idn": "P6139B", "overdue": False}]}
    out = _node(
        {"bench": bench, "tests": []},
        """
        const s = renderBenchSection();
        console.log(JSON.stringify(byTag(s, 'tr').map(r => r.children.map(c => c.textContent))));
        """,
    )
    assert out == [["Name", "*IDN?"], ["Probe", "P6139B"]]


@requires_node
def test_no_bench_data_no_section_and_no_notice() -> None:
    out = _node(
        {"bench": None, "tests": []},
        "console.log(JSON.stringify([renderBenchSection(), renderBenchNotice(),"
        " renderBenchChanges([]), renderBenchChanges(undefined)]));",
    )
    assert out == [None, None, None, None]


@requires_node
def test_overdue_notice_names_the_instruments_and_opens_the_report_tab() -> None:
    late = [{"name": f"I{n}", "cal_due": f"2026-0{n}-01", "overdue": True} for n in range(1, 6)]
    out = _node(
        {"bench": {"instruments": [*late, {"name": "OK", "overdue": False}]}, "tests": []},
        """
        const n = renderBenchNotice();
        byTag(n, 'button')[0].listeners.click();
        console.log(JSON.stringify({cls: n.className, role: n.attrs.role,
          text: texts(n, 'bench-notice-text')[0], button: byTag(n, 'button')[0].textContent,
          opened: opened}));
        """,
    )
    assert out["cls"] == "bench-notice"
    assert out["role"] == "note"
    assert out["text"] == (
        "Calibration overdue I1 (due 2026-01-01), I2 (due 2026-02-01), "
        "I3 (due 2026-03-01) and 2 more"
    )
    assert out["button"] == "Bench details"
    assert out["opened"] == ["tab:report"]


@requires_node
def test_a_tests_own_changes_block() -> None:
    out = _node(
        {"bench": BENCH, "tests": []},
        f"""
        const own = renderBenchChanges([{json.dumps(CHANGE)}]);
        const attempt = renderBenchChanges([{json.dumps(CHANGE)}], 'Bench changed in this attempt');
        console.log(JSON.stringify({{
          title: byTag(own, 'h4')[0].textContent,
          labelled: own.attrs['aria-labelledby'] === byTag(own, 'h4')[0].attrs.id,
          rows: byTag(own, 'li').map(li => li.children.map(c => c.textContent)),
          buttons: byTag(own, 'button').length,
          attempt: byTag(attempt, 'h4')[0].textContent,
        }}));
        """,
    )
    assert out["title"] == "Bench changed in this test"
    assert out["labelled"] is True
    # The test is the one on screen: no link to it, only what changed and when
    assert out["rows"] == [["DUT serial", "SN-0042\u2192 changed to SN-0043", "15:43:56 UTC"]]
    assert out["buttons"] == 0
    assert out["attempt"] == "Bench changed in this attempt"


def test_bench_text_is_never_set_as_html() -> None:
    """Every bench renderer builds text nodes; only our own icons are markup."""
    for name in _FUNCTIONS[2:]:
        body = _function(name)
        assert "insertAdjacentHTML" not in body
        for line in body.splitlines():
            if "innerHTML" in line:
                assert "innerHTML = '<svg" in line, line


def test_report_wires_the_bench_views() -> None:
    assert "renderBenchSection()" in _function("renderReport")
    assert "renderBenchNotice()" in _function("renderSummary")
    sub_tab = _function("showSubTab")
    assert "renderBenchChanges(run.bench_changes)" in sub_tab
    assert "renderBenchChanges(attempt.bench_changes, 'Bench changed in this attempt')" in sub_tab


def test_under_xdist_the_hook_records_and_worker_fixtures_do_not(pytester: Pytester) -> None:
    """The controller writes the report: only what runs there reaches it."""
    pytest.importorskip("xdist")
    pytester.makeconftest(
        """
        import pytest

        def pytest_reporter_bench(config, bench):
            bench.device("DUT", serial="SN-0042")

        @pytest.fixture(scope="session", autouse=True)
        def _bench(report_bench):
            report_bench.set("From a worker", "lost")
            assert report_bench.empty
        """
    )
    pytester.makepyfile("def test_one(): pass\ndef test_two(): pass\n")
    result = pytester.runpytest_subprocess("--report-dir=reports", "-n", "2")
    result.assert_outcomes(passed=2)
    document = json.loads((_run_dir(pytester) / "bench.json").read_text(encoding="utf-8"))
    assert document["devices"] == [{"name": "DUT", "serial": "SN-0042"}]
    assert document["sections"] == {}


# ---------------------------------------------------------------------------
# Review fixes
# ---------------------------------------------------------------------------


def test_a_subclass_value_is_stored_plain_for_every_output() -> None:
    """A str or int enum member reads the same in bench.json, junit.xml and the report."""
    import enum

    class Rev(str, enum.Enum):  # noqa: UP042 - str() of this one is 'Rev.C'
        C = "rev C"

    class Slot(enum.IntEnum):
        THREE = 3

    class Gain(float):
        def __str__(self) -> str:
            return "gain!"

    bench = _recording()
    bench.device("DUT", hardware=Rev.C, slot=Slot.THREE)
    bench.set("Board", Rev.C)
    bench.set("Gain", Gain(1.5))
    bench.device("DUT", hardware=Rev.C)  # the same fact again: no change
    bench.device("DUT", hardware="rev D")
    document = bench.document(TODAY)
    device = document["devices"][0]
    assert device == {"name": "DUT", "hardware": "rev D", "slot": 3}
    assert type(device["slot"]) is int
    assert type(document["sections"]["Bench"]["Board"]) is str
    assert type(document["sections"]["Bench"]["Gain"]) is float
    assert [(c["old"], c["new"]) for c in bench.changes()] == [("rev C", "rev D")]
    assert type(bench.changes()[0]["old"]) is str
    properties = dict(_bench.junit_properties(document))
    assert properties["bench.Bench.Board"] == "rev C"
    assert properties["bench.Bench.Gain"] == "1.5"
    assert properties["bench.device.DUT.slot"] == "3"
    assert _bench.change_text(bench.changes()[0]) == "device DUT hardware: rev C -> rev D"
    assert json.loads(json.dumps(document)) == document


def test_an_explicit_value_outlives_a_later_idn() -> None:
    """What was given by name stays; a later ``idn=`` fills only the other parts."""
    bench = _recording()
    bench.instrument("X", idn="A,B,C,D", serial="EXPL")
    bench.instrument("X", idn="A,B2,C2,D")
    (first,) = bench.document(TODAY)["instruments"]
    assert first["serial"] == "EXPL"
    assert first["model"] == "B2"
    assert first["idn"] == "A,B2,C2,D"
    assert [(c["label"], c["old"], c["new"]) for c in bench.changes()] == [
        ("idn", "A,B,C,D", "A,B2,C2,D"),
        ("model", "B", "B2"),
    ]
    # Given by name after an idn: it replaces the idn's part, and stays
    bench.instrument("X", firmware="patched")
    bench.instrument("X", idn="A,B2,C2,D9")
    (later,) = bench.document(TODAY)["instruments"]
    assert later["firmware"] == "patched"
    assert later["serial"] == "EXPL"


def test_overdue_cannot_be_given() -> None:
    """``overdue`` is the report's own key of an instrument: giving it is a usage error."""
    for bench in (_recording(), BenchInfo()):
        with pytest.raises(ValueError, match="overdue is worked out from cal_due"):
            bench.instrument("DMM", cal_due="2026-03-02", overdue="mine")
        assert bench.empty
    # A device has no such key
    bench = _recording()
    bench.device("DUT", overdue="rent")
    assert bench.document(TODAY)["devices"] == [{"name": "DUT", "overdue": "rent"}]


def test_a_shared_fixture_run_again_for_a_retry_changes_nothing() -> None:
    """A session fixture set up again for a retry gives its first values: not a change."""
    state: dict[str, Any] = {"running": (None, 0), "shared": False}
    bench = _bench.recording(lambda: state["running"], lambda: state["shared"])

    def fixture(serial: str = "SN-0042") -> None:
        bench.device("DUT", serial=serial, firmware="2.3.1")
        bench.instrument("DMM", cal_due="2026-03-02")
        bench.set("Ambient", "23.5 °C", section="Environment")

    state.update(running=("t.py::test_a", 0), shared=True)
    fixture()
    state["shared"] = False
    bench.device("DUT", serial="SN-0044")
    bench.instrument("DMM", cal_due="2027-05-01")
    bench.set("Ambient", "25.0 °C", section="Environment")
    # The retry of the last test: pytest sets the session fixture up again
    state.update(running=("t.py::test_last", 1), shared=True)
    fixture()
    state["shared"] = False
    document = bench.document(TODAY)
    assert document["devices"] == [{"name": "DUT", "serial": "SN-0044", "firmware": "2.3.1"}]
    assert document["instruments"][0]["cal_due"] == "2027-05-01"
    assert document["sections"] == {"Environment": {"Ambient": "25.0 °C"}}
    assert {c["nodeid"] for c in bench.changes()} == {"t.py::test_a"}
    assert bench.overdue(TODAY) == []
    # A value the fixture did not give before is a change, by the retry that saw it
    state.update(running=("t.py::test_last", 2), shared=True)
    fixture(serial="SN-0050")
    state["shared"] = False
    assert bench.document(TODAY)["devices"][0]["serial"] == "SN-0050"
    assert [(c["nodeid"], c["attempt"], c["old"], c["new"]) for c in bench.changes()][-1] == (
        "t.py::test_last",
        2,
        "SN-0044",
        "SN-0050",
    )
    # Outside a shared fixture's setup a retry's call counts, whatever the value
    state.update(running=("t.py::test_last", 3), shared=False)
    bench.device("DUT", serial="SN-0042")
    assert bench.changes()[-1]["new"] == "SN-0042"


def test_a_retry_of_the_last_test_does_not_undo_the_bench(pytester: Pytester) -> None:
    """pytest sets session fixtures up again for a retry of the last test."""
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(
        test_b="""
        def test_change(report_bench):
            report_bench.device("DUT", serial="SN-0044", firmware="2.4.0")
            report_bench.instrument("DMM", cal_due="2999-05-01")
            report_bench.set("Ambient", "25.0 °C", section="Environment")

        def test_last():
            assert False
        """
    )
    result = pytester.runpytest("--report-dir=reports", "--report-retries=2")
    result.assert_outcomes(passed=1, failed=1)
    assert "calibration was due" not in result.stdout.str()
    run_dir = _run_dir(pytester)
    document = json.loads((run_dir / "bench.json").read_text(encoding="utf-8"))
    assert document["devices"][0]["serial"] == "SN-0044"
    assert document["devices"][0]["firmware"] == "2.4.0"
    assert document["instruments"][0]["cal_due"] == "2999-05-01"
    assert document["instruments"][0]["overdue"] is False
    assert document["sections"]["Environment"] == {"Ambient": "25.0 °C"}
    assert {c["nodeid"] for c in document["changes"]} == {"test_b.py::test_change"}
    run = _runs(_data(run_dir))["test_b.py::test_last"]
    assert run["bench_changes"] == []
    assert all("bench_changes" not in attempt for attempt in run["retry_attempts"])
    suite = ET.parse(run_dir / "junit.xml").getroot().find("testsuite")
    assert suite is not None
    case = next(c for c in suite.findall("testcase") if c.get("name") == "test_last")
    assert "bench.changed" not in [p.get("name") for p in _properties(case)]


def test_a_raising_metadata_hook_costs_no_file_with_warnings_as_errors(
    pytester: Pytester,
) -> None:
    """The metadata is collected before junit.xml: its warning must not stop the rest."""
    pytester.makeconftest(
        """
        import pytest

        def pytest_reporter_metadata():
            raise RuntimeError("meta boom")

        @pytest.fixture(scope="session", autouse=True)
        def _meta(report_metadata):
            report_metadata["Lab"] = {"Site": "Lab 2"}
        """
    )
    pytester.makepyfile("def test_one(): pass")
    result = pytester.runpytest("--report-dir=reports", "-W", "error")
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    run_dir = _run_dir(pytester)
    for name in ("junit.xml", "session.log.json", "pytest.log", "report.html", "bench.json"):
        assert (run_dir / name).exists(), name
    assert 'name="metadata.Lab.Site" value="Lab 2"' in (run_dir / "junit.xml").read_text(
        encoding="utf-8"
    )
    assert _data(run_dir)["system_metadata"] == {"Lab": {"Site": "Lab 2"}}
    result.stdout.fnmatch_lines(
        ["*Warning: pytest_reporter_metadata hook raised an exception and will be ignored: *boom"]
    )


def test_a_raising_bench_hook_is_still_named_with_warnings_as_errors(
    pytester: Pytester,
) -> None:
    pytester.makeconftest(
        """
        def pytest_reporter_bench(config, bench):
            bench.set("Before", "kept")
            bench.instrument("DMM", cal_due="never")
        """
    )
    pytester.makepyfile("def test_one(): pass")
    result = pytester.runpytest("--report-dir=reports", "-W", "error")
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        [
            "*Warning: pytest-reporter: pytest_reporter_bench of * failed and was skipped: "
            "ValueError: cal_due must be a date*",
        ]
    )
    document = json.loads((_run_dir(pytester) / "bench.json").read_text(encoding="utf-8"))
    assert document["sections"] == {"Bench": {"Before": "kept"}}
    # Without -W error the warning itself says it: no second line
    plain = pytester.runpytest("--report-dir=reports")
    plain.assert_outcomes(passed=1, warnings=1)
    assert "  Warning: pytest-reporter" not in plain.stdout.str()


@requires_node
def test_long_text_wraps_in_its_cell_and_the_dates_never_break() -> None:
    """One instrument's reply must not push the calibration dates out of view."""
    psu = {
        "name": "PSU with a name that goes on and on",
        "idn": "ACME," + "X" * 300 + ",SN-1," + "fw" * 200,
        "manufacturer": "ACME",
        "model": "X" * 300,
        "serial": "SN-1",
        "firmware": "fw" * 200,
        "cal_due": "2027-06-01",
        "overdue": False,
        "asset": "LAB-0031",
    }
    bench = {**BENCH, "instruments": [*BENCH["instruments"], psu]}
    out = _node(
        {"bench": bench, "tests": []},
        """
        const s = renderBenchSection();
        const table = byTag(s, 'table')[1];
        const rows = byTag(byTag(table, 'tbody')[0], 'tr');
        console.log(JSON.stringify({
          cells: rows[0].children.map(c => [c.attrs['data-label'] || 'Name', c.className]),
          devices: byTag(byTag(byTag(s, 'table')[0], 'tbody')[0], 'tr')[0]
            .children.map(c => c.className),
        }));
        """,
    )
    assert out["cells"] == [
        ["Name", "bench-wrap"],
        ["Model", "bench-wrap"],
        ["Serial", ""],
        ["Calibrated", "bench-date"],
        ["Cal due", "bench-date"],
        ["Firmware", "bench-wrap"],
        ["Asset", ""],
    ]
    assert out["devices"] == ["", "", "", ""]  # short values: nothing to wrap
    wrap = CSS[CSS.index(".bench-table td.bench-wrap, .bench-table tbody th.bench-wrap {") :]
    wrap = wrap[: wrap.index("}")]
    assert "max-width: 26em" in wrap
    assert "overflow-wrap: anywhere" in wrap
    assert ".bench-table td.bench-date, .bench-badge { white-space: nowrap; }" in CSS
    # Print: short cells break between words only, never a character per line
    printed = CSS[CSS.index("@media print {\n  .bench-table-wrap") :]
    printed = printed[: printed.index("\n}\n")]
    assert ".bench-table td.bench-date, .bench-badge { white-space: nowrap; }" in printed
    assert "overflow-wrap: break-word" in printed
    assert ".bench-table td { overflow-wrap: anywhere; }" not in printed


@requires_node
def test_bench_details_lands_below_the_sticky_bars() -> None:
    """The Summary notice's button shows the section's heading, not the header over it."""
    out = _node(
        {"bench": BENCH, "tests": []},
        """
        const bars = {
          '.header': {position: 'sticky', top: '0px', offsetHeight: 56},
          '.tabs': {position: 'sticky', top: '56px', offsetHeight: 43},
        };
        const calls = [];
        const section = {style: {},
          scrollIntoView(o) { calls.push(['scroll', this.style.scrollMarginTop, o.block]); },
          focus(o) { calls.push(['focus', o.preventScroll]); }};
        document.querySelectorAll = () => Object.values(bars);
        globalThis.getComputedStyle = bar => bar;
        document.getElementById = id => id === 'bench-section' ? section : null;
        const covered = stickyTop();
        showBenchSection();
        bars['.tabs'].position = 'static';
        bars['.header'].position = 'static';
        console.log(JSON.stringify({covered: covered, calls: calls, printed: stickyTop()}));
        """,
    )
    assert out["covered"] == 99
    assert out["calls"] == [["scroll", "111px", "start"], ["focus", True]]
    assert out["printed"] == 0
    assert "#bench-section { scroll-margin-top: 112px; }" in CSS
    # A click moves the focus there without :focus-visible: the outline says where
    assert "#bench-section:focus { outline: 2px solid var(--c-accent);" in CSS
