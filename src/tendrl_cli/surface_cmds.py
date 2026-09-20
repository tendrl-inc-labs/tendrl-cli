"""Surface commands: scans, history, profiles, account.

Authenticates with a Surface API key (``SURFACE_KEY``, format
``sfk_xxx.secret``).
"""

from __future__ import annotations

from pathlib import Path

import typer

from .common import (
    DATA_OPT,
    FILE_OPT,
    LIMIT_OPT,
    OFFSET_OPT,
    client,
    parse_body,
    show_detail,
    show_list,
)
from . import config
from .http import Client
from .render import ok

app = typer.Typer(help="Surface — file and payload scanning.")


def _s():
    return client("surface")


LOCAL_OPT = typer.Option(
    False, "--local", "-l",
    help="Use a local surface-scanner daemon instead of the hosted API "
         "(SURFACE_SCANNER_URL or 'config set-scanner'; default http://127.0.0.1:8080).",
)


def _scan_client(local: bool):
    """Hosted Surface client, or an unauthenticated local-daemon client."""
    if not local:
        return _s()
    return Client("surface", base=config.scanner_url())


def _confirm(what: str, yes: bool) -> None:
    if not yes:
        typer.confirm(f"delete {what}?", abort=True)


# ---------------------------------------------------------------- scanning

scan = typer.Typer(help="Submit and inspect scans.")
app.add_typer(scan, name="scan")


@scan.command("file")
def scan_file(
    path: Path = typer.Argument(..., exists=True, readable=True, help="File to scan."),
    profile: str = typer.Option(None, "--profile", help="Scan profile name or id (hosted only)."),
    local: bool = LOCAL_OPT,
) -> None:
    """Scan a local file — hosted, or on a local scanner daemon with --local."""
    if local and profile:
        raise typer.BadParameter("--profile does not apply to --local: the daemon uses the profile linked to its own API key")
    c = _scan_client(local)
    form = None
    if profile:
        # The API takes a profile_id; resolve a profile name.
        profile_id = profile
        if "-" not in profile or len(profile) < 32:
            profiles = c.get("/account/profiles")
            rows = profiles if isinstance(profiles, list) else profiles.get("profiles", [])
            profile_id = next((p["id"] for p in rows if p.get("name") == profile), profile)
        form = {"profile_id": profile_id}
    with path.open("rb") as fh:
        result = c.post("/scan", data=form, files={"file": (path.name, fh)})
    show_detail(result, title=f"scan: {path.name}")


@scan.command("payload")
def scan_payload(data: str = DATA_OPT, file: Path = FILE_OPT, local: bool = LOCAL_OPT) -> None:
    """Scan an inline payload (JSON body)."""
    show_detail(_scan_client(local).post("/scan/payload", json=parse_body(data, file)), title="scan")


@scan.command("get")
def scan_get(scan_id: str = typer.Argument(..., help="Scan id (the requestId from a scan or history entry)."), local: bool = LOCAL_OPT) -> None:
    """Show a scan's result."""
    show_detail(_scan_client(local).get(f"/scan/{scan_id}"))


# ---------------------------------------------------------------- history

history = typer.Typer(help="Scan history.")
app.add_typer(history, name="history")


@history.command("list")
def history_list(limit: int = LIMIT_OPT, offset: int = OFFSET_OPT) -> None:
    """List past scans."""
    show_list(_s().get("/account/history", params={"limit": limit, "offset": offset}),
              "history", "scans", empty="no scans yet")


@history.command("get")
def history_get(scan_id: str = typer.Argument(..., help="Scan id (the requestId from a scan or history entry).")) -> None:
    """Show one history entry."""
    show_detail(_s().get(f"/account/history/{scan_id}"))


@history.command("export")
def history_export(
    scan_id: str = typer.Argument(..., help="Scan id (the requestId from a scan or history entry)."),
    out: Path = typer.Option(None, "--out", "-o", help="Output file."),
) -> None:
    """Export a scan report."""
    resp = _s().get(f"/account/history/{scan_id}/export", raw=True)
    target = out or Path(f"surface-scan-{scan_id}.json")
    target.write_bytes(resp.content)
    ok(f"exported scan report to {target}")


# ---------------------------------------------------------------- account

account = typer.Typer(help="Account, usage, and analytics.")
app.add_typer(account, name="account")


@account.command("show")
def account_show() -> None:
    """Show account details and plan."""
    show_detail(_s().get("/account"), title="surface account")


@account.command("usage")
def account_usage() -> None:
    """Show scan usage against your plan."""
    show_detail(_s().get("/account/usage"), title="usage")


@account.command("analytics")
def account_analytics() -> None:
    """Show detection analytics."""
    show_detail(_s().get("/account/stats/charts"), title="analytics")


@account.command("blocked-ips")
def account_blocked_ips() -> None:
    """List blocked IPs."""
    show_list(_s().get("/account/blocked-ips"), "blocked_ips", "ips")


# ---------------------------------------------------------------- profiles

profiles = typer.Typer(help="Scan profiles.")
app.add_typer(profiles, name="profiles")


@profiles.command("list")
def profiles_list() -> None:
    """List scan profiles."""
    show_list(_s().get("/account/profiles"), "profiles")


@profiles.command("get")
def profiles_get(profile_id: str = typer.Argument(..., help="Profile id (see 'profiles list').")) -> None:
    """Show one profile."""
    show_detail(_s().get(f"/account/profiles/{profile_id}"))


@profiles.command("create")
def profiles_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a scan profile."""
    show_detail(_s().post("/account/profiles", json=parse_body(data, file)), title="created")


@profiles.command("update")
def profiles_update(profile_id: str = typer.Argument(..., help="Profile id (see 'profiles list')."), data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Update a scan profile."""
    show_detail(_s().put(f"/account/profiles/{profile_id}", json=parse_body(data, file)))


@profiles.command("delete")
def profiles_delete(profile_id: str = typer.Argument(..., help="Profile id (see 'profiles list')."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete a scan profile."""
    _confirm(f"profile {profile_id}", yes)
    _s().delete(f"/account/profiles/{profile_id}")
    ok(f"deleted profile {profile_id}")


@profiles.command("test-webhook")
def profiles_test_webhook(profile_id: str = typer.Argument(..., help="Profile id (see 'profiles list').")) -> None:
    """Send a test event to a profile's webhook."""
    show_detail(_s().post(f"/account/profiles/{profile_id}/test-webhook"), title="webhook test")


# ---------------------------------------------------------------- keys

keys = typer.Typer(help="Surface API keys.")
app.add_typer(keys, name="keys")


@keys.command("list")
def keys_list() -> None:
    """List API keys."""
    show_list(_s().get("/api-keys"), "api_keys", "keys")


@keys.command("create")
def keys_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create an API key (secret shown once — save it)."""
    show_detail(_s().post("/api-keys", json=parse_body(data, file)), title="created — secret shown once")


@keys.command("delete")
def keys_delete(key_id: str = typer.Argument(..., help="API key id (see 'keys list')."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete an API key."""
    _confirm(f"API key {key_id}", yes)
    _s().delete(f"/api-keys/{key_id}")
    ok(f"deleted key {key_id}")
