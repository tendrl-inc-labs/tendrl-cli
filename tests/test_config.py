import json
import stat

import pytest

from tendrl_cli import config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("TENDRL_APP_URL", "TENDRL_API_KEY", "CONTACT_API_KEY",
                "STRAND_API_KEY", "SURFACE_KEY", "SURFACE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    yield tmp_path


def test_default_app_url():
    assert config.app_url() == "https://app.tendrl.com"


def test_app_url_resolution_order(monkeypatch):
    config.update(app_url="https://file.example")
    assert config.app_url() == "https://file.example"
    monkeypatch.setenv("TENDRL_APP_URL", "https://env.example/")
    assert config.app_url() == "https://env.example"  # env beats file, slash stripped
    assert config.app_url("https://flag.example") == "https://flag.example"


def test_api_key_env_fallback_order(monkeypatch):
    assert config.api_key("surface") is None
    config.update(api_keys={"surface": "from-file"})
    assert config.api_key("surface") == "from-file"
    monkeypatch.setenv("SURFACE_API_KEY", "from-alt-env")
    assert config.api_key("surface") == "from-alt-env"
    monkeypatch.setenv("SURFACE_KEY", "from-env")
    assert config.api_key("surface") == "from-env"  # primary env var wins
    assert config.api_key("surface", "from-flag") == "from-flag"


def test_device_key_env_is_not_used(monkeypatch):
    # TENDRL_KEY is the device/entity key — the CLI must never read it.
    monkeypatch.setenv("TENDRL_KEY", "device-key")
    assert config.api_key("contact") is None


def test_config_file_permissions():
    config.update(session_token="secret")
    mode = stat.S_IMODE(config.config_path().stat().st_mode)
    assert mode == 0o600
    assert json.loads(config.config_path().read_text())["session_token"] == "secret"


def test_update_removes_none_fields():
    config.update(session_token="secret")
    config.update(session_token=None)
    assert config.session_token() is None
