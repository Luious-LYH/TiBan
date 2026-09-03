from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import DocumentVersionModel, FactoryJobModel, KnowledgeChunkModel, SourceDocumentModel, VectorIndexStateModel
from app.main import app
from app.routers import api as api_router
from app.routers import factory as factory_router
from app.services.embedding_provider import OpenAICompatibleEmbeddingProvider
from app.services.factory_service import import_allowed_document
from app.services.rag_service import COLLECTION, rag_service
from app.workers import background_worker, factory_worker


def test_openai_embedding_batches_preserve_order_and_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        provider_id="test", model_id="test-embedding", base_url="https://example.test/v1",
        api_key="test-key", timeout_seconds=1,
    )
    monkeypatch.setattr("app.services.embedding_provider.embedding_batch_size", lambda: 2)
    calls: list[list[str]] = []

    def request(body: dict[str, object]) -> dict[str, object]:
        batch = [str(item) for item in body["input"]]  # type: ignore[index]
        calls.append(batch)
        return {"data": [
            {"index": index, "embedding": [float(len(value)), float(index)]}
            for index, value in reversed(list(enumerate(batch)))
        ]}

    monkeypatch.setattr(provider, "_request", request)
    vectors = provider.embed_documents(["a", "bb", "ccc"])

    assert calls == [["a", "bb"], ["ccc"]]
    assert vectors == [[1.0, 0.0], [2.0, 1.0], [3.0, 0.0]]
    assert provider.dimension() == 2


def test_embedding_batch_dimension_failure_does_not_return_partial_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        provider_id="test", model_id="test-embedding", base_url="https://example.test/v1",
        api_key="test-key", timeout_seconds=1,
    )
    monkeypatch.setattr("app.services.embedding_provider.embedding_batch_size", lambda: 1)
    responses = iter([
        {"data": [{"embedding": [1.0, 2.0]}]},
        {"data": [{"embedding": [1.0, 2.0, 3.0]}]},
    ])
    monkeypatch.setattr(provider, "_request", lambda _body: next(responses))

    with pytest.raises(RuntimeError, match="embedding_vector_dimensions_inconsistent"):
        provider.embed_documents(["a", "b"])
    assert provider._dimension is None


def test_factory_dispatch_failure_is_durable_and_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    document = import_allowed_document(
        f"dispatch-{uuid4().hex[:8]}.md",
        b"# Teaching source\n\nThis is a sufficiently long source for dispatch failure testing.",
        "text/markdown",
    )

    def fail_send(*_args: object, **_kwargs: object) -> None:
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(factory_router.process_factory_job_actor, "send", fail_send)
    client = TestClient(app)
    response = client.post("/api/v3/factory/jobs", json={"document_id": document["document_id"]})
    assert response.status_code == 503
    with SessionLocal() as session:
        job = session.query(FactoryJobModel).filter_by(document_id=document["document_id"]).one()
        assert job.status == "failed"
        assert job.stage == "dispatch_failed"
        assert job.error_code == "dispatch_failed"

    with SessionLocal() as session:
        version = session.query(DocumentVersionModel).filter_by(document_id=document["document_id"]).all()
        session.query(FactoryJobModel).filter_by(document_id=document["document_id"]).delete(synchronize_session=False)
        session.query(DocumentVersionModel).filter_by(document_id=document["document_id"]).delete(synchronize_session=False)
        source = session.get(SourceDocumentModel, document["document_id"])
        if source is not None:
            session.delete(source)
        session.commit()
    for item in version:
        Path(item.source_path).unlink(missing_ok=True)


def test_readiness_reports_db_schema_queue_and_qdrant_without_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRedis:
        @classmethod
        def from_url(cls, *_args: object, **_kwargs: object) -> "FakeRedis":
            return cls()

        def ping(self) -> bool:
            return True

    class FakeQdrant:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def get_collections(self) -> object:
            return {"collections": []}

    monkeypatch.setattr(api_router.redis, "Redis", FakeRedis)
    monkeypatch.setattr(api_router, "QdrantClient", FakeQdrant)
    response = TestClient(app).get("/api/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert set(payload["checks"]) == {"database", "schema", "redis", "qdrant"}
    assert "llm" not in payload["checks"]


def test_worker_readiness_is_independent_from_embedding_prewarm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ready = tmp_path / "worker-ready"
    monkeypatch.setenv("FACTORY_WORKER_READY_FILE", str(ready))
    monkeypatch.setenv("FACTORY_EMBEDDING_PREWARM", "false")
    monkeypatch.setattr(factory_worker.rag_service, "prewarm", lambda: pytest.fail("prewarm must not run"))

    factory_worker._write_worker_ready()
    factory_worker._prewarm_embedding_if_configured()

    assert ready.read_text(encoding="utf-8") == "broker_and_actors_ready\n"
    assert not ready.with_name("worker-ready.embedding").exists()
    assert factory_worker.broker is background_worker.broker


def test_incremental_knowledge_reindex_only_replaces_target_document(monkeypatch: pytest.MonkeyPatch) -> None:
    token = uuid4().hex[:10]
    target_id, other_id = f"incremental-target-{token}", f"incremental-other-{token}"
    now = datetime.utcnow()
    with SessionLocal() as session:
        for document_id, name, content in ((target_id, "目标资料", "目标资料中的心力衰竭证据。"), (other_id, "其他资料", "其他资料中的心律失常证据。")):
            version_id = f"{document_id}-v1"
            session.add(SourceDocumentModel(
                document_id=document_id, domain_id="endoscopy", name=name, media_type="text/markdown",
                content_hash=token, status="ready", business_usage="knowledge_base", license_gate_status="allow",
                ai_ingestion_allowed=True, namespace="system", source_scope="system", enabled=True,
            ))
            session.add(DocumentVersionModel(
                version_id=version_id, document_id=document_id, version_label="v1", source_path="test.md",
                content_hash=token, parser="test", status="indexed", created_at=now,
            ))
            session.add(KnowledgeChunkModel(
                chunk_id=f"{document_id}-chunk", document_id=document_id, version_id=version_id,
                parent_section=name, page=1, ordinal=0, content=content, content_hash=token,
                token_count=len(content), namespace="system",
            ))
        session.add(DocumentVersionModel(
            version_id=f"{target_id}-old", document_id=target_id, version_label="old", source_path="test.md",
            content_hash=f"old-{token}", parser="test", status="indexed", created_at=now - timedelta(minutes=1),
        ))
        session.add(KnowledgeChunkModel(
            chunk_id=f"{target_id}-old-chunk", document_id=target_id, version_id=f"{target_id}-old",
            parent_section="旧目标资料", page=1, ordinal=0, content="旧目标资料中的过期证据。", content_hash=f"old-{token}",
            token_count=12, namespace="system",
        ))
        state = session.get(VectorIndexStateModel, "knowledge")
        if state is None:
            session.add(VectorIndexStateModel(
                index_key="knowledge", provider="fake", model_id="fake-v1", vector_dimension=2,
                status="ready", index_version=1,
            ))
        else:
            state.provider, state.model_id, state.vector_dimension, state.status = "fake", "fake-v1", 2, "ready"
        session.commit()

    class FakeProvider:
        provider_id = "fake"
        model_id = "fake-v1"

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            assert texts == ["目标资料中的心力衰竭证据。"]
            return [[1.0, 0.0]]

        def dimension(self) -> int:
            return 2

    class FakeQdrant:
        def __init__(self) -> None:
            self.upserted: list[object] = []
            self.deleted: list[object] = []

        def collection_exists(self, collection: str) -> bool:
            assert collection == COLLECTION
            return True

        def upsert(self, _collection: str, *, points: list[object], wait: bool) -> None:
            self.upserted.extend(points)

        def delete(self, _collection: str, *, points_selector: object, wait: bool) -> None:
            self.deleted.append(points_selector)

    fake_qdrant = FakeQdrant()
    monkeypatch.setattr(type(rag_service), "embedding_provider", property(lambda _self: FakeProvider()))
    monkeypatch.setattr(type(rag_service), "qdrant", property(lambda _self: fake_qdrant))
    result = rag_service.rebuild_knowledge_index(document_ids=[target_id])
    assert result == [f"{target_id}-chunk"]
    assert len(fake_qdrant.upserted) == 1
    assert len(fake_qdrant.deleted) == 1

    with SessionLocal() as session:
        session.query(KnowledgeChunkModel).filter(KnowledgeChunkModel.document_id.in_([target_id, other_id])).delete(synchronize_session=False)
        session.query(DocumentVersionModel).filter(DocumentVersionModel.document_id.in_([target_id, other_id])).delete(synchronize_session=False)
        session.query(SourceDocumentModel).filter(SourceDocumentModel.document_id.in_([target_id, other_id])).delete(synchronize_session=False)
        session.commit()
