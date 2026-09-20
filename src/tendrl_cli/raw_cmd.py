"""Raw API escape hatch: call any customer endpoint with your own key.

Curated commands cover the common paths; this covers everything else:

    tendrl-cli api contact GET /entities/abc/heartbeat
    tendrl-cli api strand POST /workflows/wf_1/run -d '{"data": {}}'
    tendrl-cli api surface GET /history -q limit=5
"""

from __future__ import annotations

from pathlib import Path

import typer

from .common import DATA_OPT, FILE_OPT, client, json_mode, parse_body, parse_params
from .render import print_json
from .http import SERVICE_PREFIX

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


def api(
    service: str = typer.Argument(..., help="contact, strand, or surface."),
    method: str = typer.Argument(..., help="GET, POST, PUT, PATCH, or DELETE."),
    path: str = typer.Argument(..., help="Endpoint path, e.g. /entities."),
    data: str = DATA_OPT,
    file: Path = FILE_OPT,
    query: list[str] = typer.Option(None, "--param", "-q", help="Query param, key=value (repeatable)."),
) -> None:
    """Call any Tendrl API endpoint directly (uses your API key)."""
    service = service.lower()
    if service not in SERVICE_PREFIX or service == "auth":
        raise typer.BadParameter("service must be contact, strand, or surface")
    method = method.upper()
    if method not in METHODS:
        raise typer.BadParameter(f"method must be one of: {', '.join(METHODS)}")
    if not path.startswith("/"):
        path = "/" + path

    body = parse_body(data, file) if (data or file) else None
    result = client(service).request(method, path, params=parse_params(query), json=body)
    if result is None:
        if not json_mode():
            typer.echo("(empty response)", err=True)
        return
    if isinstance(result, (dict, list)):
        print_json(result)
    else:
        typer.echo(result)
