from fastapi.testclient import TestClient
from unittest.mock import patch

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


def test_restoring_already_default_embedding_does_not_invalidate_indexes() -> None:
    client = TestClient(app)
    with patch("app.services.rag_service.rag_service.mark_index_stale") as mark_knowledge, patch(
        "app.services.semantic_memory_service.semantic_memory_service.mark_index_stale"
    ) as mark_memory:
        restored = client.post("/api/v3/settings/embedding/restore")

    assert restored.status_code == 200
    assert restored.json()["embedding"]["runtime_override"] is False
    mark_knowledge.assert_not_called()
    mark_memory.assert_not_called()


def test_mentor_conversation_delete_is_learner_scoped_and_removes_the_history() -> None:
    client = TestClient(app)
    learner_id = "mentor-delete-test"
    created = client.post("/api/v3/mentor/conversations", params={"learner_id": learner_id})
    assert created.status_code == 200
    conversation_id = created.json()["item"]["id"]

    other_learner = client.delete(f"/api/v3/mentor/conversations/{conversation_id}", params={"learner_id": "other-learner"})
    assert other_learner.status_code == 404

    deleted = client.delete(f"/api/v3/mentor/conversations/{conversation_id}", params={"learner_id": learner_id})
    assert deleted.status_code == 200
    assert deleted.json()["conversation_id"] == conversation_id
    assert deleted.json()["deleted"] is True
    assert client.get(f"/api/v3/mentor/conversations/{conversation_id}", params={"learner_id": learner_id}).status_code == 404


def test_explicit_private_ip_is_allowed_only_for_opted_in_runtime() -> None:
    original = config.LLM_PROVIDER_ALLOW_PRIVATE_NETWORK
    try:
        config.LLM_PROVIDER_ALLOW_PRIVATE_NETWORK = False
        assert llm_provider.preflight("https://10.0.0.8:53580/v1")["blocked_reason"] == "private_or_reserved_ip_blocked"
        config.LLM_PROVIDER_ALLOW_PRIVATE_NETWORK = True
        assert llm_provider.preflight("http://10.0.0.8:53580/v1")["ok"] is True
    finally:
        config.LLM_PROVIDER_ALLOW_PRIVATE_NETWORK = original
