"""Custom HTML tabs of a test: ``ReportTabs`` (what tests and conftests add to)
and ``collect_tabs`` (what the HTML report reads back).

Each tab is saved as it is added, in the attempt's ``tabs/`` folder: one
``NN_<slug>.html`` file per tab and a ``tabs.json`` manifest naming them in
order. The report embeds the HTML and shows each tab in a sandboxed frame.
"""

from __future__ import annotations

import json
import os
import re
import warnings
from pathlib import Path
from typing import Any

MANIFEST = "tabs.json"
MAX_TITLE = 40
# The sub-tabs the report builds itself: a custom tab cannot take their names.
RESERVED = ("Summary", "Procedure", "Checks", "Strategy", "Artifacts", "Retries")
MAX_EMBED_BYTES = 25 * 1024 * 1024


def _html_of(content: object) -> str:
    """The HTML text of what was given to ``add``."""
    if isinstance(content, str):
        return content
    if isinstance(content, os.PathLike):
        return Path(content).read_text(encoding="utf-8")
    to_html = getattr(content, "_repr_html_", None)
    if callable(to_html):
        html = to_html()
        if isinstance(html, str):
            return html
        raise TypeError(
            f"{type(content).__name__}._repr_html_() returned "
            f"{type(html).__name__}, not the HTML as a str"
        )
    raise TypeError(
        "tab content must be HTML as a str, the path of an HTML file, or an object "
        f"with _repr_html_(), not {type(content).__name__}"
    )


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug[:40] or "tab"


class ReportTabs:
    """The custom tabs of one test attempt in the HTML report.

    Given by the ``report_tabs`` fixture and to ``pytest_reporter_test_tabs``
    hook implementations. Without ``--report-dir`` the arguments are still
    checked, and nothing is saved.
    """

    def __init__(self, directory: Path | None = None) -> None:
        self._dir = directory
        self._tabs: list[dict[str, Any]] = []

    @property
    def titles(self) -> list[str]:
        """The titles of the tabs added so far, in order."""
        return [str(tab["title"]) for tab in self._tabs]

    def add(
        self,
        title: str,
        content: str | os.PathLike[str] | object,
        *,
        scripts: bool = False,
        height: int | None = None,
    ) -> None:
        """Add a tab to this test's detail in the HTML report.

        The tab is shown after the report's own tabs, in the order added, in a
        sandboxed frame: its HTML cannot read or change the report.

        Args:
            title: The tab's name. Not blank, at most 40 characters, not the
                name of one of the report's tabs (Summary, Procedure, Checks,
                Strategy, Artifacts, Retries) nor of a tab this test already
                has (compared without case).
            content: The HTML as a ``str`` (a whole document or a fragment),
                the path of an HTML file (read now, as UTF-8), or an object
                with ``_repr_html_()`` such as a pandas ``Styler``.
            scripts: Let the tab's JavaScript run (an interactive plot, say).
                Off by default. The frame stays isolated from the report
                either way.
            height: The frame's height in pixels. By default the frame is as
                tall as its content.

        Raises:
            TypeError: An argument of the wrong type.
            ValueError: A blank, too long, reserved or repeated title, or a
                height that is not positive.
            OSError: The file given as ``content`` could not be read.
        """
        if not isinstance(title, str):
            raise TypeError(f"tab title must be a str, not {type(title).__name__}")
        title = " ".join(title.split())
        if not title:
            raise ValueError("tab title must not be blank")
        if len(title) > MAX_TITLE:
            raise ValueError(f"tab title is longer than {MAX_TITLE} characters: {title!r}")
        key = title.casefold()
        if key in (name.casefold() for name in RESERVED):
            raise ValueError(f"tab title {title!r} is the name of one of the report's own tabs")
        if key in (name.casefold() for name in self.titles):
            raise ValueError(f"this test already has a tab named {title!r}")
        if not isinstance(scripts, bool):
            raise TypeError(f"scripts must be a bool, not {type(scripts).__name__}")
        if height is not None:
            if isinstance(height, bool) or not isinstance(height, int):
                raise TypeError(f"height must be an int, not {type(height).__name__}")
            if height <= 0:
                raise ValueError(f"height must be positive, not {height}")
        html = _html_of(content)

        tab: dict[str, Any] = {
            "title": title,
            "file": f"{len(self._tabs) + 1:02d}_{_slug(title)}.html",
            "scripts": scripts,
            "height": height,
        }
        self._tabs.append(tab)
        if self._dir is None:
            return
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            # surrogateescape text cannot be written as UTF-8: replace, never fail
            (self._dir / tab["file"]).write_bytes(html.encode("utf-8", errors="replace"))
            (self._dir / MANIFEST).write_text(
                json.dumps({"tabs": self._tabs}, indent=2), encoding="utf-8"
            )
        except OSError as err:
            # The report losing a tab must not fail the test
            warnings.warn(f"pytest-reporter: tab {title!r} could not be saved: {err}", stacklevel=2)


def collect_tabs(tabs_dir: Path) -> list[dict[str, Any]]:
    """Read an attempt's custom tabs for the HTML report.

    Anything unreadable is skipped with a warning: a broken tab never costs
    the report.

    Args:
        tabs_dir: The attempt's ``tabs`` folder.

    Returns:
        One dict per tab, in order: ``title``, ``scripts``, ``height`` and its
        ``html`` (or ``too_large: True`` for a file over the embedding cap).
    """
    manifest = tabs_dir / MANIFEST
    if not manifest.is_file():
        return []
    try:
        listed = json.loads(manifest.read_text(encoding="utf-8"))["tabs"]
        if not isinstance(listed, list):
            raise TypeError("'tabs' is not a list")
    except (OSError, ValueError, KeyError, TypeError) as err:
        warnings.warn(
            f"pytest-reporter: tabs skipped (unreadable): {manifest}: {err}", stacklevel=2
        )
        return []

    result: list[dict[str, Any]] = []
    for tab in listed:
        if not isinstance(tab, dict) or not isinstance(tab.get("title"), str):
            continue
        height = tab.get("height")
        entry: dict[str, Any] = {
            "title": tab["title"],
            "scripts": tab.get("scripts") is True,
            "height": height if isinstance(height, int) and height > 0 else None,
        }
        # the manifest names a file of this folder: never follow a path out of it
        path = tabs_dir / Path(str(tab.get("file", ""))).name
        try:
            if path.stat().st_size > MAX_EMBED_BYTES:
                entry["too_large"] = True
                warnings.warn(f"pytest-reporter: tab too large to embed: {path}", stacklevel=2)
            else:
                entry["html"] = path.read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            warnings.warn(f"pytest-reporter: tab skipped (unreadable): {path}: {err}", stacklevel=2)
            continue
        result.append(entry)
    return result
