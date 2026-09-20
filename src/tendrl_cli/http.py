"""HTTP client for the Tendrl platform APIs.

One origin (default ``https://app.tendrl.com``) serves every product,
path-routed at the edge:

- Contact:  ``{origin}/api/...``
- Strand:   ``{origin}/strand/api/...``
- Surface:  ``{origin}/surface/api/...``
- Auth:     ``{origin}/auth/...`` and ``{origin}/api/accounts`` (session token)

All services accept ``Authorization: Bearer <credential>``. Errors come back
as ``{"reason": ...}`` (sometimes ``message``/``error``), with an optional
machine-readable ``status`` discriminator worth branching on.
"""

from __future__ import annotations

from typing import Any

import httpx

from . import __version__, config

SERVICE_PREFIX = {
    "contact": "/api",
    "strand": "/strand/api",
    "surface": "/surface/api",
    "auth": "",  # auth routes carry their own /auth or /api prefix
}

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ApiError(Exception):
    """A non-2xx response, or a transport failure."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,
        request_id: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload if isinstance(payload, dict) else {}
        self.request_id = request_id

    @property
    def status(self) -> str | None:
        """Machine-readable discriminator (e.g. ``multiple_accounts``)."""
        value = self.payload.get("status")
        return value if isinstance(value, str) else None

    @property
    def code(self) -> str | None:
        """Strand business-error code (e.g. ``SUBSCRIPTION_REQUIRED``)."""
        detail = self.payload.get("detail")
        if isinstance(detail, dict):
            value = detail.get("code")
            return value if isinstance(value, str) else None
        return None


class AuthRequired(ApiError):
    pass


def error_message(payload: Any, status_code: int) -> str:
    if isinstance(payload, dict):
        # Contact/Auth style: {"reason": ...} with message/error fallbacks.
        for field in ("reason", "message", "error"):
            value = payload.get(field)
            if isinstance(value, str) and value:
                return value
        # Strand (FastAPI) style: {"detail": <string | 422 list | object>}.
        detail = payload.get("detail")
        if isinstance(detail, str) and detail:
            return detail
        if isinstance(detail, list):
            parts = []
            for item in detail:
                if isinstance(item, dict):
                    loc = ".".join(str(x) for x in item.get("loc", []) if x != "body")
                    msg = item.get("msg", "invalid")
                    parts.append(f"{loc}: {msg}" if loc else str(msg))
            if parts:
                return "; ".join(parts)
        if isinstance(detail, dict):
            for field in ("message", "error"):
                value = detail.get(field)
                if isinstance(value, str) and value:
                    return value
    return f"request failed with HTTP {status_code}"


class Client:
    def __init__(
        self,
        service: str,
        *,
        app_url: str | None = None,
        token: str | None = None,
        base: str | None = None,
    ):
        if service not in SERVICE_PREFIX:
            raise ValueError(f"unknown service: {service}")
        self.service = service
        # An explicit base (e.g. a local surface-scanner daemon) wins over the
        # platform origin + service prefix.
        self.base = base.rstrip("/") if base else config.app_url(app_url) + SERVICE_PREFIX[service]
        self.token = token
        self._http = httpx.Client(
            timeout=TIMEOUT,
            follow_redirects=False,  # auth HTML surfaces answer 302 + ?error=
            headers={"User-Agent": f"tendrl-cli/{__version__}"},
        )

    @classmethod
    def for_service(cls, service: str, *, app_url: str | None = None, key: str | None = None) -> "Client":
        """Client authenticated with the service's account API key."""
        token = config.api_key(service, key)
        if not token:
            names = " or ".join(config.ENV_KEYS[service])
            raise AuthRequired(
                f"no API key for {service}: set {names}, pass --key, "
                f"or run 'tendrl-cli config set-key {service} <key>'"
            )
        return cls(service, app_url=app_url, token=token)

    @classmethod
    def for_session(cls, *, app_url: str | None = None) -> "Client":
        """Auth-service client using the cached login session token."""
        token = config.session_token()
        if not token:
            raise AuthRequired("not logged in: run 'tendrl-cli login' first")
        return cls("auth", app_url=app_url, token=token)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: dict[str, Any] | None = None,
        files: Any = None,
        headers: dict[str, str] | None = None,
        raw: bool = False,
    ) -> Any:
        url = self.base + path
        merged = dict(headers or {})
        if self.token:
            merged.setdefault("Authorization", f"Bearer {self.token}")
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            resp = self._http.request(
                method, url, params=clean_params, json=json, data=data, files=files, headers=merged
            )
        except httpx.HTTPError as exc:
            raise ApiError(f"cannot reach {url}: {exc}") from exc

        if resp.status_code in (301, 302, 303, 307, 308):
            raise ApiError(
                f"unexpected redirect to {resp.headers.get('location', '?')} "
                "(this endpoint is browser-only)",
                status_code=resp.status_code,
            )

        payload: Any = None
        if resp.content and (not raw or resp.status_code >= 400):
            try:
                payload = resp.json()
            except ValueError:
                payload = None

        request_id = resp.headers.get("X-Request-Id")
        if resp.status_code == 401:
            raise AuthRequired(
                error_message(payload, 401), status_code=401, payload=payload,
                request_id=request_id,
            )
        if resp.status_code >= 400:
            raise ApiError(
                error_message(payload, resp.status_code),
                status_code=resp.status_code,
                payload=payload,
                request_id=request_id,
            )
        if raw:
            return resp
        if payload is not None:
            return payload
        return resp.text or None

    def get(self, path: str, **kw: Any) -> Any:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> Any:
        return self.request("POST", path, **kw)

    def put(self, path: str, **kw: Any) -> Any:
        return self.request("PUT", path, **kw)

    def patch(self, path: str, **kw: Any) -> Any:
        return self.request("PATCH", path, **kw)

    def delete(self, path: str, **kw: Any) -> Any:
        return self.request("DELETE", path, **kw)

    def close(self) -> None:
        self._http.close()
