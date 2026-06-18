"""Unit tests for TeeFile console capture."""

from __future__ import annotations

from pytest_reporter._console_capture import TeeFile


class _NoneWriter:
    """Stream whose write() returns None (mimics tee-sys / Windows console proxy)."""

    def __init__(self) -> None:
        self.data: list[str | bytes] = []

    def write(self, data: str | bytes) -> None:
        self.data.append(data)
        return None

    def flush(self) -> None:
        pass


class _IntWriter:
    """Stream whose write() returns the character count (standard TextIO contract)."""

    def __init__(self) -> None:
        self.data: list[str | bytes] = []

    def write(self, data: str | bytes) -> int:
        self.data.append(data)
        return len(data)

    def flush(self) -> None:
        pass


def test_write_handles_none_return() -> None:
    """A wrapped stream returning None must not crash; falls back to len(text)."""
    tee = TeeFile(_NoneWriter())
    result = tee.write("hello")
    assert result == 5
    assert tee.capture.getvalue() == "hello"


def test_write_preserves_int_return() -> None:
    """When the wrapped stream returns an int, it is passed through."""
    tee = TeeFile(_IntWriter())
    assert tee.write("abc") == 3
    assert tee.capture.getvalue() == "abc"


def test_write_handles_bytes_with_none_return() -> None:
    """Bytes input with a None-returning stream falls back to decoded length."""
    tee = TeeFile(_NoneWriter())
    result = tee.write(b"hi")
    assert result == 2
    assert tee.capture.getvalue() == "hi"
