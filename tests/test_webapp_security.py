"""Security regression tests for the clutch web API (2026-07-04 review).

Covers: DNS-rebinding host validation, the optional /api/* auth token gate,
and serve()'s refusal to bind a non-loopback host without a token.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from clutch.chat_runtime import ChatRuntime
from clutch.motorblock import MotorErgebnis


def _handler(config, task):
    return MotorErgebnis(text="WEBOK", input_tokens=1, output_tokens=1,
                         model_id=config.model_id, provider=config.provider)


def _app(tmp, **kwargs):
    from clutch.webapp import create_app
    db = Path(tmp) / "clutch.db"
    rt = ChatRuntime(db_path=db, handler=_handler)
    return create_app(db_path=db, runtime=rt, **kwargs)


def test_loopback_host_is_accepted():
    with tempfile.TemporaryDirectory() as tmp:
        client = TestClient(_app(tmp), base_url="http://127.0.0.1")
        assert client.get("/api/models").status_code == 200


def test_rebinding_host_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        # Simulates a DNS-rebinding attacker: request arrives on the socket but
        # carries the attacker's own Host header.
        client = TestClient(_app(tmp), base_url="http://evil.example.com")
        assert client.get("/api/models").status_code == 400


def test_auth_token_blocks_unauthenticated_api_access():
    with tempfile.TemporaryDirectory() as tmp:
        client = TestClient(_app(tmp, auth_token="s3cret"),
                            base_url="http://127.0.0.1")
        # No token -> 401
        assert client.get("/api/models").status_code == 401
        # Wrong token -> 401
        assert client.get(
            "/api/models", headers={"Authorization": "Bearer wrong"}
        ).status_code == 401
        # Correct token -> 200
        assert client.get(
            "/api/models", headers={"Authorization": "Bearer s3cret"}
        ).status_code == 200
        # X-Clutch-Token header also works
        assert client.get(
            "/api/models", headers={"X-Clutch-Token": "s3cret"}
        ).status_code == 200


def test_index_injects_clutch_token_script():
    # The token gate guards /api/* — the UI page stays reachable and receives the injected token script
    with tempfile.TemporaryDirectory() as tmp:
        client = TestClient(_app(tmp, auth_token="s3cret"),
                            base_url="http://127.0.0.1")
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<script>window.CLUTCH_TOKEN = 's3cret';</script>" in resp.text


def test_serve_refuses_non_loopback_without_token(monkeypatch):
    monkeypatch.delenv("CLUTCH_WEB_TOKEN", raising=False)
    from clutch import webapp
    with pytest.raises(RuntimeError, match="Auth-Token"):
        webapp.serve(host="0.0.0.0", port=8760)


def test_serve_auto_generates_token_on_loopback(monkeypatch):
    monkeypatch.delenv("CLUTCH_WEB_TOKEN", raising=False)
    from clutch import webapp
    created_apps = []
    def dummy_create_app(**kwargs):
        created_apps.append(kwargs)
        return None

    monkeypatch.setattr(webapp, "create_app", dummy_create_app)
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: None)

    webapp.serve(host="127.0.0.1", port=8760)
    assert len(created_apps) == 1
    token = created_apps[0]["auth_token"]
    assert token is not None
    assert len(token) > 20
