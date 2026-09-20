"""Terminal output for the Tendrl CLI.

Every command supports two modes: pretty (rich tables/panels, the default)
and ``--json`` (raw API payloads for scripting). Pretty output goes to
stdout; status chatter and errors go to stderr so pipes stay clean.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable, Sequence

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)

ACCENT = "cyan"

STATUS_STYLES = {
    "online": "bold green",
    "success": "bold green",
    "succeeded": "bold green",
    "completed": "bold green",
    "active": "green",
    "clean": "bold green",
    "running": "yellow",
    "pending": "yellow",
    "queued": "yellow",
    "offline": "red",
    "failed": "bold red",
    "error": "bold red",
    "cancelled": "dim",
    "canceled": "dim",
    "disabled": "dim",
    "malicious": "bold red",
    "suspicious": "yellow",
}


def print_json(data: Any) -> None:
    console.print_json(json.dumps(data, default=str))


def ok(message: str) -> None:
    err_console.print(f"[bold green]✓[/] {message}")


def warn(message: str) -> None:
    err_console.print(f"[yellow]![/] {message}")


def fail(message: str) -> None:
    err_console.print(f"[bold red]✗[/] {message}")


def style_status(value: Any) -> str:
    text = str(value)
    style = STATUS_STYLES.get(text.lower())
    return f"[{style}]{text}[/]" if style else text


def _cell(value: Any) -> str:
    if value is None:
        return "[dim]—[/]"
    if isinstance(value, bool):
        return "[green]yes[/]" if value else "[dim]no[/]"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, default=str)
        return text if len(text) <= 60 else text[:57] + "…"
    if isinstance(value, str) and _looks_like_timestamp(value):
        return _short_time(value)
    return str(value)


def _looks_like_timestamp(value: str) -> bool:
    return len(value) >= 19 and value[4:5] == "-" and value[7:8] == "-" and "T" in value


def _short_time(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def records_table(
    records: Sequence[dict[str, Any]],
    columns: Sequence[tuple[str, str]] | None = None,
    *,
    title: str | None = None,
    status_fields: Iterable[str] = ("status", "state"),
) -> Table:
    """Build a table from a list of dicts.

    ``columns`` is a list of (header, key) pairs; if omitted, columns are
    inferred from the keys of the first record (scalars first, capped at 8).
    """
    table = Table(
        title=title,
        header_style=f"bold {ACCENT}",
        border_style="bright_black",
        title_style="bold",
        expand=False,
    )
    if not records:
        return table
    if columns is None:
        keys = list(records[0].keys())
        scalars = [k for k in keys if not isinstance(records[0][k], (dict, list))]
        columns = [(k.replace("_", " "), k) for k in (scalars or keys)[:8]]
    status_set = set(status_fields)
    for header, _ in columns:
        table.add_column(header)
    for record in records:
        row = []
        for _, key in columns:
            value = record.get(key)
            row.append(style_status(value) if key in status_set and value else _cell(value))
        table.add_row(*row)
    return table


def print_records(
    records: Sequence[dict[str, Any]],
    columns: Sequence[tuple[str, str]] | None = None,
    *,
    title: str | None = None,
    total: int | None = None,
    empty: str = "nothing here yet",
) -> None:
    if not records:
        err_console.print(f"[dim]{empty}[/]")
        return
    console.print(records_table(records, columns, title=title))
    if total is not None and total > len(records):
        err_console.print(
            f"[dim]{len(records)} of {total} shown — use --limit/--offset to page[/]"
        )


def print_detail(record: dict[str, Any], *, title: str | None = None) -> None:
    """Key/value view of a single object."""
    table = Table(
        show_header=False,
        border_style="bright_black",
        title=title,
        title_style=f"bold {ACCENT}",
        expand=False,
    )
    table.add_column(style=f"bold {ACCENT}", no_wrap=True)
    table.add_column(overflow="fold")
    for key, value in record.items():
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, indent=2, default=str)
            if len(rendered) > 400:
                rendered = rendered[:397] + "…"
        elif key in ("status", "state") and value:
            rendered = style_status(value)
        else:
            rendered = _cell(value)
        table.add_row(key.replace("_", " "), rendered)
    console.print(table)
