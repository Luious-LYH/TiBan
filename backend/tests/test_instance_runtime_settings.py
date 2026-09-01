from fastapi.testclient import TestClient

from app.core import config
from app.main import app
from app.services.llm_provider import llm_provider


def test_instance_llm_settings_are_redacted_runtime_scoped_and_restorable() -> None:
    client = TestClient(app)
    secret = "instance-only-test-secret"
    applied = client.post("/api/v3/settings/llm/apply", json={
        "provider": "openai_compatible",
        "base_url": "http://127.0.0.1:8000/v1",
        "model": "test-runtime-model",
        "api_key": secret,
    })
    assert applied.status_code == 200
    assert applied.json()["llm"]["runtime_override"] is True
    assert secret not in applied.text
    current = client.get("/api/v3/settings")
    assert current.status_code == 200
    assert current.json()["llm"]["api_key_configured"] is True
    assert secret not in current.text
    restored = client.post("/api/v3/settings/llm/restore")
    assert restored.status_code == 200
    assert restored.json()["llm"]["runtime_override"] is False


def test_embedding_batch_setting_is_bounded_and_restorable() -> None:
    client = TestClient(app)
    response = client.post("/api/v3/settings/embedding/apply", json={"batch_size": 16})
    assert response.status_code == 200
    assert response.json()["embedding"]["batch_size"] == 16
    invalid = client.post("/api/v3/settings/embedding/apply", json={"batch_size": 65})
    assert invalid.status_code == 422
    restored = client.post("/api/v3/settings/embedding/restore")
    assert restored.status_code == 200
    assert restored.json()["embedding"]["batch_size"] == 32


def test_explicit_private_ip_is_allowed_only_for_opted_in_runtime() -> None:
    original = config.LLM_PROVIDER_ALLOW_PRIVATE_NETWORK
    try:
        config.LLM_PROVIDER_ALLOW_PRIVATE_NETWORK = False
        assert llm_provider.preflight("https://10.0.0.8:53580/v1")["blocked_reason"] == "private_or_reserved_ip_blocked"
        config.LLM_PROVIDER_ALLOW_PRIVATE_NETWORK = True
        assert llm_provider.preflight("http://10.0.0.8:53580/v1")["ok"] is True
    finally:
        config.LLM_PROVIDER_ALLOW_PRIVATE_NETWORK = original
