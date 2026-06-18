"""HTML report data assembly — builds the data dict for build_html_report()."""

from __future__ import annotations

import base64
import json
import mimetypes
import platform
import sys
import warnings
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from .reporter import Reporter


def merge_metadata(
    hook_results: list[dict[str, dict[str, object]]],
    fixture: dict[str, dict[str, object]],
) -> dict[str, dict[str, str]]:
    """Merge hook contributions and fixture overrides into a stringified metadata dict.

    Hook results are applied in order (last implementation wins per label within
    a section).  The fixture dict is applied last, so fixture values override
    hook values on collision.  All section names, labels, and values are
    stringified via ``str()``.

    Args:
        hook_results: List of dicts returned by ``pytest_reporter_metadata``
            hookimpls (may include ``None`` entries; skipped automatically).
        fixture: Mutable dict populated via the ``report_metadata`` fixture.

    Returns:
        A ``{section: {label: str_value}}`` dict ready for JSON embedding.
    """
    merged: dict[str, dict[str, str]] = {}

    # Apply hook contributions first (last registered/later conftest wins per label).
    # Pluggy returns results in LIFO order (last registered = index 0), so we
    # iterate in reverse to ensure the last-registered hookimpl wins on collision.
    for result in reversed(hook_results):
        if not result:
            continue
        for section, rows in result.items():
            if not isinstance(rows, dict):
                continue
            merged.setdefault(section, {}).update({str(k): str(v) for k, v in rows.items()})

    # Apply fixture dict on top (fixture overrides hooks on collision)
    for section, rows in fixture.items():
        if not isinstance(rows, dict):
            continue
        merged.setdefault(section, {}).update({str(k): str(v) for k, v in rows.items()})

    return merged


MAX_EMBED_BYTES = 25 * 1024 * 1024  # 25 MB per-file embedding cap (REQ-6)


def collect_artifacts(artifacts_dir: Path) -> list[dict[str, object]]:
    """Read artifacts from disk and encode embeddable ones as data URIs.

    Per-file I/O errors are caught and warned so a single locked or deleted
    file does not prevent the rest of the artifact list from rendering (REQ-2A).
    Files larger than ``MAX_EMBED_BYTES`` are included as metadata-only entries
    without a ``data_uri``, avoiding MemoryError for large artifacts (REQ-6).

    Args:
        artifacts_dir: Path to the artifacts directory for a test run.

    Returns:
        A list of artifact dicts, each containing at minimum ``name`` and ``size``.
        Embeddable file types (images, HTML) additionally carry a ``data_uri``
        with a base64-encoded ``data:`` URI.  Oversized or unreadable files
        carry ``too_large: True`` or are skipped with a warning respectively.
    """
    if not artifacts_dir.is_dir():
        return []

    result: list[dict[str, object]] = []
    embeddable = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".bmp",
        ".html",
        ".htm",
    }

    for path in sorted(artifacts_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except (OSError, ValueError) as err:
            warnings.warn(
                f"pytest-reporter: artifact skipped (stat failed): {path}: {err}",
                stacklevel=2,
            )
            continue

        entry: dict[str, object] = {
            "name": path.name,
            "size": size,
        }

        ext = path.suffix.lower()
        if ext in embeddable:
            if size > MAX_EMBED_BYTES:
                # File is too large to embed — metadata-only entry (REQ-6)
                entry["too_large"] = True
                warnings.warn(
                    f"pytest-reporter: artifact too large to embed ({size} bytes): {path.name}",
                    stacklevel=2,
                )
            else:
                try:
                    raw = path.read_bytes()
                except (OSError, ValueError) as err:
                    warnings.warn(
                        f"pytest-reporter: artifact skipped (read failed): {path}: {err}",
                        stacklevel=2,
                    )
                    result.append(entry)
                    continue
                mime = mimetypes.guess_type(path.name)[0] or (
                    "text/html" if ext in (".html", ".htm") else "application/octet-stream"
                )
                b64 = base64.b64encode(raw).decode("ascii")
                entry["data_uri"] = f"data:{mime};base64,{b64}"

        result.append(entry)
    return result


def build_html_data(reporter: Reporter, duration: float, exitstatus: int) -> dict:  # type: ignore[type-arg]
    """Build the data dict for the HTML report.

    Args:
        reporter: The active ``Reporter`` instance holding all collected state.
        duration: Total session duration in seconds.
        exitstatus: Pytest exit status code.

    Returns:
        A dict ready to be passed to ``build_html_report()``.
    """
    # Collect all test data
    tests: list[dict] = []  # type: ignore[type-arg]
    for base_nodeid in reporter.collector.get_all_base_nodeids():
        aggregate = reporter.collector.get_function_aggregate(base_nodeid)
        runs: list[dict] = []  # type: ignore[type-arg]
        for nodeid in reporter.collector.get_function_nodeids(base_nodeid):
            run_info = reporter.collector.get_run_info(nodeid)
            phases = {}
            for when in ("setup", "call", "teardown"):
                phase = reporter.collector.get_phase(nodeid, when)
                if phase is not None:
                    phases[when] = {
                        "phase": phase.when,
                        "outcome": phase.outcome,
                        "start_time": phase.start_time,
                        "end_time": phase.end_time,
                        "duration": round(phase.duration, 4),
                        "longrepr": phase.longrepr,
                        "entries": phase.entries,
                    }

            # Collect artifacts from disk
            run_dir = reporter.context.run_subdir(
                run_info.file_path,
                run_info.function_name,
                run_info.run_id,
            )
            artifacts = collect_artifacts(run_dir / "artifacts")

            # Collect procedure
            tracker = reporter._procedure_trackers.get(nodeid)
            procedure = tracker.serialize() if tracker else {"steps": []}

            # Collect retry data
            retry_data = reporter.collector.get_retry_data(nodeid)
            retries_info = None
            retry_attempts = []
            if retry_data and retry_data.attempts > 0:
                retries_info = {
                    "attempts": retry_data.attempts,
                    "original_outcome": retry_data.original_outcome,
                    "history": retry_data.history,
                }
                # Collect retry attempt data from disk
                retries_base = run_dir / "retries"
                if retries_base.is_dir():
                    for attempt_dir in sorted(retries_base.iterdir()):
                        if attempt_dir.is_dir():
                            attempt_data: dict[str, Any] = {
                                "attempt": attempt_dir.name,
                                "phases": {},
                                "artifacts": collect_artifacts(attempt_dir / "artifacts"),
                            }
                            # Read phase logs from retry dir — guarded per-file (REQ-2B).
                            # A corrupt or unreadable phase log is warned and omitted
                            # so the attempt entry is still present minus the bad phase.
                            for phase_name in ("setup", "call", "teardown"):
                                phase_file = attempt_dir / f"{phase_name}.log.json"
                                if phase_file.exists():
                                    try:
                                        attempt_data["phases"][phase_name] = json.loads(
                                            phase_file.read_text()
                                        )
                                    except (json.JSONDecodeError, OSError) as err:
                                        warnings.warn(
                                            f"pytest-reporter: retry phase log skipped "
                                            f"(unreadable): {phase_file}: {err}",
                                            stacklevel=2,
                                        )
                            # Read procedure — guarded (REQ-2B)
                            proc_file = attempt_dir / "procedure.json"
                            if proc_file.exists():
                                try:
                                    attempt_data["procedure"] = json.loads(proc_file.read_text())
                                except (json.JSONDecodeError, OSError) as err:
                                    warnings.warn(
                                        f"pytest-reporter: retry procedure log skipped "
                                        f"(unreadable): {proc_file}: {err}",
                                        stacklevel=2,
                                    )
                            retry_attempts.append(attempt_data)

            # Collect verification check results from pytest-verify
            check_results = reporter._check_results.get(nodeid, [])

            runs.append(
                {
                    "run_id": run_info.run_id,
                    "nodeid": nodeid,
                    "parametrize_id": run_info.parametrize_id,
                    "params": {
                        k: {"type": type(v).__name__, "value": str(v)}
                        for k, v in run_info.params.items()
                    },
                    "outcome": reporter.collector.get_outcome(nodeid),
                    "duration": round(reporter.collector.get_duration(nodeid), 4),
                    "phases": phases,
                    "procedure": procedure,
                    "artifacts": artifacts,
                    "retries": retries_info,
                    "retry_attempts": retry_attempts,
                    "check_results": check_results,
                }
            )
        tests.append(
            {
                "base_nodeid": base_nodeid,
                "aggregate": dict(aggregate),
                "runs": runs,
            }
        )

    # Collect environment info
    plugin_list = []
    pm = reporter.config.pluginmanager
    for plugin in pm.get_plugins():
        name = pm.get_name(plugin) or getattr(plugin, "__name__", None)
        if name and not name.startswith("_"):
            plugin_list.append(name)

    cmdline = reporter.config.invocation_params.args

    # Session log data
    session_log_data = reporter.session_logger.serialize()

    # Collect and merge metadata from hook + fixture.
    # Broad except is intentional: pytest_reporter_metadata() is third-party
    # user code called at report-generation time.  The reporter is an observer
    # and must never crash or suppress test outcomes because a plugin misbehaves
    # (see .claude/CLAUDE.md: "The reporter observes, never judges / never
    # affects outcomes").  A raising hook gets its data silently dropped; the
    # fixture-provided metadata_store is still merged as usual.
    hook_results: list[dict[str, dict[str, object]]] = []
    try:
        hook_results = reporter.config.hook.pytest_reporter_metadata()
    except Exception as exc:  # noqa: BLE001
        warnings.warn(
            f"pytest_reporter_metadata hook raised an exception and will be ignored: {exc}",
            stacklevel=2,
        )
    system_metadata = merge_metadata(hook_results, reporter.metadata_store)

    return {
        "timestamp": reporter.context.timestamp,
        "duration": round(duration, 2),
        "exit_code": exitstatus,
        "python_version": sys.version,
        "pytest_version": pytest.__version__,
        "platform": platform.platform(),
        "plugins": plugin_list,
        "cmdline": [str(a) for a in cmdline],
        "tests": tests,
        "session_log": session_log_data,
        "retries_enabled": reporter.max_retries > 0,
        "max_retries": reporter.max_retries,
        "system_metadata": system_metadata,
    }
