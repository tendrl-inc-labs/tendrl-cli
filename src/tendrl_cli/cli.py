"""tendrl-cli — the Tendrl platform in your terminal."""

from __future__ import annotations

import sys

import typer

from . import __version__
from . import auth_cmds, config_cmds, contact_cmds, raw_cmd, strand_cmds, surface_cmds
from .common import state
from .http import ApiError, AuthRequired
from .render import err_console, fail

app = typer.Typer(
    name="tendrl-cli",
    help="The Tendrl platform in your terminal: Contact, Strand, and Surface.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"tendrl-cli {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    json_output: bool = typer.Option(
        False, "--json", help="Print raw API JSON (for scripting/jq)."
    ),
    app_url: str = typer.Option(
        None, "--app-url", help="Platform origin (default https://app.tendrl.com; env TENDRL_APP_URL)."
    ),
    version: bool = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="Show the CLI version.",
    ),
) -> None:
    state["json"] = json_output
    state["app_url"] = app_url


# Session commands at the top level.
app.command("login")(auth_cmds.login)
app.command("logout")(auth_cmds.logout)
app.command("whoami")(auth_cmds.whoami)
app.add_typer(auth_cmds.accounts_app, name="accounts")
app.add_typer(auth_cmds.billing_app, name="billing")

# Products.
app.add_typer(contact_cmds.app, name="contact")
app.add_typer(strand_cmds.app, name="strand")
app.add_typer(surface_cmds.app, name="surface")

# Utilities.
app.add_typer(config_cmds.app, name="config")
app.command("api")(raw_cmd.api)


def _explain(exc: ApiError) -> None:
    if isinstance(exc, AuthRequired):
        fail(exc.message)
        if exc.status_code == 401:
            err_console.print(
                "[dim]hint: your credential was rejected — re-run 'tendrl-cli login' "
                "or check the API key for this service[/]"
            )
        return
    if exc.code == "SUBSCRIPTION_REQUIRED":
        fail("this feature needs an active Strand subscription")
        err_console.print("[dim]manage your plan at https://app.tendrl.com/billing[/]")
        return
    fail(exc.message)
    if exc.status_code == 403:
        err_console.print("[dim]hint: your key's role lacks this action (it's not a bad token)[/]")
    elif exc.status_code == 429:
        err_console.print("[dim]hint: rate limited — wait a moment and retry[/]")
    if exc.request_id:
        err_console.print(f"[dim]request id: {exc.request_id}[/]")


def main() -> None:
    try:
        app()
    except AuthRequired as exc:
        _explain(exc)
        sys.exit(3)
    except ApiError as exc:
        _explain(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
