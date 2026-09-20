"""Session commands: login, logout, whoami, accounts, billing plans.

These talk to the Auth service with a cached session token (not an API
key) — Auth's customer routes only accept session tokens.
"""

from __future__ import annotations

import typer
from rich.prompt import Prompt

from . import config
from .common import extract_list, json_mode, session_client, show_detail, show_list, state
from .http import ApiError, Client
from .render import console, err_console, ok, print_json, print_records, warn

app = typer.Typer(help="Sign in and inspect your Tendrl account.")

accounts_app = typer.Typer(help="Accounts you belong to.")
billing_app = typer.Typer(help="Plans and billing info.")


def _auth_client(token: str | None = None) -> Client:
    return Client("auth", app_url=state["app_url"], token=token)


@app.command()
def login(
    email: str = typer.Option(None, "--email", "-e", help="Email (prompted if omitted)."),
    account: str = typer.Option(None, "--account", help="Account to sign into (if you belong to several)."),
) -> None:
    """Sign in with email + password and cache a session token."""
    email = email or Prompt.ask("email")
    password = Prompt.ask("password", password=True)
    body = {"email": email, "password": password, "rememberMe": True}
    if account:
        body["account"] = account

    client = _auth_client()
    result = client.post("/auth/login", json=body)

    # 200 does not mean success: branch on the machine-readable status.
    if isinstance(result, dict) and not result.get("success", False):
        if result.get("status") == "multiple_accounts":
            options = result.get("accounts") or []
            err_console.print("[bold]you belong to several accounts:[/]")
            for i, acct in enumerate(options, 1):
                name = acct.get("name") or acct.get("account") or acct.get("rolePath", "?")
                err_console.print(f"  [cyan]{i}[/]. {name}")
            choice = Prompt.ask("account", choices=[str(i) for i in range(1, len(options) + 1)])
            picked = options[int(choice) - 1]
            body["account"] = picked.get("rolePath") or picked.get("account") or picked.get("name")
            result = client.post("/auth/login", json=body)
        if isinstance(result, dict) and not result.get("success", False):
            raise ApiError(result.get("reason") or f"login failed ({result.get('status', 'unknown')})",
                           payload=result)

    token = result.get("token")
    if not token:
        raise ApiError("login response had no token", payload=result)
    user = result.get("user") or {}
    config.update(session_token=token, session_user=user)
    who = user.get("email") or email
    ok(f"signed in as [bold]{who}[/] — session cached at {config.config_path()}")


@app.command()
def logout() -> None:
    """Revoke the cached session and forget it locally."""
    token = config.session_token()
    if token:
        try:
            # /auth/logout only reads the cookie; it answers 302 on success.
            _auth_client().get("/auth/logout", headers={"Cookie": f"access_token={token}"})
        except ApiError as exc:
            if exc.status_code not in (301, 302):
                warn(f"server-side revoke failed ({exc.message}) — clearing local session anyway")
    config.update(session_token=None, session_user=None)
    ok("signed out")


@app.command()
def whoami(
    permissions: bool = typer.Option(False, "--permissions", help="Also show your role's allowed actions."),
) -> None:
    """Show the signed-in user and active account."""
    client = session_client()
    session = client.get("/auth/session")
    if json_mode() and not permissions:
        print_json(session)
        return
    show_detail(session, title="session")
    if permissions:
        perms = client.get("/auth/my-permissions")
        if json_mode():
            print_json(perms)
        else:
            show_detail(perms, title="permissions")


@accounts_app.command("list")
def accounts_list() -> None:
    """List the accounts your user belongs to."""
    payload = session_client().get("/auth/user-accounts")
    show_list(payload, "accounts")


@accounts_app.command("switch")
def accounts_switch(account: str = typer.Argument(..., help="Account (role path) to switch to.")) -> None:
    """Switch the cached session to another account."""
    session_client().post("/auth/switch-account", json={"account": account})
    ok(f"active account is now [bold]{account}[/]")


@accounts_app.command("show")
def accounts_show() -> None:
    """Show the active account's details."""
    payload = session_client().get("/api/accounts")
    show_detail(payload, title="account")


@billing_app.command("plans")
def billing_plans(
    product: str = typer.Option("contact", "--product", "-p", help="contact, strand, or surface."),
) -> None:
    """Show the public plan catalogue for a product."""
    client = _auth_client()  # public endpoint, no credential needed
    payload = client.get("/api/billing/plans", params={"product": product})
    if json_mode():
        print_json(payload)
        return
    records, _ = extract_list(payload, "plans")
    if records:
        print_records(records, title=f"{product} plans")
    else:
        show_detail(payload if isinstance(payload, dict) else {"plans": payload}, title=f"{product} plans")
