"""Every command, argument, and option must carry help text — the generated
docs reference (scripts/gen_cli_reference.py) depends on it."""

import typer
from typer.core import TyperArgument, TyperOption

from tendrl_cli.cli import app


def iter_commands(cmd, path=()):
    subs = getattr(cmd, "commands", None)
    if subs:
        for name, sub in subs.items():
            yield from iter_commands(sub, path + (name,))
    else:
        yield path, cmd


def test_every_command_and_param_has_help():
    root = typer.main.get_command(app)
    missing = []
    for path, cmd in iter_commands(root):
        name = " ".join(path)
        if not (cmd.help or "").strip():
            missing.append(f"{name}: command docstring")
        for p in cmd.params:
            if isinstance(p, TyperArgument) and not (getattr(p, "help", "") or "").strip():
                missing.append(f"{name}: argument {p.name}")
            elif isinstance(p, TyperOption) and p.name != "help" and not (p.help or "").strip():
                missing.append(f"{name}: option {p.name}")
    assert not missing, "params missing help text:\n" + "\n".join(missing)


def test_reference_generator_runs():
    import subprocess, sys
    out = subprocess.run(
        [sys.executable, "scripts/gen_cli_reference.py"], capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.count("### `tendrl-cli ") > 150
