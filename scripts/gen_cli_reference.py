#!/usr/bin/env python3
"""Generate the complete CLI reference (every command, argument, and option)
as Markdown by walking the Typer command tree.

Usage: python scripts/gen_cli_reference.py > reference.md

The output is the source for the docs site's "CLI Options Reference" page,
so the published reference can never drift from the shipped commands.
"""

from __future__ import annotations

import sys

import typer
from typer.core import TyperArgument, TyperOption

from tendrl_cli import __version__
from tendrl_cli.cli import app

TYPE_NAMES = {
    "text": "string",
    "integer": "int",
    "int": "int",
    "boolean": "flag",
    "bool": "flag",
    "path": "path",
    "file": "path",
    "filename": "path",
}


def type_name(param) -> str:
    if isinstance(param, TyperOption) and getattr(param, "is_flag", False):
        return "flag"
    name = getattr(param.type, "name", "text")
    return TYPE_NAMES.get(name, name)


def fmt_default(param) -> str:
    if isinstance(param, TyperOption) and getattr(param, "is_flag", False):
        return ""
    d = param.default
    if d in (None, ...) or param.required:
        return ""
    return f"`{d}`"


def esc(text) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def emit_command(cmd, path: list[str], out: list[str]) -> None:
    full = " ".join(path)
    out.append(f"### `tendrl-cli {full}`\n")
    if cmd.help:
        out.append(esc(cmd.help.splitlines()[0]) + "\n")

    args = [p for p in cmd.params if isinstance(p, TyperArgument)]
    opts = [p for p in cmd.params if isinstance(p, TyperOption) and p.name != "help"]

    if args:
        out.append("| Argument | Type | Required | Description |")
        out.append("|---|---|---|---|")
        for a in args:
            req = "yes" if a.required else "no"
            out.append(
                f"| `{a.name.upper()}` | {type_name(a)} | {req} | {esc(getattr(a, 'help', ''))} |"
            )
        out.append("")
    if opts:
        out.append("| Option | Type | Default | Description |")
        out.append("|---|---|---|---|")
        for o in opts:
            flags = ", ".join(f"`{x}`" for x in o.opts)
            out.append(f"| {flags} | {type_name(o)} | {fmt_default(o)} | {esc(o.help)} |")
        out.append("")


def walk(cmd, path: list[str], out: list[str]) -> None:
    subcommands = getattr(cmd, "commands", None)
    if subcommands:
        for name in subcommands:
            walk(subcommands[name], path + [name], out)
    else:
        emit_command(cmd, path, out)


def main() -> None:
    root = typer.main.get_command(app)

    out: list[str] = []
    out.append("---")
    out.append("sidebar_position: 6")
    out.append("---")
    out.append("")
    out.append("# Tendrl CLI: Options Reference")
    out.append("")
    out.append(
        f"Every command with its arguments, options, types, and defaults — "
        f"generated from tendrl-cli {__version__} itself "
        f"(`scripts/gen_cli_reference.py` in the CLI repo), so this page cannot "
        f"drift from the shipped tool. JSON request-body shapes and worked "
        f"examples live in the per-product pages: [Contact](contact-commands), "
        f"[Strand](strand-commands), [Surface](surface-commands)."
    )
    out.append("")
    out.append(
        "Global options (before any command): `--json` prints the raw API "
        "response for scripting; `--app-url <origin>` targets another "
        "environment (default `https://app.tendrl.com`, env `TENDRL_APP_URL`); "
        "`--version` prints the CLI version."
    )
    out.append("")

    order = ["login", "logout", "whoami", "accounts", "billing",
             "contact", "strand", "surface", "config", "api"]
    names = list(root.commands)
    ordered = [n for n in order if n in names] + [n for n in names if n not in order]

    for name in ordered:
        cmd = root.commands[name]
        out.append(f"## {name}\n")
        if getattr(cmd, "commands", None) and cmd.help:
            out.append(esc(cmd.help.splitlines()[0]) + "\n")
        walk(cmd, [name], out)

    sys.stdout.write("\n".join(out).rstrip() + "\n")


if __name__ == "__main__":
    main()
