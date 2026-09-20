"""Local CLI configuration commands."""

from __future__ import annotations

import typer
from rich.prompt import Prompt

from . import config
from .common import json_mode
from .render import ok, print_json, print_detail

app = typer.Typer(help="Local CLI configuration (~/.config/tendrl/config.json).")

SERVICES = ("contact", "strand", "surface")


@app.command("path")
def path() -> None:
    """Print the config file path."""
    typer.echo(str(config.config_path()))


@app.command("show")
def show() -> None:
    """Show the current configuration (secrets masked)."""
    data = config.load()
    masked = dict(data)
    if masked.get("session_token"):
        masked["session_token"] = masked["session_token"][:8] + "…"
    if isinstance(masked.get("api_keys"), dict):
        masked["api_keys"] = {k: v[:8] + "…" for k, v in masked["api_keys"].items()}
    masked.setdefault("app_url", config.app_url())
    if json_mode():
        print_json(masked)
    else:
        print_detail(masked, title="tendrl-cli config")


@app.command("set-url")
def set_url(url: str = typer.Argument(..., help="Platform origin, e.g. https://app.tendrl.com")) -> None:
    """Set the platform URL (dev stacks, staging)."""
    config.update(app_url=url.rstrip("/"))
    ok(f"app url set to {url.rstrip('/')}")


@app.command("set-key")
def set_key(
    service: str = typer.Argument(..., help="contact, strand, or surface."),
    key: str = typer.Argument(None, help="API key (prompted if omitted)."),
) -> None:
    """Store an API key for a service."""
    if service not in SERVICES:
        raise typer.BadParameter(f"service must be one of: {', '.join(SERVICES)}")
    key = key or Prompt.ask(f"{service} API key", password=True)
    keys = config.load().get("api_keys", {})
    keys[service] = key
    config.update(api_keys=keys)
    ok(f"stored {service} key in {config.config_path()}")


@app.command("unset-key")
def unset_key(service: str = typer.Argument(..., help="contact, strand, or surface.")) -> None:
    """Remove a stored API key."""
    keys = config.load().get("api_keys", {})
    if keys.pop(service, None) is None:
        typer.echo(f"no stored key for {service}")
        return
    config.update(api_keys=keys or None)
    ok(f"removed {service} key")
