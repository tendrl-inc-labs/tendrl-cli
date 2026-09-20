"""Shared plumbing for command modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from . import config
from .http import Client
from .render import print_json, print_records

# Set once by the root callback; read by every command.
state: dict[str, Any] = {"json": False, "app_url": None, "key": None}


def client(service: str, key: str | None = None) -> Client:
    return Client.for_service(service, app_url=state["app_url"], key=key or state.get("key"))


def session_client() -> Client:
    return Client.for_session(app_url=state["app_url"])


def json_mode() -> bool:
    return bool(state["json"])


def parse_body(data: str | None, file: Path | None) -> Any:
    """Parse a request body from --data (inline JSON or '-' for stdin) or --file."""
    if data and file:
        raise typer.BadParameter("use either --data or --file, not both")
    if file:
        raw = file.read_text()
    elif data == "-":
        raw = sys.stdin.read()
    elif data:
        raw = data
    else:
        raise typer.BadParameter("a JSON body is required: pass --data '<json>' or --file body.json")
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise typer.BadParameter(f"body is not valid JSON: {exc}") from exc


def parse_params(pairs: list[str] | None) -> dict[str, str]:
    """Parse repeated key=value query parameters."""
    result: dict[str, str] = {}
    for pair in pairs or []:
        key, sep, value = pair.partition("=")
        if not sep:
            raise typer.BadParameter(f"expected key=value, got '{pair}'")
        result[key] = value
    return result


def extract_list(payload: Any, *keys: str) -> tuple[list[dict[str, Any]], int | None]:
    """Normalize the API's three list envelopes into (records, total).

    Handles: bare arrays, ``{"data": [...], "total": N}``, and
    ``{"<resource>": [...], "total"|"next_cursor": ...}``.
    """
    if isinstance(payload, list):
        return payload, None
    if isinstance(payload, dict):
        for key in (*keys, "data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                total = payload.get("total")
                return value, total if isinstance(total, int) else None
    return [], None


def show_list(
    payload: Any,
    *keys: str,
    columns: list[tuple[str, str]] | None = None,
    empty: str = "nothing here yet",
) -> None:
    if json_mode():
        print_json(payload)
        return
    records, total = extract_list(payload, *keys)
    print_records(records, columns, total=total, empty=empty)


def show_detail(payload: Any, *, title: str | None = None) -> None:
    from .render import print_detail

    if json_mode():
        print_json(payload)
        return
    if isinstance(payload, dict):
        print_detail(payload, title=title)
    elif payload is not None:
        print_json(payload)


def save_export(resp: Any, out: Path | None, default_name: str) -> Path:
    """Write a raw export/download response body to disk."""
    target = out or Path(default_name)
    target.write_bytes(resp.content)
    return target


LIMIT_OPT = typer.Option(25, "--limit", "-n", help="Max rows to return.")
OFFSET_OPT = typer.Option(0, "--offset", help="Rows to skip (paging).")
DATA_OPT = typer.Option(None, "--data", "-d", help="JSON body, or '-' to read stdin.")
FILE_OPT = typer.Option(None, "--file", "-f", help="Read the JSON body from a file.")
