import httpx
import pytest
import respx
from typer.testing import CliRunner

from tendrl_cli.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("TENDRL_APP_URL", "TENDRL_API_KEY", "CONTACT_API_KEY",
                "STRAND_API_KEY", "SURFACE_KEY", "SURFACE_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_root_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in ("contact", "strand", "surface", "login", "config", "api"):
        assert group in result.output


@pytest.mark.parametrize("group", [
    ["contact"], ["strand"], ["surface"], ["accounts"], ["billing"], ["config"],
    ["contact", "entities"], ["contact", "messages"], ["contact", "keys"],
    ["strand", "workflows"], ["strand", "runs"], ["strand", "vault"],
    ["surface", "scan"], ["surface", "profiles"],
])
def test_group_help_renders(group):
    result = runner.invoke(app, [*group, "--help"])
    assert result.exit_code == 0, result.output


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "tendrl-cli" in result.output


def test_missing_key_hint():
    # The CliRunner surfaces uncaught exceptions on the result; in real use
    # cli.main() renders this AuthRequired with the same hint text.
    result = runner.invoke(app, ["contact", "entities", "list"])
    assert result.exit_code != 0
    assert "TENDRL_API_KEY" in str(result.exception)


@respx.mock
def test_entities_list_json(monkeypatch):
    monkeypatch.setenv("TENDRL_API_KEY", "k1")
    respx.get("https://app.tendrl.com/api/entities").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "e1", "status": "online"}], "total": 1})
    )
    result = runner.invoke(app, ["--json", "contact", "entities", "list"])
    assert result.exit_code == 0, result.output
    assert '"e1"' in result.output


@respx.mock
def test_raw_api_command(monkeypatch):
    monkeypatch.setenv("STRAND_API_KEY", "k2")
    route = respx.get("https://app.tendrl.com/strand/api/workflows").mock(
        return_value=httpx.Response(200, json=[{"id": "wf1"}])
    )
    result = runner.invoke(app, ["api", "strand", "GET", "/workflows", "-q", "limit=5"])
    assert result.exit_code == 0, result.output
    assert "wf1" in result.output
    assert route.calls[0].request.url.params["limit"] == "5"


def test_raw_api_rejects_auth_service():
    result = runner.invoke(app, ["api", "auth", "GET", "/session"])
    assert result.exit_code != 0
