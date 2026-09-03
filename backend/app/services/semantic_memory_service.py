"""Derived semantic recall for canonical, evidence-backed Learning Memory."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from qdrant_client import models
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import LearningMemoryItemModel, VectorIndexStateModel
from app.services.rag_service import _point_id, _terms, rag_service


MEMORY_COLLECTION = "tiban_learning_memory_v32"
MEMORY_INDEX_KEY = "learning_memory"
MEMORY_SEMANTIC_MIN_SCORE = 0.55

# These are intentionally narrower than a general Chinese stop-word list.  A
# memory query such as “我最近整体哪里最弱” is a valid request for a recent
# overview, while “这个概念怎么理解” is not enough evidence to return an
# arbitrary memory merely because it is the newest row.
_MEMORY_STOP_TERMS = {
    "我们", "你们", "我最近", "最近", "整体", "学习", "学习情", "学习状", "情况",
    "哪里", "哪个", "哪些", "什么", "怎么", "如何", "为什么", "请问", "帮我",
    "告诉", "一下", "相关", "概念", "问题", "内容", "这个", "那个", "一下",
}
_RECENT_MEMORY_QUERY_MARKERS = (
    "最近", "整体", "学习情况", "学习状态", "过去", "历史作答", "哪里最弱",
    "薄弱点", "薄弱项", "复习什么", "复习计划", "学习计划", "接下来刷",
)


def _memory_text(item: LearningMemoryItemModel) -> str:
    labels = " ".join([*list(item.topic_keys or []), *list(item.concept_keys or [])])
    return f"{item.summary}\n主题与概念：{labels}".strip()


def _meaningful_overlap(query: str, item: LearningMemoryItemModel) -> int:
    """Return concept-bearing lexical overlap for a structured memory.

    ``rag_service._terms`` handles Chinese runs as bigrams and Latin terms as
    whole tokens.  Reusing it keeps semantic-memory fallback behavior aligned
    with governed Knowledge retrieval instead of using whitespace splitting,
    which treats an entire Chinese sentence as one unusable token.
    """

    query_terms = _terms(query)
    memory_terms = _terms(_memory_text(item))
    return sum(
        min(count, memory_terms.get(term, 0))
        for term, count in query_terms.items()
        if term not in _MEMORY_STOP_TERMS
    )


def _is_recent_memory_query(query: str) -> bool:
    lowered = query.casefold().strip()
    return any(marker.casefold() in lowered for marker in _RECENT_MEMORY_QUERY_MARKERS)


class SemanticMemoryService:
    """Qdrant is a bounded recall accelerator; PostgreSQL remains truth."""

    def mark_index_stale(self) -> None:
        provider = rag_service.embedding_provider
        with SessionLocal() as session:
            state = session.get(VectorIndexStateModel, MEMORY_INDEX_KEY)
            if state is None:
                session.add(VectorIndexStateModel(
                    index_key=MEMORY_INDEX_KEY,
                    provider=provider.provider_id,
                    model_id=provider.model_id,
                    status="stale",
                ))
            else:
                state.provider, state.model_id, state.status = provider.provider_id, provider.model_id, "stale"
                state.error_message = None
                state.index_version += 1
            session.commit()

    def rebuild(self) -> int:
        provider = rag_service.embedding_provider
        try:
            with SessionLocal() as session:
                state = session.get(VectorIndexStateModel, MEMORY_INDEX_KEY)
                if state is None:
                    state = VectorIndexStateModel(index_key=MEMORY_INDEX_KEY, provider=provider.provider_id, model_id=provider.model_id, status="rebuilding")
                    session.add(state)
                else:
                    state.provider, state.model_id, state.status, state.error_message = provider.provider_id, provider.model_id, "rebuilding", None
                rows = list(session.scalars(select(LearningMemoryItemModel).where(LearningMemoryItemModel.status == "active").order_by(LearningMemoryItemModel.updated_at)))
                session.commit()
            vectors = provider.embed_documents([_memory_text(row) for row in rows]) if rows else []
            client = rag_service.qdrant
            dimension = len(vectors[0]) if vectors else provider.dimension()
            if client.collection_exists(MEMORY_COLLECTION):
                client.delete_collection(MEMORY_COLLECTION)
            client.create_collection(MEMORY_COLLECTION, vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE))
            if rows:
                client.upsert(MEMORY_COLLECTION, points=[
                    models.PointStruct(
                        id=_point_id(row.memory_id),
                        vector=vector,
                        payload={
                            "memory_id": row.memory_id,
                            "learner_id": row.learner_id,
                            "domain_id": row.domain_id,
                            "status": row.status,
                            "version": row.version,
                        },
                    )
                    for row, vector in zip(rows, vectors)
                ], wait=True)
            with SessionLocal() as session:
                state = session.get(VectorIndexStateModel, MEMORY_INDEX_KEY)
                assert state is not None
                state.vector_dimension, state.status, state.indexed_at, state.error_message = dimension, "ready", datetime.utcnow(), None
                session.commit()
            return len(rows)
        except Exception as exc:
            with SessionLocal() as session:
                state = session.get(VectorIndexStateModel, MEMORY_INDEX_KEY)
                if state is None:
                    session.add(VectorIndexStateModel(index_key=MEMORY_INDEX_KEY, provider=provider.provider_id, model_id=provider.model_id, status="failed", error_message=type(exc).__name__))
                else:
                    state.status, state.error_message = "failed", type(exc).__name__
                session.commit()
            raise

    def sync_memory(self, memory_id: str) -> None:
        """Refresh the sole index. A stale signature is rebuilt, never mixed."""

        provider = rag_service.embedding_provider
        with SessionLocal() as session:
            state = session.get(VectorIndexStateModel, MEMORY_INDEX_KEY)
            item = session.get(LearningMemoryItemModel, memory_id)
            compatible = bool(
                state
                and state.status == "ready"
                and state.provider == provider.provider_id
                and state.model_id == provider.model_id
            )
        if not compatible:
            self.rebuild()
            return
        client = rag_service.qdrant
        if item is None or item.status != "active":
            client.delete(MEMORY_COLLECTION, points_selector=models.PointIdsList(points=[_point_id(memory_id)]), wait=True)
            return
        vector = provider.embed_query(_memory_text(item))
        client.upsert(MEMORY_COLLECTION, points=[models.PointStruct(
            id=_point_id(item.memory_id),
            vector=vector,
            payload={"memory_id": item.memory_id, "learner_id": item.learner_id, "domain_id": item.domain_id, "status": item.status, "version": item.version},
        )], wait=True)

    def retrieve(self, session: Session, *, learner_id: str, domain_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Return only relevant memories, with an explicit recent-query exception.

        PostgreSQL supplies the canonical, learner/domain-scoped candidates.
        Qdrant is an optional ranking accelerator; it is never allowed to turn
        an unrelated query into a fabricated memory hit.  When the vector
        index is unavailable, lexical overlap remains a truthful fallback.  A
        newest-first fallback is permitted only for an explicit overall/recent
        learning request, where “what have I recently been weak at?” is itself
        asking for a recency view rather than a concept lookup.
        """

        rows = list(session.scalars(select(LearningMemoryItemModel).where(
            LearningMemoryItemModel.learner_id == learner_id,
            LearningMemoryItemModel.domain_id == domain_id,
            LearningMemoryItemModel.status == "active",
        ).order_by(LearningMemoryItemModel.last_seen_at.desc()).limit(50)))
        if not rows:
            return []
        scores: dict[str, float] = {}
        provider = rag_service.embedding_provider
        state = session.get(VectorIndexStateModel, MEMORY_INDEX_KEY)
        if state and state.status == "ready" and state.provider == provider.provider_id and state.model_id == provider.model_id:
            try:
                points = rag_service.qdrant.query_points(
                    MEMORY_COLLECTION,
                    query=provider.embed_query(query),
                    limit=max(limit * 3, 10),
                    with_payload=True,
                    query_filter=models.Filter(must=[
                        models.FieldCondition(key="learner_id", match=models.MatchValue(value=learner_id)),
                        models.FieldCondition(key="domain_id", match=models.MatchValue(value=domain_id)),
                        models.FieldCondition(key="status", match=models.MatchValue(value="active")),
                    ]),
                ).points
                scores = {str(point.payload.get("memory_id")): float(point.score) for point in points}
            except Exception:
                scores = {}
        recent_query = _is_recent_memory_query(query)
        ranked = sorted(
            (
                item
                for item in rows
                if (
                    _meaningful_overlap(query, item) > 0
                    or scores.get(item.memory_id, 0.0) >= MEMORY_SEMANTIC_MIN_SCORE
                    or recent_query
                )
            ),
            key=lambda item: (
                _meaningful_overlap(query, item),
                scores.get(item.memory_id, 0.0),
                item.confidence,
                item.last_seen_at,
            ),
            reverse=True,
        )[: max(1, min(limit, 5))]
        return [
            {
                "memory_id": item.memory_id,
                "kind": item.kind,
                "summary": item.summary,
                "topic_keys": list(item.topic_keys or []),
                "concept_keys": list(item.concept_keys or []),
                "confidence": item.confidence,
                "evidence_count": len(item.evidence_refs or []),
                "semantic_score": round(scores.get(item.memory_id, 0.0), 5) if item.memory_id in scores else None,
            }
            for item in ranked
        ]


semantic_memory_service = SemanticMemoryService()
