"""Console output capture for pytest.log."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from _typeshed import WriteableBuffer


class TeeFile:
    """Wraps a file-like object to duplicate writes to a capture buffer."""

    def __init__(self, original: Any) -> None:  # noqa: ANN401
        self.original = original
        self.capture = StringIO()

    def write(self, data: str | bytes | WriteableBuffer) -> int:
        if isinstance(data, bytes):
            text = data.decode("utf-8", errors="replace")
        else:
            text = str(data)
        self.capture.write(text)
        written = self.original.write(data)
        # Some wrapped streams (pytest tee-sys capture, Windows console proxies)
        # return None instead of the character count. Fall back to len(text).
        return written if isinstance(written, int) else len(text)

    def flush(self) -> None:
        self.original.flush()

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        return getattr(self.original, name)


def install_capture(config: Any) -> TeeFile | None:  # noqa: ANN401
    """Install a TeeFile on the terminal reporter to capture output."""
    tr = config.pluginmanager.get_plugin("terminalreporter")
    if tr is None:
        return None
    tw = getattr(tr, "_tw", None)
    if tw is None:
        return None
    original_file = getattr(tw, "_file", None)
    if original_file is None:
        return None
    tee = TeeFile(original_file)
    tw._file = tee
    return tee


def finalize_capture(tee: TeeFile | None, log_path: Path) -> None:
    """Write captured output to pytest.log and restore original file."""
    if tee is None:
        return
    content = tee.capture.getvalue()
    log_path.write_text(content, encoding="utf-8")
    # Restore original file
    # The terminal reporter's _tw._file was replaced, but since the session
    # is finishing this is mostly for cleanliness
