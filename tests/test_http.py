import httpx
import pytest
import respx

from tendrl_cli.http import ApiError, AuthRequired, Client, error_message


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("TENDRL_APP_URL", raising=False)


def test_service_base_paths():
    assert Client("contact").base == "https://app.tendrl.com/api"
    assert Client("strand").base == "https://app.tendrl.com/strand/api"
    assert Client("surface").base == "https://app.tendrl.com/surface/api"
    assert Client("auth").base == "https://app.tendrl.com"


def test_unknown_service_rejected():
    with pytest.raises(ValueError):
        Client("nope")


@respx.mock
def test_bearer_header_and_json():
    route = respx.get("https://app.tendrl.com/api/entities").mock(
        return_value=httpx.Response(200, json={"data": [], "total": 0})
    )
    result = Client("contact", token="k123").get("/entities")
    assert result == {"data": [], "total": 0}
    assert route.calls[0].request.headers["Authorization"] == "Bearer k123"


@respx.mock
def test_401_raises_auth_required():
    respx.get("https://app.tendrl.com/api/entities").mock(
        return_value=httpx.Response(401, json={"reason": "invalid key"})
    )
    with pytest.raises(AuthRequired) as exc:
        Client("contact", token="bad").get("/entities")
    assert exc.value.message == "invalid key"


@respx.mock
def test_redirect_is_an_error_not_followed():
    respx.get("https://app.tendrl.com/billing").mock(
        return_value=httpx.Response(302, headers={"location": "/login?error=x"})
    )
    with pytest.raises(ApiError) as exc:
        Client("auth", token="t").get("/billing")
    assert "browser-only" in exc.value.message


@respx.mock
def test_strand_business_error_code():
    respx.get("https://app.tendrl.com/strand/api/workflows").mock(
        return_value=httpx.Response(403, json={
            "detail": {"error": "no sub", "code": "SUBSCRIPTION_REQUIRED"}
        }, headers={"X-Request-Id": "req-9"})
    )
    with pytest.raises(ApiError) as exc:
        Client("strand", token="t").get("/workflows")
    assert exc.value.code == "SUBSCRIPTION_REQUIRED"
    assert exc.value.message == "no sub"
    assert exc.value.request_id == "req-9"


def test_error_message_shapes():
    assert error_message({"reason": "r"}, 400) == "r"
    assert error_message({"message": "m"}, 400) == "m"
    assert error_message({"detail": "not found"}, 404) == "not found"
    assert error_message(
        {"detail": [{"loc": ["body", "name"], "msg": "required", "type": "missing"}]}, 422
    ) == "name: required"
    assert error_message({"detail": {"message": "limit hit"}}, 403) == "limit hit"
    assert error_message(None, 500) == "request failed with HTTP 500"


def test_multiple_accounts_status():
    err = ApiError("login incomplete", payload={"status": "multiple_accounts"})
    assert err.status == "multiple_accounts"


def test_for_service_falls_back_to_session(tmp_path, monkeypatch):
    import json
    cfg = tmp_path / "tendrl" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"session_token": "sess-tok"}))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("TENDRL_API_KEY", "CONTACT_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    c = Client.for_service("contact")
    assert c.token == "sess-tok"


def test_for_service_prefers_api_key_over_session(tmp_path, monkeypatch):
    import json
    cfg = tmp_path / "tendrl" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"session_token": "sess-tok", "api_keys": {"contact": "api-key"}}))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("TENDRL_API_KEY", "CONTACT_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    c = Client.for_service("contact")
    assert c.token == "api-key"
