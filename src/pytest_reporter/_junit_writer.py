"""JUnit XML report writer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element, ElementTree, SubElement

if TYPE_CHECKING:
    from ._collector import DataCollector


def write_junit_xml(
    path: Path,
    collector: DataCollector,
    duration: float,
    *,
    retries_enabled: bool = False,
) -> None:
    """Write a standard JUnit XML report."""
    testsuites = Element("testsuites")
    testsuite = SubElement(testsuites, "testsuite", name="pytest")

    total = passed = failed = errors = skipped = 0

    for base_nodeid in collector.get_all_base_nodeids():
        for nodeid in collector.get_function_nodeids(base_nodeid):
            run_info = collector.get_run_info(nodeid)
            outcome = collector.get_outcome(nodeid)
            test_duration = collector.get_duration(nodeid)

            # classname: file path with dots instead of slashes, without .py
            classname = run_info.file_path.replace("/", ".").replace(".py", "")
            name = nodeid.split("::", 1)[1] if "::" in nodeid else nodeid

            tc = SubElement(
                testsuite,
                "testcase",
                classname=classname,
                name=name,
                time=f"{test_duration:.4f}",
            )

            # Add retry properties if applicable
            retry_data = collector.get_retry_data(nodeid)
            if retry_data and retry_data.attempts > 0:
                props = SubElement(tc, "properties")
                SubElement(
                    props, "property",
                    name="retries", value=str(retry_data.attempts),
                )
                SubElement(
                    props, "property",
                    name="original_outcome", value=retry_data.original_outcome,
                )

            total += 1
            if outcome == "passed":
                passed += 1
                # If passed after retries, include original failure in system-out
                if retry_data and retry_data.attempts > 0:
                    call_phase = collector.get_phase(nodeid, "call")
                    if call_phase and call_phase.longrepr:
                        so = SubElement(tc, "system-out")
                        so.text = f"Original failure (passed on retry {retry_data.attempts}):\n{call_phase.longrepr}"
            elif outcome == "failed":
                failed += 1
                # For retried tests, get the last attempt's failure
                call_phase = collector.get_phase(nodeid, "call")
                longrepr = call_phase.longrepr if call_phase else ""
                failure = SubElement(
                    tc, "failure", message=f"{name} failed", type="AssertionError"
                )
                failure.text = longrepr or ""
                # Include original failure in system-out for retried tests
                if retry_data and retry_data.attempts > 0 and call_phase and call_phase.longrepr:
                    so = SubElement(tc, "system-out")
                    so.text = f"Original failure:\n{call_phase.longrepr}"
            elif outcome == "skipped":
                skipped += 1
                setup_phase = collector.get_phase(nodeid, "setup")
                reason = setup_phase.longrepr if setup_phase else "skipped"
                skip_el = SubElement(tc, "skipped", message=str(reason))
                skip_el.text = str(reason)
            else:
                errors += 1
                setup_phase = collector.get_phase(nodeid, "setup")
                longrepr = setup_phase.longrepr if setup_phase else ""
                error_el = SubElement(
                    tc, "error", message=f"{name} error", type="Error"
                )
                error_el.text = longrepr or ""

    testsuite.set("tests", str(total))
    testsuite.set("failures", str(failed))
    testsuite.set("errors", str(errors))
    testsuite.set("skipped", str(skipped))
    testsuite.set("time", f"{duration:.4f}")

    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ElementTree(testsuites)
    tree.write(path, encoding="unicode", xml_declaration=True)
