"""Strand commands: workflows, runs, connectors, functions, vault, team.

Authenticates with a Strand API key (``STRAND_API_KEY``). A workflow is
the customer-facing object ("strand" is the product name); saving a
workflow mints a new immutable version.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .common import (
    DATA_OPT,
    FILE_OPT,
    LIMIT_OPT,
    OFFSET_OPT,
    client,
    json_mode,
    parse_body,
    show_detail,
    show_list,
)
from .render import ok, print_json

app = typer.Typer(help="Strand — workflows, runs, connectors, and automation.")


def _s():
    return client("strand")


def _confirm(what: str, yes: bool) -> None:
    if not yes:
        typer.confirm(f"delete {what}?", abort=True)


# ---------------------------------------------------------------- workflows

workflows = typer.Typer(help="Workflows (strands) and their versions.")
app.add_typer(workflows, name="workflows")


@workflows.command("list")
def workflows_list(limit: int = LIMIT_OPT, offset: int = OFFSET_OPT) -> None:
    """List workflows."""
    show_list(_s().get("/workflows", params={"limit": limit, "offset": offset}),
              "workflows", empty="no workflows yet")


@workflows.command("get")
def workflows_get(workflow_id: str) -> None:
    """Show one workflow."""
    show_detail(_s().get(f"/workflows/{workflow_id}"))


@workflows.command("create")
def workflows_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a workflow."""
    show_detail(_s().post("/workflows", json=parse_body(data, file)), title="created")


@workflows.command("update")
def workflows_update(workflow_id: str, data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Update a workflow's settings (name, schedule, tags, active)."""
    show_detail(_s().put(f"/workflows/{workflow_id}", json=parse_body(data, file)))


@workflows.command("delete")
def workflows_delete(workflow_id: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Delete a workflow."""
    _confirm(f"workflow {workflow_id}", yes)
    _s().delete(f"/workflows/{workflow_id}")
    ok(f"deleted workflow {workflow_id}")


@workflows.command("run")
def workflows_run(
    workflow_id: str,
    data: str = typer.Option(None, "--data", "-d", help="JSON input payload (optional)."),
    file: Path = FILE_OPT,
    version: str = typer.Option(None, "--version", help="Run a specific version id."),
) -> None:
    """Queue a workflow run."""
    body: dict = {"data": {}}
    if data or file:
        body["data"] = parse_body(data, file)
    if version:
        body["workflow_version_id"] = version
    show_detail(_s().post(f"/workflows/{workflow_id}/run", json=body), title="run queued")


@workflows.command("save")
def workflows_save(workflow_id: str, data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Save a new immutable version of a workflow's graph.

    The body is the graph: {"nodes": {...}, "edges": [...], "variables": {...}}.
    """
    body = parse_body(data, file)
    body.setdefault("edges", [])
    body.setdefault("nodes", {})
    show_detail(_s().post(f"/workflows/{workflow_id}/versions", json=body), title="version saved")


@workflows.command("versions")
def workflows_versions(workflow_id: str) -> None:
    """List a workflow's versions."""
    show_list(_s().get(f"/workflows/{workflow_id}/versions"), "versions")


@workflows.command("export")
def workflows_export(
    workflow_id: str,
    out: Path = typer.Option(None, "--out", "-o", help="Output file (default <id>.json)."),
) -> None:
    """Export a workflow to a JSON file."""
    payload = _s().get(f"/workflows/{workflow_id}/export")
    target = out or Path(f"{workflow_id}.json")
    target.write_text(json.dumps(payload, indent=2) + "\n")
    ok(f"exported workflow to {target}")


@workflows.command("import")
def workflows_import(
    path: Path = typer.Argument(..., exists=True, readable=True),
    name: str = typer.Option(None, "--name", help="Name for the imported workflow."),
) -> None:
    """Import a workflow from an exported JSON file."""
    template = json.loads(path.read_text())
    # The API wants the export wrapped as {"template": ...}; accept either.
    body = template if "template" in template else {"template": template}
    if name:
        body["name"] = name
    show_detail(_s().post("/workflows/import", json=body), title="imported")


@workflows.command("schedule-presets")
def workflows_schedule_presets() -> None:
    """List schedule presets."""
    show_list(_s().get("/schedule-presets"), "presets")


# ---------------------------------------------------------------- runs

runs = typer.Typer(help="Workflow runs.")
app.add_typer(runs, name="runs")


@runs.command("list")
def runs_list(
    status: str = typer.Option(None, "--status", help="Filter by run status."),
    limit: int = LIMIT_OPT,
    offset: int = OFFSET_OPT,
) -> None:
    """List runs."""
    show_list(_s().get("/runs", params={"status": status, "limit": limit, "offset": offset}),
              "runs", empty="no runs yet")


@runs.command("get")
def runs_get(run_id: str) -> None:
    """Show one run."""
    show_detail(_s().get(f"/runs/{run_id}"))


@runs.command("steps")
def runs_steps(run_id: str) -> None:
    """List a run's steps."""
    show_list(_s().get(f"/runs/{run_id}/steps"), "steps")


@runs.command("cancel")
def runs_cancel(
    run_id: str,
    reason: str = typer.Option(None, "--reason", help="Why the run is being cancelled."),
) -> None:
    """Cancel a run."""
    _s().post(f"/runs/{run_id}/cancel", json={"reason": reason} if reason else {})
    ok(f"cancelled run {run_id}")


@runs.command("approve")
def runs_approve(
    run_id: str,
    step_run_id: str,
    comment: str = typer.Option(None, "--comment", help="Note for the audit trail."),
) -> None:
    """Approve a paused approval step."""
    body = {"comment": comment} if comment else {}
    show_detail(_s().post(f"/runs/{run_id}/steps/{step_run_id}/approve", json=body), title="approved")


@runs.command("reject")
def runs_reject(
    run_id: str,
    step_run_id: str,
    comment: str = typer.Option(None, "--comment", help="Note for the audit trail."),
) -> None:
    """Reject a paused approval step."""
    body = {"comment": comment} if comment else {}
    show_detail(_s().post(f"/runs/{run_id}/steps/{step_run_id}/reject", json=body), title="rejected")


# ---------------------------------------------------------------- connectors

connectors = typer.Typer(help="Connectors, including AI model connectors.")
app.add_typer(connectors, name="connectors")


@connectors.command("list")
def connectors_list(
    connector_type: str = typer.Option(None, "--type", help="Filter by connector type."),
    limit: int = LIMIT_OPT,
    offset: int = OFFSET_OPT,
) -> None:
    """List connectors."""
    show_list(
        _s().get("/connectors", params={
            "connector_type": connector_type, "limit": limit, "offset": offset,
        }),
        "connectors",
    )


@connectors.command("get")
def connectors_get(connector_id: str) -> None:
    """Show one connector."""
    show_detail(_s().get(f"/connectors/{connector_id}"))


@connectors.command("create")
def connectors_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a connector."""
    show_detail(_s().post("/connectors", json=parse_body(data, file)), title="created")


@connectors.command("delete")
def connectors_delete(connector_id: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Delete a connector."""
    _confirm(f"connector {connector_id}", yes)
    _s().delete(f"/connectors/{connector_id}")
    ok(f"deleted connector {connector_id}")


@connectors.command("test")
def connectors_test(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Test a connector configuration."""
    show_detail(_s().post("/connectors/test", json=parse_body(data, file)), title="test")


@connectors.command("types")
def connectors_types() -> None:
    """List available connector types."""
    show_list(_s().get("/connector-types"), "connector_types", "types")


@connectors.command("ai-models")
def connectors_ai_models() -> None:
    """List available AI models by provider."""
    payload = _s().get("/ai-models")
    print_json(payload) if json_mode() else show_detail(
        payload if isinstance(payload, dict) else {"models": payload}, title="AI models"
    )


# ---------------------------------------------------------------- functions & vault

functions = typer.Typer(help="Reusable Python functions.")
app.add_typer(functions, name="functions")


@functions.command("list")
def functions_list() -> None:
    """List functions."""
    show_list(_s().get("/functions"), "functions")


@functions.command("get")
def functions_get(function_id: str) -> None:
    """Show one function."""
    show_detail(_s().get(f"/functions/{function_id}"))


@functions.command("create")
def functions_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a function."""
    show_detail(_s().post("/functions", json=parse_body(data, file)), title="created")


@functions.command("delete")
def functions_delete(function_id: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Delete a function."""
    _confirm(f"function {function_id}", yes)
    _s().delete(f"/functions/{function_id}")
    ok(f"deleted function {function_id}")


@functions.command("test")
def functions_test(
    function_id: str = typer.Argument(None, help="Saved function to test (omit with --code-file)."),
    data: str = typer.Option(None, "--data", "-d", help="Test payload JSON (default {})."),
    file: Path = FILE_OPT,
    code_file: Path = typer.Option(None, "--code-file", exists=True, readable=True,
                                   help="Test unsaved code from a local file."),
) -> None:
    """Run a function against a test payload."""
    payload = parse_body(data, file) if (data or file) else {}
    if code_file:
        body = {"code": code_file.read_text(), "test_payload": payload}
        result = _s().post("/functions/test", json=body)
    elif function_id:
        # The test endpoint requires code even for a saved function.
        code = _s().get(f"/functions/{function_id}").get("code", "")
        body = {"code": code, "test_payload": payload}
        result = _s().post(f"/functions/{function_id}/test", json=body)
    else:
        raise typer.BadParameter("pass a function id or --code-file")
    show_detail(result, title="test result")


vault = typer.Typer(help="Encrypted secrets (values are never returned).")
app.add_typer(vault, name="vault")


@vault.command("list")
def vault_list() -> None:
    """List secrets."""
    show_list(_s().get("/vault"), "vault", "secrets")


@vault.command("set")
def vault_set(
    key: str,
    value: str = typer.Argument(None, help="Secret value (prompted if omitted)."),
    description: str = typer.Option(None, "--description"),
) -> None:
    """Store a secret."""
    from rich.prompt import Prompt

    value = value if value is not None else Prompt.ask(f"value for {key}", password=True)
    body = {"key": key, "value": value}
    if description:
        body["description"] = description
    _s().post("/vault", json=body)
    ok(f"stored secret {key}")


@vault.command("delete")
def vault_delete(vault_id: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Delete a secret."""
    _confirm(f"secret {vault_id}", yes)
    _s().delete(f"/vault/{vault_id}")
    ok(f"deleted secret {vault_id}")


# ---------------------------------------------------------------- connections & configurations

connections = typer.Typer(help="Database/host connection credentials.")
app.add_typer(connections, name="connections")


@connections.command("list")
def connections_list() -> None:
    """List connections."""
    show_list(_s().get("/connections"), "connections")


@connections.command("get")
def connections_get(connection_id: str) -> None:
    """Show one connection."""
    show_detail(_s().get(f"/connections/{connection_id}"))


@connections.command("create")
def connections_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a connection."""
    show_detail(_s().post("/connections", json=parse_body(data, file)), title="created")


@connections.command("delete")
def connections_delete(connection_id: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Delete a connection."""
    _confirm(f"connection {connection_id}", yes)
    _s().delete(f"/connections/{connection_id}")
    ok(f"deleted connection {connection_id}")


configurations = typer.Typer(help="Named configuration blobs.")
app.add_typer(configurations, name="configurations")


@configurations.command("list")
def configurations_list(
    config_type: str = typer.Option(None, "--type", help="Filter by configuration type."),
) -> None:
    """List configurations."""
    show_list(_s().get("/configurations", params={"config_type": config_type}), "configurations")


@configurations.command("get")
def configurations_get(configuration_id: str) -> None:
    """Show one configuration."""
    show_detail(_s().get(f"/configurations/{configuration_id}"))


@configurations.command("create")
def configurations_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a configuration."""
    show_detail(_s().post("/configurations", json=parse_body(data, file)), title="created")


@configurations.command("delete")
def configurations_delete(configuration_id: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Delete a configuration."""
    _confirm(f"configuration {configuration_id}", yes)
    _s().delete(f"/configurations/{configuration_id}")
    ok(f"deleted configuration {configuration_id}")


# ---------------------------------------------------------------- templates

templates = typer.Typer(help="Workflow templates.")
app.add_typer(templates, name="templates")


@templates.command("list")
def templates_list(
    category: str = typer.Option(None, "--category"),
    tag: str = typer.Option(None, "--tag"),
) -> None:
    """List templates."""
    show_list(_s().get("/templates", params={"category": category, "tag": tag}), "templates")


@templates.command("get")
def templates_get(template_id: str) -> None:
    """Show one template."""
    show_detail(_s().get(f"/templates/{template_id}"))


@templates.command("readiness")
def templates_readiness(template_id: str) -> None:
    """Check what a template needs before it can run for you."""
    show_detail(_s().get(f"/templates/{template_id}/readiness"), title="readiness")


@templates.command("use")
def templates_use(
    template_id: str,
    name: str = typer.Option(None, "--name", help="Name for the new workflow."),
) -> None:
    """Create a workflow from a template."""
    body = {"name": name} if name else {}
    show_detail(_s().post(f"/templates/{template_id}/create", json=body), title="created")


# ---------------------------------------------------------------- keys, team, roles

keys = typer.Typer(help="Strand API keys.")
app.add_typer(keys, name="keys")


@keys.command("list")
def keys_list() -> None:
    """List API keys."""
    show_list(_s().get("/api-keys"), "api_keys", "keys")


@keys.command("create")
def keys_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create an API key (token shown once — save it)."""
    show_detail(_s().post("/api-keys", json=parse_body(data, file)), title="created — token shown once")


@keys.command("rotate")
def keys_rotate(key_id: str) -> None:
    """Rotate an API key (new token shown once)."""
    show_detail(_s().post(f"/api-keys/{key_id}/rotate"), title="rotated — token shown once")


@keys.command("delete")
def keys_delete(key_id: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Delete an API key."""
    _confirm(f"API key {key_id}", yes)
    _s().delete(f"/api-keys/{key_id}")
    ok(f"deleted key {key_id}")


team = typer.Typer(help="Team members.")
app.add_typer(team, name="team")


@team.command("list")
def team_list() -> None:
    """List team members."""
    show_list(_s().get("/team"), "team", "members", "users")


def _role_id(client, role: str) -> str:
    """Resolve a role name (or id) to its id."""
    roles = client.get("/roles")
    rows = roles if isinstance(roles, list) else roles.get("roles", [])
    for row in rows:
        if role in (row.get("id"), row.get("name")):
            return row["id"]
    raise typer.BadParameter(f"unknown role '{role}' — see 'strand roles list'")


@team.command("invite")
def team_invite(email: str, role: str = typer.Option("Viewer", "--role", help="Role name or id (see 'strand roles list').")) -> None:
    """Invite a team member."""
    c = _s()
    show_detail(c.post("/team/invite", json={"email": email, "role_id": _role_id(c, role)}),
                title="invited")


@team.command("set-role")
def team_set_role(user_id: str, role: str = typer.Argument(..., help="Role name or id.")) -> None:
    """Change a member's role."""
    c = _s()
    c.put(f"/team/{user_id}/role", json={"role_id": _role_id(c, role)})
    ok(f"user {user_id} role set to {role}")


@team.command("remove")
def team_remove(user_id: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Remove a team member."""
    _confirm(f"team member {user_id}", yes)
    _s().delete(f"/team/{user_id}")
    ok(f"removed {user_id}")


roles = typer.Typer(help="Strand roles and permissions.")
app.add_typer(roles, name="roles")


@roles.command("list")
def roles_list() -> None:
    """List roles."""
    show_list(_s().get("/roles"), "roles")


@roles.command("get")
def roles_get(role_id: str) -> None:
    """Show one role."""
    show_detail(_s().get(f"/roles/{role_id}"))


@roles.command("permissions")
def roles_permissions() -> None:
    """List all assignable permissions."""
    show_list(_s().get("/roles/permissions"), "permissions")


# ---------------------------------------------------------------- usage & audit

usage = typer.Typer(help="Plan usage.")
app.add_typer(usage, name="usage")

for _name, _help in [
    ("current", "Usage this billing period."),
    ("history", "Usage history."),
    ("breakdown", "Usage broken down by workflow."),
    ("summary", "Usage summary."),
]:
    def _make_usage(name: str, help_text: str):
        def cmd() -> None:
            show_detail(_s().get(f"/usage/{name}"), title=f"usage {name}")
        cmd.__doc__ = help_text
        return cmd
    usage.command(_name, help=_help)(_make_usage(_name, _help))


@app.command("audit")
def audit_list(
    resource_type: str = typer.Option(None, "--resource-type"),
    action: str = typer.Option(None, "--action"),
    limit: int = LIMIT_OPT,
    offset: int = OFFSET_OPT,
) -> None:
    """List audit log entries."""
    show_list(
        _s().get("/audit-logs", params={
            "resource_type": resource_type, "action": action,
            "limit": limit, "offset": offset,
        }),
        "audit_logs", "logs",
    )


@app.command("whoami")
def whoami() -> None:
    """Show the account and role behind your Strand key."""
    show_detail(_s().get("/auth/me"), title="strand identity")
