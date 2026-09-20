"""Contact commands: entities, messages, files, groups, dashboards, IAM.

Everything here authenticates with a Contact *account* API key
(``TENDRL_API_KEY``). Device-plane verbs that need an entity key
(publishing messages, check_messages) belong to the device SDKs and are
deliberately absent.
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
    json_mode,
    parse_body,
    show_detail,
    show_list,
)
from .render import ok, print_json

app = typer.Typer(help="Contact — devices (entities), messages, files, and account IAM.")


def _c():
    return client("contact")


def _confirm(what: str, yes: bool) -> None:
    if not yes:
        typer.confirm(f"delete {what}?", abort=True)


# ---------------------------------------------------------------- entities

entities = typer.Typer(help="Devices and services registered on your account.")
app.add_typer(entities, name="entities")


@entities.command("list")
def entities_list(limit: int = LIMIT_OPT, offset: int = OFFSET_OPT) -> None:
    """List entities."""
    payload = _c().get("/entities", params={"limit": limit, "offset": offset})
    if json_mode():
        print_json(payload)
        return
    from .common import extract_list
    from .render import print_records

    records, total = extract_list(payload, "entities")
    rows = [{
        "name": r.get("name"),
        "status": ("online" if (r.get("status") or {}).get("online") else "offline")
                  if isinstance(r.get("status"), dict) else r.get("status"),
        "role": r.get("role"),
        "mqtt": r.get("mqtt"),
        "service": r.get("service"),
        "created at": r.get("createdAt"),
    } for r in records]
    print_records(rows, total=total,
                  empty="no entities yet — register one with 'entities create'")


@entities.command("get")
def entities_get(entity_id: str = typer.Argument(..., help="Entity name.")) -> None:
    """Show one entity."""
    show_detail(_c().get(f"/entities/{entity_id}"), title=entity_id)


@entities.command("create")
def entities_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Register an entity (returns its key once — save it)."""
    show_detail(_c().post("/entities", json=parse_body(data, file)), title="created")


@entities.command("update")
def entities_update(entity_id: str = typer.Argument(..., help="Entity name."), data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Update an entity."""
    show_detail(_c().patch(f"/entities/{entity_id}", json=parse_body(data, file)))


@entities.command("delete")
def entities_delete(entity_id: str = typer.Argument(..., help="Entity name."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete an entity."""
    _confirm(f"entity {entity_id}", yes)
    _c().delete(f"/entities/{entity_id}")
    ok(f"deleted entity {entity_id}")


@entities.command("reboot")
def entities_reboot(entity_id: str = typer.Argument(..., help="Entity name.")) -> None:
    """Ask a device to reboot."""
    _c().post(f"/entities/{entity_id}/reboot")
    ok(f"reboot requested for {entity_id}")


@entities.command("heartbeat")
def entities_heartbeat(entity_id: str = typer.Argument(..., help="Entity name.")) -> None:
    """Show an entity's last heartbeat."""
    show_detail(_c().get(f"/entities/{entity_id}/heartbeat"), title="heartbeat")


@entities.command("state")
def entities_state(entity_id: str = typer.Argument(..., help="Entity name.")) -> None:
    """Show an entity's state table."""
    show_detail(_c().get(f"/entities/{entity_id}/status-table"), title=f"{entity_id} state")


@entities.command("provision-payload")
def entities_provision_payload(entity_id: str = typer.Argument(..., help="Entity name.")) -> None:
    """Fetch the provisioning payload for a device."""
    payload = _c().get(f"/entities/{entity_id}/provision-payload")
    print_json(payload) if json_mode() else show_detail(payload, title="provision payload")


@entities.command("rotate-key")
def entities_rotate_key(entity_id: str = typer.Argument(..., help="Entity name.")) -> None:
    """Rotate a device's entity key (returned once)."""
    show_detail(_c().post(f"/entities/{entity_id}/provision-rotate-key"), title="new key")


@entities.command("boards")
def entities_boards() -> None:
    """List supported board profiles."""
    show_list(_c().get("/board-profiles"), "board_profiles", "boards")


# ---------------------------------------------------------------- messages

messages = typer.Typer(help="Read, search, and export entity messages.")
app.add_typer(messages, name="messages")


@messages.command("list")
def messages_list(
    entity: str = typer.Option(None, "--entity", help="Filter by entity name."),
    start: str = typer.Option(None, "--start", help="Start date (ISO 8601)."),
    end: str = typer.Option(None, "--end", help="End date (ISO 8601)."),
    limit: int = LIMIT_OPT,
    offset: int = OFFSET_OPT,
) -> None:
    """List recent messages."""
    show_list(
        _c().get("/entities/messages", params={
            "limit": limit, "offset": offset, "entity_name": entity,
            "start_date": start, "end_date": end,
        }),
        "messages", empty="no messages in this window",
    )


@messages.command("get")
def messages_get(message_id: str = typer.Argument(..., help="Message id.")) -> None:
    """Show one message."""
    show_detail(_c().get(f"/entities/messages/{message_id}"))


@messages.command("search")
def messages_search(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Search messages with a filter body."""
    show_list(_c().post("/entities/messages/search", json=parse_body(data, file)), "messages")


@messages.command("export")
def messages_export(
    out: Path = typer.Option(None, "--out", "-o", help="Output file (default messages export)."),
    fmt: str = typer.Option("csv", "--format", help="csv or json."),
) -> None:
    """Export messages to a file."""
    resp = _c().get("/messages/export", params={"format": fmt}, raw=True)
    target = out or Path(f"tendrl-messages.{fmt}")
    target.write_bytes(resp.content)
    ok(f"exported messages to {target}")


# ---------------------------------------------------------------- files

files = typer.Typer(help="Account file storage and device file transfer.")
app.add_typer(files, name="files")


@files.command("list")
def files_list(limit: int = LIMIT_OPT, offset: int = OFFSET_OPT) -> None:
    """List files on the account."""
    show_list(_c().get("/files", params={"limit": limit, "offset": offset}), "files")


@files.command("get")
def files_get(file_id: str = typer.Argument(..., help="File id (see 'files list').")) -> None:
    """Show file metadata."""
    show_detail(_c().get(f"/entities/files/{file_id}"))


@files.command("upload")
def files_upload(
    path: Path = typer.Argument(..., exists=True, readable=True, help="Local file to send."),
    dest: str = typer.Option(..., "--dest", help="Destination entity or path."),
    tags: str = typer.Option(None, "--tags", help="Comma-separated tags."),
) -> None:
    """Upload a file for delivery to a device."""
    with path.open("rb") as fh:
        form = {"dest": dest}
        if tags:
            form["tags"] = tags
        result = _c().post("/entities/files", data=form, files={"file": (path.name, fh)})
    show_detail(result if isinstance(result, dict) else {"result": result}, title="uploaded")


@files.command("download")
def files_download(
    file_id: str = typer.Argument(..., help="File id (see 'files list')."),
    out: Path = typer.Option(None, "--out", "-o", help="Output path (default: file id)."),
) -> None:
    """Download a file's bytes."""
    resp = _c().get(f"/entities/files/download/{file_id}", raw=True)
    target = out or Path(file_id)
    target.write_bytes(resp.content)
    ok(f"saved {target} ({len(resp.content)} bytes)")


@files.command("delete")
def files_delete(file_id: str = typer.Argument(..., help="File id (see 'files list')."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete a file."""
    _confirm(f"file {file_id}", yes)
    _c().delete(f"/files/{file_id}")
    ok(f"deleted file {file_id}")


@files.command("rescan")
def files_rescan(file_id: str = typer.Argument(..., help="File id (see 'files list').")) -> None:
    """Re-run the Surface scan on a stored file."""
    show_detail(_c().post(f"/entities/files/{file_id}/rescan"), title="rescan")


# ---------------------------------------------------------------- grouping

fanouts = typer.Typer(help="Entity groups (fanouts).")
app.add_typer(fanouts, name="fanouts")


@fanouts.command("list")
def fanouts_list() -> None:
    """List fanouts."""
    show_list(_c().get("/fanouts"), "fanouts")


@fanouts.command("get")
def fanouts_get(fanout_id: str = typer.Argument(..., help="Fanout name.")) -> None:
    """Show one fanout."""
    show_detail(_c().get(f"/fanouts/{fanout_id}"))


@fanouts.command("create")
def fanouts_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a fanout."""
    show_detail(_c().post("/fanouts", json=parse_body(data, file)), title="created")


@fanouts.command("delete")
def fanouts_delete(fanout_id: str = typer.Argument(..., help="Fanout name."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete a fanout."""
    _confirm(f"fanout {fanout_id}", yes)
    _c().delete(f"/fanouts/{fanout_id}")
    ok(f"deleted fanout {fanout_id}")


@fanouts.command("add")
def fanouts_add(fanout_id: str = typer.Argument(..., help="Fanout name."), entity: str = typer.Argument(..., help="Entity name or resource path.")) -> None:
    """Add an entity to a fanout."""
    c = _c()
    # The API wants the entity's full resource path; resolve a bare name.
    entity_id = entity if ":" in entity else c.get(f"/entities/{entity}")["resourcePath"]
    c.post(f"/fanouts/{fanout_id}/entities", json={"entityId": entity_id})
    ok(f"added {entity} to {fanout_id}")


@fanouts.command("remove")
def fanouts_remove(fanout_id: str = typer.Argument(..., help="Fanout name."), entity_id: str = typer.Argument(..., help="Entity name.")) -> None:
    """Remove an entity from a fanout."""
    _c().delete(f"/fanouts/{fanout_id}/entities/{entity_id}")
    ok(f"removed {entity_id} from {fanout_id}")


@fanouts.command("publish")
def fanouts_publish(fanout_id: str = typer.Argument(..., help="Fanout name."), data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Publish a message to every entity in a fanout."""
    show_detail(_c().post(f"/fanouts/{fanout_id}/publish", json=parse_body(data, file)),
                title="published")


directories = typer.Typer(help="Fleet directory tree.")
app.add_typer(directories, name="directories")


@directories.command("list")
def directories_list() -> None:
    """List directories."""
    show_list(_c().get("/directories"), "directories")


@directories.command("get")
def directories_get(directory_id: str = typer.Argument(..., help="Directory id (see 'directories list').")) -> None:
    """Show one directory."""
    show_detail(_c().get(f"/directories/{directory_id}"))


@directories.command("create")
def directories_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a directory."""
    show_detail(_c().post("/directories", json=parse_body(data, file)), title="created")


@directories.command("delete")
def directories_delete(directory_id: str = typer.Argument(..., help="Directory id (see 'directories list')."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete a directory."""
    _confirm(f"directory {directory_id}", yes)
    _c().delete(f"/directories/{directory_id}")
    ok(f"deleted directory {directory_id}")


@directories.command("move")
def directories_move(directory_id: str = typer.Argument(..., help="Directory id (see 'directories list')."), data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Move a directory."""
    show_detail(_c().post(f"/directories/{directory_id}/move", json=parse_body(data, file)))


# ---------------------------------------------------------------- dashboards & alerts

dashboards = typer.Typer(help="Dashboards and widget data.")
app.add_typer(dashboards, name="dashboards")


@dashboards.command("list")
def dashboards_list() -> None:
    """List dashboards."""
    show_list(_c().get("/dashboards"), "dashboards")


@dashboards.command("get")
def dashboards_get(dashboard_id: str = typer.Argument(..., help="Dashboard id (see 'dashboards list').")) -> None:
    """Show one dashboard."""
    show_detail(_c().get(f"/dashboards/{dashboard_id}"))


@dashboards.command("fields")
def dashboards_fields(
    service: str = typer.Option(None, "--service", help="Service (payload schema) to inspect fields for."),
    entity: str = typer.Option(None, "--entity", help="Restrict field discovery to one entity."),
) -> None:
    """Discover queryable data fields."""
    show_list(_c().get("/dashboards/fields", params={"service": service, "entity": entity}),
              "fields")


@dashboards.command("query")
def dashboards_query(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Run a widget data query (see docs for the body shape)."""
    payload = _c().post("/dashboards/query", json=parse_body(data, file))
    print_json(payload)


alerts = typer.Typer(help="Alert rules.")
app.add_typer(alerts, name="alerts")


@alerts.command("list")
def alerts_list() -> None:
    """List alerts."""
    show_list(_c().get("/alerts"), "alerts")


@alerts.command("get")
def alerts_get(alert_id: str = typer.Argument(..., help="Alert id (see 'alerts list').")) -> None:
    """Show one alert."""
    show_detail(_c().get(f"/alerts/{alert_id}"))


@alerts.command("create")
def alerts_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create an alert."""
    show_detail(_c().post("/alerts", json=parse_body(data, file)), title="created")


@alerts.command("update")
def alerts_update(alert_id: str = typer.Argument(..., help="Alert id (see 'alerts list')."), data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Update an alert."""
    show_detail(_c().patch(f"/alerts/{alert_id}", json=parse_body(data, file)))


@alerts.command("delete")
def alerts_delete(alert_id: str = typer.Argument(..., help="Alert id (see 'alerts list')."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete an alert."""
    _confirm(f"alert {alert_id}", yes)
    _c().delete(f"/alerts/{alert_id}")
    ok(f"deleted alert {alert_id}")


@alerts.command("test")
def alerts_test(alert_id: str = typer.Argument(..., help="Alert id (see 'alerts list').")) -> None:
    """Fire a test of an alert."""
    show_detail(_c().post(f"/alerts/{alert_id}/test"), title="test result")


# ---------------------------------------------------------------- flows & services

flows = typer.Typer(help="Message routing flows and their connectors.")
app.add_typer(flows, name="flows")


@flows.command("list")
def flows_list() -> None:
    """List flows."""
    show_list(_c().get("/flows"), "flows")


@flows.command("get")
def flows_get(flow_id: str = typer.Argument(..., help="Flow id (see 'flows list').")) -> None:
    """Show one flow."""
    show_detail(_c().get(f"/flows/{flow_id}"))


@flows.command("connectors")
def flows_connectors() -> None:
    """List flow connectors."""
    show_list(_c().get("/flows/connectors"), "connectors")


@flows.command("connector-templates")
def flows_connector_templates() -> None:
    """List available connector templates."""
    show_list(_c().get("/flows/connector-templates"), "templates")


@flows.command("test-connector")
def flows_test_connector(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Test a connector configuration."""
    show_detail(_c().post("/flows/connectors/test", json=parse_body(data, file)), title="test")


services = typer.Typer(help="Payload schemas (services).")
app.add_typer(services, name="services")


@services.command("list")
def services_list() -> None:
    """List services."""
    show_list(_c().get("/services"), "services")


@services.command("get")
def services_get(service_id: str = typer.Argument(..., help="Service name.")) -> None:
    """Show one service."""
    show_detail(_c().get(f"/services/{service_id}"))


@services.command("create")
def services_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a service schema."""
    show_detail(_c().post("/services", json=parse_body(data, file)), title="created")


@services.command("delete")
def services_delete(service_id: str = typer.Argument(..., help="Service name."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete a service."""
    _confirm(f"service {service_id}", yes)
    _c().delete(f"/services/{service_id}")
    ok(f"deleted service {service_id}")


@services.command("validate")
def services_validate(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Validate a service definition before creating it."""
    show_detail(_c().post("/services/validate", json=parse_body(data, file)), title="validation")


# ---------------------------------------------------------------- insights

insights = typer.Typer(help="Account analytics and usage.")
app.add_typer(insights, name="insights")

for _name, _help in [
    ("summary", "Account overview."),
    ("messages", "Message volume analytics."),
    ("entities", "Entity analytics."),
    ("validation", "Schema validation analytics."),
    ("flows", "Flow analytics."),
]:
    def _make(name: str, help_text: str):
        def cmd() -> None:
            show_detail(_c().get(f"/insights/{name}"), title=name)
        cmd.__doc__ = help_text
        return cmd
    insights.command(_name, help=_help)(_make(_name, _help))


@insights.command("usage")
def insights_usage() -> None:
    """Data usage against your plan."""
    show_detail(_c().get("/insights/data-usage"), title="data usage")


# ---------------------------------------------------------------- IAM

keys = typer.Typer(help="Account API keys.")
app.add_typer(keys, name="keys")


@keys.command("list")
def keys_list() -> None:
    """List API keys."""
    show_list(_c().get("/api_keys"), "api_keys", "keys")


@keys.command("get")
def keys_get(key_id: str = typer.Argument(..., help="API key id (see 'keys list').")) -> None:
    """Show one API key."""
    show_detail(_c().get(f"/api_keys/{key_id}"))


@keys.command("create")
def keys_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create an API key (token shown once — save it)."""
    show_detail(_c().post("/api_keys", json=parse_body(data, file)), title="created — token shown once")


@keys.command("rotate")
def keys_rotate(key_id: str = typer.Argument(..., help="API key id (see 'keys list').")) -> None:
    """Rotate an API key (new token shown once)."""
    show_detail(_c().post(f"/api_keys/{key_id}/rotate"), title="rotated — token shown once")


@keys.command("delete")
def keys_delete(key_id: str = typer.Argument(..., help="API key id (see 'keys list')."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete an API key."""
    _confirm(f"API key {key_id}", yes)
    _c().delete(f"/api_keys/{key_id}")
    ok(f"deleted key {key_id}")


users = typer.Typer(help="Account users and invites.")
app.add_typer(users, name="users")


@users.command("list")
def users_list() -> None:
    """List users on the account."""
    show_list(_c().get("/users"), "users")


@users.command("set-role")
def users_set_role(user_id: str = typer.Argument(..., help="User id (see 'users list' / 'team list')."), role: str = typer.Argument(..., help="Role name.")) -> None:
    """Change a user's role."""
    _c().patch(f"/users/{user_id}/role", json={"role": role})
    ok(f"user {user_id} role set to {role}")


@users.command("remove")
def users_remove(user_id: str = typer.Argument(..., help="User id (see 'users list' / 'team list')."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Remove a user from the account."""
    _confirm(f"user {user_id}", yes)
    _c().delete(f"/users/{user_id}")
    ok(f"removed user {user_id}")


@users.command("invites")
def users_invites() -> None:
    """List pending invites."""
    show_list(_c().get("/user_invites"), "invites")


@users.command("invite")
def users_invite(email: str = typer.Argument(..., help="Email address to invite."), role: str = typer.Option(None, "--role", help="Role for the invited user (e.g. ReadOnly).")) -> None:
    """Invite a user to the account."""
    body = {"email": email}
    if role:
        body["role"] = role
    show_detail(_c().post("/user_invites", json=body), title="invited")


@users.command("revoke-invite")
def users_revoke_invite(email: str = typer.Argument(..., help="Invited email address (see 'users invites').")) -> None:
    """Revoke a pending invite."""
    _c().delete(f"/user_invites/{email}")
    ok(f"revoked invite for {email}")


roles = typer.Typer(help="IAM roles.")
app.add_typer(roles, name="roles")


@roles.command("list")
def roles_list() -> None:
    """List roles."""
    show_list(_c().get("/roles"), "roles")


@roles.command("get")
def roles_get(role_id: str = typer.Argument(..., help="Role name.")) -> None:
    """Show one role."""
    show_detail(_c().get(f"/roles/{role_id}"))


@roles.command("create")
def roles_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a role."""
    show_detail(_c().post("/roles", json=parse_body(data, file)), title="created")


@roles.command("delete")
def roles_delete(role_id: str = typer.Argument(..., help="Role name."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete a role."""
    _confirm(f"role {role_id}", yes)
    _c().delete(f"/roles/{role_id}")
    ok(f"deleted role {role_id}")


policies = typer.Typer(help="IAM policies.")
app.add_typer(policies, name="policies")


@policies.command("list")
def policies_list() -> None:
    """List policies."""
    show_list(_c().get("/policies"), "policies")


@policies.command("get")
def policies_get(policy_id: str = typer.Argument(..., help="Policy name.")) -> None:
    """Show one policy."""
    show_detail(_c().get(f"/policies/{policy_id}"))


@policies.command("create")
def policies_create(data: str = DATA_OPT, file: Path = FILE_OPT) -> None:
    """Create a policy."""
    show_detail(_c().post("/policies", json=parse_body(data, file)), title="created")


@policies.command("delete")
def policies_delete(policy_id: str = typer.Argument(..., help="Policy name."), yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt.")) -> None:
    """Delete a policy."""
    _confirm(f"policy {policy_id}", yes)
    _c().delete(f"/policies/{policy_id}")
    ok(f"deleted policy {policy_id}")


# ---------------------------------------------------------------- audit & deployments

audit = typer.Typer(help="Audit log.")
app.add_typer(audit, name="audit")


@audit.command("list")
def audit_list(limit: int = LIMIT_OPT, offset: int = OFFSET_OPT) -> None:
    """List audit log entries."""
    show_list(_c().get("/audit-logs", params={"limit": limit, "offset": offset}),
              "audit_logs", "logs")


@audit.command("export")
def audit_export(out: Path = typer.Option(None, "--out", "-o", help="Output file (default tendrl-audit-log.csv).")) -> None:
    """Export the audit log."""
    resp = _c().get("/audit-log/export", raw=True)
    target = out or Path("tendrl-audit-log.csv")
    target.write_bytes(resp.content)
    ok(f"exported audit log to {target}")


deployments = typer.Typer(help="OTA deployments.")
app.add_typer(deployments, name="deployments")


@deployments.command("list")
def deployments_list() -> None:
    """List deployments."""
    show_list(_c().get("/deployments"), "deployments")


@deployments.command("get")
def deployments_get(deployment_id: str = typer.Argument(..., help="Deployment id (see 'deployments list').")) -> None:
    """Show one deployment."""
    show_detail(_c().get(f"/deployments/{deployment_id}"))


@deployments.command("create")
def deployments_create(
    paths: list[Path] = typer.Argument(..., exists=True, readable=True,
                                       help="App files to include in the deployment."),
    name: str = typer.Option(None, "--name", help="Deployment name."),
    entry: str = typer.Option(None, "--entry", help="Entry module (defaults to the device's app_entry)."),
    no_scan: bool = typer.Option(False, "--no-scan", help="Skip the malware scan for these files."),
) -> None:
    """Create a deployment from local app files."""
    form: dict = {}
    if name:
        form["name"] = name
    if entry:
        form["entry"] = entry
    if no_scan:
        form["scan"] = "false"
    handles = [p.open("rb") for p in paths]
    try:
        files = [("file", (p.name, fh)) for p, fh in zip(paths, handles)]
        result = _c().post("/deployments", data=form or None, files=files)
    finally:
        for fh in handles:
            fh.close()
    show_detail(result, title="created")


@deployments.command("deploy")
def deployments_deploy(deployment_id: str = typer.Argument(..., help="Deployment id (see 'deployments list').")) -> None:
    """Roll out a deployment to its targets."""
    show_detail(_c().post(f"/deployments/{deployment_id}/deploy"), title="deploying")
