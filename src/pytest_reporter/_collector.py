"""DataCollector -- item registry, phase tracking, and aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ._types import PhaseData, RetryData, RunEntry, RunInfo, TestLogJson

if TYPE_CHECKING:
    import pytest


class DataCollector:
    """Collects and indexes test data during the pytest run."""

    def __init__(self) -> None:
        # nodeid -> RunInfo
        self._run_map: dict[str, RunInfo] = {}
        # base_nodeid -> list of full nodeids (in collection order)
        self._function_runs: dict[str, list[str]] = {}
        # (nodeid, when) -> PhaseData
        self._phases: dict[tuple[str, str], PhaseData] = {}
        # nodeid -> RetryData (only for tests that were retried)
        self._retries: dict[str, RetryData] = {}

    def register_items(self, items: list[pytest.Item]) -> None:
        """Index all collected items and assign run IDs."""
        # First pass: count items per base nodeid
        base_counts: dict[str, int] = {}
        for item in items:
            base = item.nodeid.split("[")[0]
            base_counts[base] = base_counts.get(base, 0) + 1

        # Second pass: assign run IDs and extract metadata
        run_counters: dict[str, int] = {}
        for item in items:
            base = item.nodeid.split("[")[0]
            is_parametrized = hasattr(item, "callspec")

            if is_parametrized:
                run_counters[base] = run_counters.get(base, 0) + 1
                run_id = f"{run_counters[base]:02d}"
                parametrize_id = item.callspec.id  # type: ignore[attr-defined]
                params = dict(item.callspec.params)  # type: ignore[attr-defined]
            else:
                run_id = "default"
                parametrize_id = None
                params = {}

            # Parse nodeid into components
            path_part, _, func_part = item.nodeid.partition("::")
            func_name = func_part.split("[")[0]

            # Extract markers
            markers = [
                m.name
                for m in item.iter_markers()
                if m.name not in ("parametrize",)
            ]

            # Extract docstring
            docstring: str | None = None
            if hasattr(item, "function"):
                docstring = getattr(item.function, "__doc__", None)  # type: ignore[attr-defined]

            run_info = RunInfo(
                run_id=run_id,
                base_nodeid=base,
                parametrize_id=parametrize_id,
                params=params,
                function_name=func_name,
                file_path=path_part,
                module_parts=path_part.split("/"),
                docstring=docstring,
                markers=markers,
            )
            self._run_map[item.nodeid] = run_info

            if base not in self._function_runs:
                self._function_runs[base] = []
            self._function_runs[base].append(item.nodeid)

    def get_run_info(self, nodeid: str) -> RunInfo:
        """Look up run info for a nodeid."""
        return self._run_map[nodeid]

    def record_phase(self, report: Any, entries: list[dict[str, Any]] | None = None) -> None:
        """Record phase data from a TestReport."""
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Calculate start_time from end_time - duration
        end_time = now
        duration = report.duration
        start_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        from datetime import timedelta
        start_dt = start_dt - timedelta(seconds=duration)
        start_time = start_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        phase = PhaseData(
            when=report.when,
            outcome=report.outcome,
            duration=duration,
            longrepr=str(report.longrepr) if report.longrepr else None,
            start_time=start_time,
            end_time=end_time,
            entries=entries or [],
        )
        self._phases[(report.nodeid, report.when)] = phase

    def get_phase(self, nodeid: str, when: str) -> PhaseData | None:
        """Get phase data for a specific nodeid and phase."""
        return self._phases.get((nodeid, when))

    def get_phases(self, nodeid: str) -> dict[str, PhaseData]:
        """Get all phases for a nodeid."""
        result: dict[str, PhaseData] = {}
        for when in ("setup", "call", "teardown"):
            phase = self.get_phase(nodeid, when)
            if phase is not None:
                result[when] = phase
        return result

    def get_outcome(self, nodeid: str) -> str:
        """Derive final outcome for a test run from its phases."""
        # If retried, use final outcome from retry data
        retry = self._retries.get(nodeid)
        if retry and retry.history:
            return retry.history[-1]

        call = self.get_phase(nodeid, "call")
        setup = self.get_phase(nodeid, "setup")

        if setup and setup.outcome == "skipped":
            return "skipped"
        if call is None:
            if setup and setup.outcome == "failed":
                return "error"
            return "skipped"
        return call.outcome

    def get_duration(self, nodeid: str) -> float:
        """Get total duration for a test run across all phases."""
        total = 0.0
        for when in ("setup", "call", "teardown"):
            phase = self.get_phase(nodeid, when)
            if phase is not None:
                total += phase.duration

        # Add retry durations
        retry = self._retries.get(nodeid)
        if retry:
            for retry_phases_key in list(self._phases.keys()):
                nid, _ = retry_phases_key
                if nid.startswith(f"{nodeid}::retry::"):
                    phase = self._phases[retry_phases_key]
                    total += phase.duration
        return total

    def set_retry_data(self, nodeid: str, retry_data: RetryData) -> None:
        """Store retry metadata for a test run."""
        self._retries[nodeid] = retry_data

    def get_retry_data(self, nodeid: str) -> RetryData | None:
        """Get retry data for a test run, if any."""
        return self._retries.get(nodeid)

    def get_all_base_nodeids(self) -> list[str]:
        """Return all unique base nodeids (test functions)."""
        return list(self._function_runs.keys())

    def get_function_nodeids(self, base_nodeid: str) -> list[str]:
        """Return all nodeids for a given test function."""
        return self._function_runs.get(base_nodeid, [])

    def get_function_aggregate(self, base_nodeid: str) -> TestLogJson:
        """Build the test.log.json aggregate for a test function."""
        nodeids = self._function_runs.get(base_nodeid, [])
        runs: list[RunEntry] = []
        passed = failed = skipped = errors = 0
        total_duration = 0.0

        for nid in nodeids:
            run_info = self._run_map[nid]
            outcome = self.get_outcome(nid)
            duration = self.get_duration(nid)

            if outcome == "passed":
                passed += 1
            elif outcome == "failed":
                failed += 1
            elif outcome == "skipped":
                skipped += 1
            else:
                errors += 1

            total_duration += duration

            entry = RunEntry(
                run_id=run_info.run_id,
                outcome=outcome,
                duration_seconds=round(duration, 4),
            )

            # Add retries info if present
            retry = self._retries.get(nid)
            if retry and retry.attempts > 0:
                entry["retries"] = {
                    "attempts": retry.attempts,
                    "original_outcome": retry.original_outcome,
                    "history": retry.history,
                }

            runs.append(entry)

        # Get file/function from first run
        first = self._run_map[nodeids[0]]

        return TestLogJson(
            test_id=base_nodeid,
            function_name=first.function_name,
            file=first.file_path,
            total_runs=len(nodeids),
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            total_duration_seconds=round(total_duration, 4),
            runs=runs,
        )

    def all_nodeids(self) -> list[str]:
        """Return all nodeids in collection order."""
        result: list[str] = []
        for nodeids in self._function_runs.values():
            result.extend(nodeids)
        return result
