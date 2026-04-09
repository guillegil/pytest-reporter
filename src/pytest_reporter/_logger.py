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
        else:
            self._root = _root
            # These are only used on root; set to satisfy type checkers
            self._entries = _root._entries
            self._seq = 0
            self._lock = _root._lock

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

    def serialize(self) -> dict[str, Any]:
        """Serialize all entries to a dict with an 'entries' key."""
        with self._root._lock:
            return {"entries": [e.to_dict() for e in self._root._entries]}

    def reset(self) -> None:
        """Clear all entries and reset the sequence counter."""
        with self._root._lock:
            self._root._entries.clear()
            self._root._seq = 0
