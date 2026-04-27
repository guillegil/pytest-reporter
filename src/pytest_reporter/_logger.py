"""Structured tree-based logger for per-test and session logging."""

from __future__ import annotations

import traceback
from datetime import UTC, datetime
from threading import Lock
from typing import Any


class LogEntry:
    """A single log entry."""

    __slots__ = ("seq", "t", "level", "source", "msg", "data", "exc")

    def __init__(
        self,
        seq: int,
        t: str,
        level: str,
        source: list[str],
        msg: str,
        data: dict[str, Any] | None = None,
        exc: dict[str, str] | None = None,
    ) -> None:
        self.seq = seq
        self.t = t
        self.level = level
        self.source = source
        self.msg = msg
        self.data = data
        self.exc = exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "t": self.t,
            "level": self.level,
            "source": self.source,
            "msg": self.msg,
            "data": self.data,
            "exc": self.exc,
        }


class Logger:
    """Tree-based logger that serializes to a flat entry array.

    The root logger owns the sequence counter and entry list.
    Child loggers delegate to the root for storage.
    """

    def __init__(
        self,
        *,
        _root: Logger | None = None,
        _path: list[str] | None = None,
    ) -> None:
        if _root is None:
            # This is the root logger
            self._root: Logger = self
            self._entries: list[LogEntry] = []
            self._seq: int = 0
            self._lock = Lock()
            self._table_payloads: dict[int, Any] = {}
            self._used_artifact_names: set[str] = set()
        else:
            self._root = _root
            # These are only used on root; set to satisfy type checkers
            self._entries = _root._entries
            self._seq = 0
            self._lock = _root._lock
            self._table_payloads = _root._table_payloads
            self._used_artifact_names = _root._used_artifact_names

        self._path: list[str] = _path or []

    def child(self, name: str) -> Logger:
        """Create a child logger with the given name."""
        return Logger(_root=self._root, _path=[*self._path, name])

    def _log(
        self,
        level: str,
        msg: str,
        data: dict[str, Any] | None = None,
        exc_info: BaseException | None = None,
    ) -> None:
        exc: dict[str, str] | None = None
        if exc_info is not None:
            exc = {
                "type": type(exc_info).__name__,
                "msg": str(exc_info),
                "tb": "".join(
                    traceback.format_exception(
                        type(exc_info), exc_info, exc_info.__traceback__
                    )
                ),
            }

        t = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        with self._root._lock:
            seq = self._root._seq
            self._root._seq += 1

        entry = LogEntry(
            seq=seq,
            t=t,
            level=level,
            source=list(self._path),
            msg=msg,
            data=data,
            exc=exc,
        )
        with self._root._lock:
            self._root._entries.append(entry)

    def debug(self, msg: str, data: dict[str, Any] | None = None, exc_info: BaseException | None = None) -> None:
        self._log("DEBUG", msg, data, exc_info)

    def info(self, msg: str, data: dict[str, Any] | None = None, exc_info: BaseException | None = None) -> None:
        self._log("INFO", msg, data, exc_info)

    def warning(self, msg: str, data: dict[str, Any] | None = None, exc_info: BaseException | None = None) -> None:
        self._log("WARNING", msg, data, exc_info)

    def error(self, msg: str, data: dict[str, Any] | None = None, exc_info: BaseException | None = None) -> None:
        self._log("ERROR", msg, data, exc_info)

    def critical(self, msg: str, data: dict[str, Any] | None = None, exc_info: BaseException | None = None) -> None:
        self._log("CRITICAL", msg, data, exc_info)

    def table(
        self,
        data: Any,
        name: str = "table",
        *,
        level: str = "INFO",
    ) -> None:
        """Log a table (DataFrame, list[dict], or dict[str, list]).

        The table appears inline in the phase log at this chronological
        position and is also saved as a styled HTML artifact.

        Args:
            data: Table data -- pandas DataFrame (duck-typed), list of dicts,
                  or dict of lists.
            name: Display name for the table (also used for the artifact filename).
            level: Log level for the entry (default ``"INFO"``).
        """
        from ._table import (
            SERIALIZED_ROW_LIMIT,
            TablePayload,
            normalize_table,
            sanitize_filename,
        )

        columns, rows = normalize_table(data)

        # Generate unique artifact filename
        base = sanitize_filename(name)
        candidate = f"{base}.html"
        with self._root._lock:
            counter = 2
            while candidate in self._root._used_artifact_names:
                candidate = f"{base}_{counter}.html"
                counter += 1
            self._root._used_artifact_names.add(candidate)

        artifact_name = candidate
        truncated = len(rows) > SERIALIZED_ROW_LIMIT
        inline_rows = rows[:SERIALIZED_ROW_LIMIT]

        table_data: dict[str, Any] = {
            "_type": "table",
            "name": name,
            "columns": columns,
            "rows": inline_rows,
            "total_rows": len(rows),
            "truncated": truncated,
            "artifact_name": artifact_name,
        }

        self._log(level, f"Table: {name}", data=table_data)

        # Store full payload for artifact generation
        with self._root._lock:
            seq = self._root._seq - 1  # seq of the entry we just created
            self._root._table_payloads[seq] = TablePayload(
                name=name,
                columns=columns,
                rows=rows,
                artifact_name=artifact_name,
            )

    def get_table_payloads(self) -> dict[int, Any]:
        """Return table payloads for artifact writing (keyed by entry seq)."""
        with self._root._lock:
            return dict(self._root._table_payloads)

    def serialize(self) -> dict[str, Any]:
        """Serialize all entries to a dict with an 'entries' key."""
        with self._root._lock:
            return {"entries": [e.to_dict() for e in self._root._entries]}

    def reset(self) -> None:
        """Clear all entries and reset the sequence counter."""
        with self._root._lock:
            self._root._entries.clear()
            self._root._seq = 0
            self._root._table_payloads.clear()
            self._root._used_artifact_names.clear()
