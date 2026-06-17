"""Table normalization, serialization, and HTML artifact generation."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

INLINE_ROW_LIMIT: int = 20
"""Rows shown initially in the inline log view."""

SERIALIZED_ROW_LIMIT: int = 200
"""Max rows stored in the JSON log entry (for JS toggle)."""


@dataclass
class TablePayload:
    """Full table data for artifact generation."""

    name: str
    columns: list[str]
    rows: list[list[str]]
    artifact_name: str


def _stringify_cell(value: Any) -> str:  # noqa: ANN401
    """Convert a cell value to a display string."""
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Inf" if value > 0 else "-Inf"
        return str(value)
    return str(value)


def normalize_table(data: Any) -> tuple[list[str], list[list[str]]]:  # noqa: ANN401
    """Normalize various table inputs to (columns, rows).

    Accepts:
    - DataFrame-like objects (duck-typed: has ``.columns`` and ``.values``)
    - ``list[dict]`` -- union of keys as columns, values as rows
    - ``dict[str, list]`` -- keys as columns, values transposed to rows

    Returns:
        Tuple of (column_names, row_data) where all cells are strings.

    Raises:
        TypeError: If input is not a recognized table format.
    """
    columns: list[str]
    rows: list[list[str]]

    # DataFrame-like (has .columns and .values attributes)
    if hasattr(data, "columns") and hasattr(data, "values"):
        columns = [str(c) for c in data.columns]
        rows = [[_stringify_cell(cell) for cell in row] for row in data.values]
        return columns, rows

    # list[dict]
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        col_set: dict[str, None] = {}
        for row_dict in data:
            for k in row_dict:
                col_set[k] = None
        columns = list(col_set)
        rows = [[_stringify_cell(row_dict.get(c)) for c in columns] for row_dict in data]
        return columns, rows

    # dict[str, list] (column-oriented)
    if isinstance(data, dict) and data:
        first_val = next(iter(data.values()))
        if isinstance(first_val, (list, tuple)):
            columns = [str(k) for k in data]
            n_rows = max(len(v) for v in data.values())
            rows = []
            for i in range(n_rows):
                row = []
                for c in columns:
                    vals = data[c]
                    row.append(_stringify_cell(vals[i] if i < len(vals) else None))
                rows.append(row)
            return columns, rows

    # Empty list
    if isinstance(data, list) and len(data) == 0:
        return [], []

    raise TypeError(
        f"Cannot normalize {type(data).__name__} as a table. "
        "Expected a DataFrame, list[dict], or dict[str, list]."
    )


def sanitize_filename(name: str) -> str:
    """Sanitize a table name for use as a filename."""
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    clean = clean.strip("_").lower()
    return clean or "table"


def build_table_artifact_html(name: str, columns: list[str], rows: list[list[str]]) -> str:
    """Build a self-contained dark-theme HTML document for a table artifact."""

    # Escape HTML
    def esc(s: str) -> str:
        return (
            s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        )

    header_cells = "".join(f"<th>{esc(c)}</th>" for c in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{esc(cell)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    tbody = "\n".join(body_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(name)}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code',
    'JetBrains Mono', 'Consolas', monospace;
  background: #0B1120;
  color: #E8ECF4;
  padding: 24px;
  -webkit-font-smoothing: antialiased;
}}
h2 {{
  font-size: 14px;
  font-weight: 700;
  color: #8292AA;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 12px;
}}
.meta {{
  font-size: 11px;
  color: #5A6B84;
  margin-bottom: 16px;
}}
.table-wrap {{
  overflow-x: auto;
  border: 1px solid #1E2D45;
  border-radius: 10px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}}
th {{
  background: #1B2740;
  color: #8292AA;
  font-weight: 700;
  padding: 8px 12px;
  text-align: left;
  border-bottom: 2px solid #1E2D45;
  position: sticky;
  top: 0;
  white-space: nowrap;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}}
td {{
  padding: 6px 12px;
  border-bottom: 1px solid #1E2D45;
  white-space: nowrap;
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
}}
tr:hover td {{ background: #243352; }}
tr:nth-child(even) td {{ background: rgba(27, 39, 64, 0.4); }}
tr:nth-child(even):hover td {{ background: #243352; }}
.footer {{
  padding: 10px 12px;
  font-size: 11px;
  color: #5A6B84;
  border-top: 1px solid #1E2D45;
}}
</style>
</head>
<body>
<h2>{esc(name)}</h2>
<div class="meta">{len(rows)} rows &times; {len(columns)} columns</div>
<div class="table-wrap">
<table>
<thead><tr>{header_cells}</tr></thead>
<tbody>
{tbody}
</tbody>
</table>
<div class="footer">{len(rows)} rows</div>
</div>
</body>
</html>"""
