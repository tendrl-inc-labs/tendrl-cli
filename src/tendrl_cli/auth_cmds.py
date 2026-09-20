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
    email: str = typer.Option(None, "--email", "-e", help="Email for password sign-in (prompted if omitted)."),
    account: str = typer.Option(None, "--account", help="Account to sign into (if you belong to several)."),
    password: bool = typer.Option(False, "--password", help="Use email + password instead of the browser."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Print the sign-in URL and paste the code (SSH/headless)."),
) -> None:
    """Sign in — opens your browser by default; --password for the old flow."""
    if not password and not email:
        _browser_login(paste_mode=no_browser)
        return
    email = email or Prompt.ask("email")
    origin = config.app_url(state_url())
    if origin and not origin.startswith("https://") and origin != "https://app.tendrl.com":
        warn("sending credentials over plain HTTP — use --app-url with https:// in production")
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


def _browser_login(paste_mode: bool = False) -> None:
    """PKCE loopback flow against /auth/cli/authorize + /auth/cli/token."""
    import base64
    import hashlib
    import http.server
    import secrets
    import threading
    import urllib.parse
    import webbrowser

    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    origin = config.app_url(state_url())

    result: dict = {}
    port = 0
    httpd = None
    if not paste_mode:
        class _CB(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: N802
                pass

            def do_GET(self):  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/cb":
                    self.send_response(404)
                    self.end_headers()
                    return
                q = urllib.parse.parse_qs(parsed.query)
                ok_state = q.get("state", [""])[0] == state
                if ok_state:
                    result["code"] = q.get("code", [""])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Security-Policy", "default-src 'none'")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                body = ("<h2 style='font-family:sans-serif'>Signed in — you can close this tab "
                        "and return to your terminal.</h2>") if ok_state else (
                        "<h2 style='font-family:sans-serif'>Sign-in state mismatch — "
                        "run tendrl-cli login again.</h2>")
                self.wfile.write(body.encode())

        try:
            httpd = http.server.HTTPServer(("127.0.0.1", 0), _CB)
            port = httpd.server_port
        except OSError:
            paste_mode = True

    authorize = (f"{origin}/auth/cli/authorize?state={state}"
                 f"&challenge={challenge}&port={port}")
    err_console.print(f"[dim]opening[/] {authorize}")
    opened = webbrowser.open(authorize)
    if not opened and not paste_mode:
        err_console.print("[yellow]![/] couldn't open a browser — visit the URL above, "
                          "then paste the code it shows")

    code = None
    if httpd is not None and not paste_mode:
        done = threading.Event()

        def serve() -> None:
            while "code" not in result and not done.is_set():
                httpd.handle_request()

        t = threading.Thread(target=serve, daemon=True)
        t.start()
        t.join(timeout=180)
        done.set()
        httpd.server_close()
        code = result.get("code")
        if not code:
            err_console.print("[yellow]![/] no callback received — paste the code from "
                              "the browser instead (re-run with --no-browser to skip the listener)")
    if not code:
        code = Prompt.ask("code from the browser").strip()

    client = _auth_client()
    resp = client.post("/auth/cli/token", json={"code": code, "verifier": verifier})
    token = resp.get("token") if isinstance(resp, dict) else None
    if not token:
        raise ApiError("sign-in failed: no token in exchange response", payload=resp)
    config.update(session_token=token,
                  session_user={"email": resp.get("email"),
                                "accountNumber": resp.get("accountNumber")})
    ok(f"signed in as [bold]{resp.get('email')}[/] — session cached at {config.config_path()}")


def state_url() -> str | None:
    from .common import state as _state
    return _state.get("app_url")


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
def accounts_switch(
    account: str = typer.Argument(..., help="Account name, number, or path (see 'accounts list')."),
) -> None:
    """Switch the cached session to another account."""
    client = session_client()
    listing = client.get("/auth/user-accounts")
    rows = listing.get("accounts", listing) if isinstance(listing, dict) else listing
    match = None
    for row in rows or []:
        if account in (row.get("accountPath"), row.get("accountName"),
                       str(row.get("accountNumber", ""))):
            match = row
            break
    if not match:
        raise ApiError(f"no account matching '{account}' — run 'tendrl-cli accounts list'")
    client.post("/auth/switch-account", json={
        "accountPath": match["accountPath"],
        "rolePath": match["rolePath"],
    })
    ok(f"active account is now [bold]{match.get('accountName') or match['accountPath']}[/]")


@accounts_app.command("show")
def accounts_show() -> None:
    """Show the active account's details."""
    payload = session_client().get("/api/accounts")
    show_detail(payload, title="account")


@billing_app.command("plans")
def billing_plans(
    product: str = typer.Option("contact", "--product", "-p", help="contact, strand, or surface."),
) -> None:
    """Show the public plan catalog for a product."""
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
