"""The run export of pytest-strategies — an optional integration.

pytest-strategies (4.3+) can write, when a session ends, what each test's
strategies were and which rows ran: ``strategies.json`` (the definitions) and
``strategies.vectors.json`` (the same, with every row and the outcome of each
test item that ran it). It writes them into the folder that
``--strategy-export``, its ``pytest_strategies_export_dir`` hook or its
``strategies_export_dir`` ini option names.

pytest-strategies is never imported here. With ``--report-dir`` the
``Reporter`` answers that hook with the run folder when nobody else chose a
folder, so the export is saved with the report; a folder the user chose is
respected, and its two files are copied into the run folder. At session end
:meth:`StrategyExport.load` reads ``strategies.vectors.json`` and the HTML
report shows each test's strategies and rows on a Strategy tab. The
``report_strategies`` ini setting turns all of this off.

Without pytest-strategies, or with a version before 4.3, the hook is never
called and nothing is read.
"""

from __future__ import annotations

import json
import os
import shutil
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

#: The definitions: each test with its strategies, no drawn values.
DEFINITIONS_NAME = "strategies.json"
#: The same, with the rows each test ran and their outcomes.
VECTORS_NAME = "strategies.vectors.json"

_KIND = "strategy_vectors"
# A row's keys the report uses (the others are ignored, as schema 1 asks).
_ROW_KEYS = ("id", "kind", "name", "index", "enumerated", "values")
_STRATEGY_KEYS = ("name", "origin", "arguments", "context", "nsamples", "parameter", "error")
# A file is this run's when it was written after the session started; file
# systems round modification times, so allow them to be a little earlier.
_MTIME_SLACK = 2.0
# The report's JavaScript reads numbers as doubles: a larger integer (a 64-bit
# register value) is embedded as its text instead, which it shows as written.
_SAFE_INT = 2**53 - 1


class StrategyExport:
    """Where pytest-strategies writes this session's run export, and what it wrote.

    Args:
        config: The pytest config.
        run_dir: This run's folder.
    """

    def __init__(self, config: pytest.Config, run_dir: Path) -> None:
        self._config = config
        self._run_dir = run_dir
        # What the pytest_strategies_export_dir hook answered (ours included)
        self._hooked: Any = None

    @property
    def enabled(self) -> bool:
        """Whether the ``report_strategies`` ini setting leaves the integration on."""
        try:
            return bool(self._config.getini("report_strategies"))
        except ValueError:  # pragma: no cover - ini registered by our plugin
            return True

    def answer(self, hooked: Any) -> Any:  # noqa: ANN401
        """The folder for the ``pytest_strategies_export_dir`` hook.

        Args:
            hooked: What the other implementations answered (``None`` when
                none chose a folder).

        Returns:
            ``hooked`` when a folder was chosen there; ``None`` when the user's
            ``strategies_export_dir`` ini option names one, or when the
            integration is off; else the run folder.
        """
        if not self.enabled:
            return hooked
        if _blank(hooked):
            hooked = str(self._run_dir) if _blank(self._ini()) else None
        self._hooked = hooked
        return hooked

    def folder(self) -> Path | None:
        """The folder pytest-strategies writes the export into, or ``None``.

        Follows pytest-strategies' own order: ``--strategy-export`` (relative
        to the folder pytest runs in), then the hook, then the ini option
        (both relative to the rootdir).
        """
        if not self.enabled:
            return None
        config = self._config
        option = config.getoption("strategy_export", None)
        if not _blank(option):
            return Path(config.invocation_params.dir, str(option))
        if not _blank(self._hooked):
            return Path(config.rootpath, os.fspath(self._hooked))
        ini = self._ini()
        if not _blank(ini):
            return Path(config.rootpath, str(ini))
        return None

    def load(self, since: float) -> dict[str, Any] | None:
        """Read this session's ``strategies.vectors.json``.

        A folder other than the run folder may hold the files of an earlier
        session, so there only files written after ``since`` count; they are
        copied into the run folder, which then holds the whole run.

        Args:
            since: When this session started (seconds since the epoch).

        Returns:
            The document, or ``None`` when there is none (pytest-strategies not
            installed or older than 4.3, the export off, or the file missing,
            stale or not readable).
        """
        folder = self.folder()
        if folder is None:
            return None
        path = folder / VECTORS_NAME
        try:
            if not path.is_file():
                return None
            if not _same(folder, self._run_dir):
                if path.stat().st_mtime < since - _MTIME_SLACK:
                    return None
                self._copy(folder, since)
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            _warn(f"the pytest-strategies export was skipped (unreadable): {path}: {err}")
            return None
        if not isinstance(document, dict) or document.get("kind") != _KIND:
            return None
        if not isinstance(document.get("tests"), list):
            return None
        return document

    # ------------------------------------------------------------------

    def _ini(self) -> Any:  # noqa: ANN401
        try:
            return self._config.getini("strategies_export_dir")
        except (ValueError, TypeError):  # not registered: no pytest-strategies 4.3
            return None

    def _copy(self, folder: Path, since: float) -> None:
        for name in (DEFINITIONS_NAME, VECTORS_NAME):
            source = folder / name
            try:
                if source.is_file() and source.stat().st_mtime >= since - _MTIME_SLACK:
                    shutil.copyfile(source, self._run_dir / name)
            except OSError as err:
                _warn(f"could not copy {source} into the run folder: {err}")


def _warn(message: str) -> None:
    """Warn, without raising when warnings are errors (``-W error``).

    An export that cannot be read is expected and handled: it must not cost
    the rest of the report.
    """
    try:
        warnings.warn(f"pytest-reporter: {message}", stacklevel=3)
    except Warning:
        pass


def _list(value: Any) -> list[Any]:  # noqa: ANN401
    return value if isinstance(value, list) else []


def js_safe(value: Any) -> Any:  # noqa: ANN401
    """``value`` with every integer JavaScript cannot hold exactly as ``{"$repr": text}``."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if -_SAFE_INT <= value <= _SAFE_INT else {"$repr": str(value)}
    if isinstance(value, list):
        return [js_safe(v) for v in value]
    if isinstance(value, dict):
        return {key: js_safe(v) for key, v in value.items()}
    return value


def _blank(value: Any) -> bool:  # noqa: ANN401
    return value is None or str(value) == ""


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:  # pragma: no cover - defensive
        return a == b


def html_data(
    document: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, list[dict[str, Any]]]]:
    """The export as the HTML report embeds it.

    Args:
        document: ``strategies.vectors.json``, or ``None``.

    Returns:
        The session's part (generator, seed, ``nsamples`` and the counts for
        the Report tab; ``None`` without a document), and each test function's
        strategies with their rows, by its node ID without parameters.
    """
    if document is None:
        return None, {}
    by_test: dict[str, list[dict[str, Any]]] = {}
    strategies = rows = 0
    for test in _list(document.get("tests")):
        if not isinstance(test, dict) or not isinstance(test.get("nodeid"), str):
            continue
        used = [_strategy(s) for s in _list(test.get("strategies")) if isinstance(s, dict)]
        if not used:
            continue
        by_test.setdefault(test["nodeid"], []).extend(used)
        strategies += len(used)
        rows += sum(len(s["rows"]) for s in used)
    generator = document.get("generator")
    session = {
        "generator": generator if isinstance(generator, dict) else None,
        "seed": js_safe(document.get("seed")),
        "nsamples": js_safe(document.get("nsamples")),
        "tests": len(by_test),
        "strategies": strategies,
        "rows": rows,
        "files": [DEFINITIONS_NAME, VECTORS_NAME],
    }
    return session, by_test


def _strategy(strategy: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {key: js_safe(strategy.get(key)) for key in _STRATEGY_KEYS}
    out["rows"] = [_row(r) for r in _list(strategy.get("rows")) if isinstance(r, dict)]
    return out


def _row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {key: js_safe(row.get(key)) for key in _ROW_KEYS}
    out["items"] = [
        {"nodeid": item.get("nodeid"), "outcome": item.get("outcome")}
        for item in _list(row.get("items"))
        if isinstance(item, dict)
    ]
    return out
