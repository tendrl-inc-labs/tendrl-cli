import httpx
import pytest
import respx
from typer.testing import CliRunner

from tendrl_cli.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("TENDRL_APP_URL", "SURFACE_KEY", "SURFACE_API_KEY", "SURFACE_SCANNER_URL"):
        monkeypatch.delenv(var, raising=False)


@respx.mock
def test_scan_payload_local_hits_daemon_without_auth():
    route = respx.post("http://127.0.0.1:8080/scan/payload").mock(
        return_value=httpx.Response(200, json={"safetyScore": {"score": 100}})
    )
    result = runner.invoke(app, ["--json", "surface", "scan", "payload", "--local",
                                 "-d", '{"payload": "hello"}'])
    assert result.exit_code == 0, result.output
    request = route.calls[0].request
    assert "Authorization" not in request.headers


@respx.mock
def test_scanner_url_env_override(monkeypatch):
    monkeypatch.setenv("SURFACE_SCANNER_URL", "http://127.0.0.1:9999")
    respx.post("http://127.0.0.1:9999/scan/payload").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    result = runner.invoke(app, ["--json", "surface", "scan", "payload", "-l",
                                 "-d", '{"payload": "hi"}'])
    assert result.exit_code == 0, result.output


def test_local_rejects_profile():
    result = runner.invoke(app, ["surface", "scan", "file", "README.md",
                                 "--local", "--profile", "Default"])
    assert result.exit_code != 0
