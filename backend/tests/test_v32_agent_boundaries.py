from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import config
from app.db.database import SessionLocal
from app.db.models import (
    DocumentVersionModel,
    KnowledgeChunkModel,
    PracticeSessionModel,
    SourceDocumentModel,
    TutorThreadModel,
)
from app.main import app
from app.services.embedding_provider import OpenAICompatibleEmbeddingProvider, configured_embedding_provider
from app.services.knowledge_service import knowledge_service
from app.services.rag_service import COLLECTION, rag_service
from app.services.runtime_settings_service import runtime_settings_service
from app.services.semantic_memory_service import MEMORY_COLLECTION
from app.services.llm_provider import llm_provider


def _start_session(client: TestClient, learner_id: str, count: int = 2) -> dict[str, object]:
    response = client.post("/api/v3/practice/sessions", json={
        "learner_id": learner_id,
        "bank_id": "bank-cmexam-real",
        "mode": "study",
        "question_count": count,
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["question_ids"] and payload["tutor_thread_id"]
    return payload


def test_practice_session_resume_creates_fresh_tutor_and_closes_old_thread() -> None:
    learner_id = f"v32-session-{uuid4().hex[:10]}"
    client = TestClient(app)
    first = _start_session(client, learner_id)

    resumed = client.post(
        f"/api/v3/practice/sessions/{first['session_id']}/resume",
        params={"learner_id": learner_id},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["tutor_thread_id"] != first["tutor_thread_id"]

    with SessionLocal() as session:
        old = session.get(TutorThreadModel, first["tutor_thread_id"])
        current = session.get(TutorThreadModel, resumed.json()["tutor_thread_id"])
        assert old is not None and old.status == "closed"
        assert current is not None and current.status == "active"

    stale = client.post("/api/v3/tutor/stream", json={
        "practice_session_id": first["session_id"],
        "tutor_thread_id": first["tutor_thread_id"],
        "question_id": first["question_ids"][0],
        "learner_id": learner_id,
        "message": "请给我一个提示。",
        "mode": "study",
    })
    assert stale.status_code == 409

    second = _start_session(client, learner_id)
    with SessionLocal() as session:
        previous = session.get(PracticeSessionModel, first["session_id"])
        second_thread = session.get(TutorThreadModel, second["tutor_thread_id"])
        assert previous is not None and previous.status == "abandoned"
        assert second_thread is not None and second_thread.status == "active"


def test_objective_submit_does_not_call_llm_retrieval_or_embedding(monkeypatch) -> None:
    learner_id = f"v32-submit-{uuid4().hex[:10]}"
    client = TestClient(app)
    created = _start_session(client, learner_id, count=1)

    with SessionLocal() as session:
        from app.db.models import QuestionModel

        question = session.get(QuestionModel, created["question_ids"][0])
        assert question is not None
        correct = question.grading_payload["correct_option_id"]

    calls: list[str] = []

    def forbidden(*_args, **_kwargs):
        calls.append("called")
        raise AssertionError("objective submit must not invoke an Agent dependency")

    monkeypatch.setattr(llm_provider, "chat", forbidden)
    monkeypatch.setattr(rag_service, "retrieve", forbidden)
    response = client.post("/api/v3/practice/submit", json={
        "learner_id": learner_id,
        "question_id": question.question_id,
        "session_id": created["session_id"],
        "selected_answer": correct,
        "hint_count": 0,
        "mode": "study",
        "duration_ms": 18700,
    })
    assert response.status_code == 200, response.text
    assert response.json()["score"] == 100
    assert calls == []
    assert "request_total" in response.headers.get("server-timing", "")


def test_knowledge_projection_counts_only_latest_canonical_version() -> None:
    token = uuid4().hex[:10]
    document_id = f"v32-versioned-{token}"
    old_version = f"{document_id}-old"
    new_version = f"{document_id}-new"
    now = datetime.utcnow()
    with SessionLocal() as session:
        session.add(SourceDocumentModel(
            document_id=document_id,
            domain_id="endoscopy",
            name="版本投影测试资料",
            media_type="text/markdown",
            content_hash=token,
            status="ready",
            business_usage="knowledge_base",
            license_gate_status="allow",
            ai_ingestion_allowed=True,
            namespace="system",
            source_scope="system",
            enabled=True,
        ))
        session.add_all([
            DocumentVersionModel(
                version_id=old_version,
                document_id=document_id,
                version_label="old",
                source_path="old.md",
                content_hash=f"old-{token}",
                parser="test",
                status="indexed",
                created_at=now - timedelta(minutes=2),
            ),
            DocumentVersionModel(
                version_id=new_version,
                document_id=document_id,
                version_label="new",
                source_path="new.md",
                content_hash=f"new-{token}",
                parser="test",
                status="indexed",
                created_at=now,
            ),
        ])
        session.add_all([
            KnowledgeChunkModel(
                chunk_id=f"{document_id}-old-chunk",
                document_id=document_id,
                version_id=old_version,
                parent_section="旧章节",
                page=1,
                ordinal=0,
                content="旧版本内容不应计入当前资料数量。",
                content_hash=f"old-chunk-{token}",
                token_count=16,
                namespace="system",
            ),
            KnowledgeChunkModel(
                chunk_id=f"{document_id}-new-chunk",
                document_id=document_id,
                version_id=new_version,
                parent_section="当前章节",
                page=2,
                ordinal=0,
                content="当前版本内容应显示在资料预览中。",
                content_hash=f"new-chunk-{token}",
                token_count=18,
                namespace="system",
            ),
        ])
        session.commit()
    try:
        listed = next(item for item in knowledge_service.list_sources() if item["id"] == document_id)
        detail = knowledge_service.detail(document_id)
        assert listed["chunk_count"] == 1
        assert detail["chunk_count"] == 1
        assert detail["preview"][0]["section"] == "当前章节"
        citations = rag_service.retrieve("当前版本内容资料预览", mode="sparse", document_ids=[document_id], limit=5)
        assert [item.chunk_id for item in citations] == [f"{document_id}-new-chunk"]
    finally:
        with SessionLocal() as session:
            session.query(KnowledgeChunkModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            session.query(DocumentVersionModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            source = session.get(SourceDocumentModel, document_id)
            if source is not None:
                session.delete(source)
            session.commit()


def test_default_embedding_provider_is_siliconflow_compatible_bge_m3(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runtime_settings_service, "sync", lambda: None)
    monkeypatch.setattr(config, "EMBEDDING_MODE", "api")
    monkeypatch.setattr(config, "EMBEDDING_PROVIDER", "siliconflow")
    monkeypatch.setattr(config, "EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setattr(config, "EMBEDDING_API_KEY", "test-only-key")
    monkeypatch.setattr(config, "EMBEDDING_MODEL", "BAAI/bge-m3")
    provider = configured_embedding_provider(tmp_path)
    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.provider_id == "siliconflow"
    assert provider.model_id == "BAAI/bge-m3"
    assert COLLECTION != MEMORY_COLLECTION
