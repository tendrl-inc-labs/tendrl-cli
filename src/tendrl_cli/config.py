"""Configuration and credential resolution for the Tendrl CLI.

Resolution order for every value: explicit CLI flag, then environment
variable, then the config file, then the built-in default.

The config file lives at ``$XDG_CONFIG_HOME/tendrl/config.json`` (default
``~/.config/tendrl/config.json``) and is written with 0600 permissions
because it can hold the cached session token.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_APP_URL = "https://app.tendrl.com"

# Environment variables per credential. TENDRL_KEY is deliberately absent:
# that is the device/entity key used by the SDKs, not an account key.
ENV_APP_URL = "TENDRL_APP_URL"
ENV_KEYS: dict[str, tuple[str, ...]] = {
    "contact": ("TENDRL_API_KEY", "CONTACT_API_KEY"),
    "strand": ("STRAND_API_KEY",),
    "surface": ("SURFACE_KEY", "SURFACE_API_KEY"),
}


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "tendrl"


def config_path() -> Path:
    return config_dir() / "config.json"


def load() -> dict[str, Any]:
    try:
        return json.loads(config_path().read_text())
    except (OSError, ValueError):
        return {}


def save(data: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.chmod(0o600)
    tmp.replace(path)


def update(**fields: Any) -> dict[str, Any]:
    data = load()
    for key, value in fields.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    save(data)
    return data


def app_url(override: str | None = None) -> str:
    url = override or os.environ.get(ENV_APP_URL) or load().get("app_url") or DEFAULT_APP_URL
    return url.rstrip("/")


def api_key(service: str, override: str | None = None) -> str | None:
    """Resolve the account-plane API key for a service (contact|strand|surface)."""
    if override:
        return override
    for var in ENV_KEYS.get(service, ()):
        value = os.environ.get(var)
        if value:
            return value
    keys = load().get("api_keys", {})
    return keys.get(service)


DEFAULT_SCANNER_URL = "http://127.0.0.1:8080"
ENV_SCANNER_URL = "SURFACE_SCANNER_URL"


def scanner_url(override: str | None = None) -> str:
    """Base URL of a local surface-scanner daemon (``--daemon`` mode)."""
    url = (
        override
        or os.environ.get(ENV_SCANNER_URL)
        or load().get("scanner_url")
        or DEFAULT_SCANNER_URL
    )
    return url.rstrip("/")


def session_token() -> str | None:
    return load().get("session_token")


def session_user() -> dict[str, Any]:
    return load().get("session_user", {})
