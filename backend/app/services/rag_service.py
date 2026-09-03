"""Qdrant-backed dense retrieval plus transparent sparse/hybrid baselines."""

from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Iterable, Literal

from qdrant_client import QdrantClient, models
from sqlalchemy import func, select

from app.core.config import DEFAULT_DOMAIN_ID, DEFAULT_KNOWLEDGE_NAMESPACE, QDRANT_URL
from app.db.database import SessionLocal
from app.db.models import DocumentVersionModel, KnowledgeChunkModel, SourceDocumentModel, VectorIndexStateModel
from app.services.embedding_provider import EmbeddingProvider, RerankerProvider, configured_embedding_provider, configured_reranker_provider


MODEL_NAME = 'BAAI/bge-m3'
RERANK_MODEL = 'BAAI/bge-reranker-v2-m3'
COLLECTION = 'tiban_knowledge_v32'
KNOWLEDGE_INDEX_KEY = 'knowledge'
MODEL_CACHE = Path(os.getenv('ENDO_EMBEDDING_CACHE', Path(__file__).resolve().parents[2] / 'runtime' / 'fastembed'))


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    document_name: str
    page: int
    section: str
    snippet: str
    score: float
    document_id: str | None = None
    namespace: str = DEFAULT_KNOWLEDGE_NAMESPACE
    source_uri: str | None = None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _terms(value: str) -> Counter[str]:
    """Tokenize Latin identifiers and CJK text without cross-token noise.

    The previous all-character bigram tokenizer made an identifier such as a
    unique evaluation marker partially match every older document containing
    a generic suffix (for example ``general``).  That is especially harmful to
    namespace isolation tests and to explainable sparse retrieval.  Preserve
    CJK bigrams for Chinese retrieval, while treating ASCII identifiers/words
    as whole tokens.
    """

    terms: list[str] = []
    for token in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", value.lower()):
        if re.fullmatch(r"[a-z0-9_]+", token):
            terms.append(token)
        else:
            terms.extend(token[index:index + 2] for index in range(max(len(token) - 1, 0)))
    return Counter(terms)


def _sparse_score(query: str, content: str) -> float:
    left, right = _terms(query), _terms(content)
    if not left or not right:
        return 0.0
    return sum(min(left[key], right[key]) for key in left) / max(sum(left.values()), 1)


# These instruction words occur in almost every explicit retrieval request but
# say nothing about the medical concept being requested.  Letting them pass the
# evidence gate is how a request such as "根据资料解释当前题" used to cite a
# merely adjacent question-bank explanation.  Keep the ranking signal intact;
# this list is only used to decide whether a result is credible enough to show
# as learner-facing evidence.
_RETRIEVAL_INSTRUCTION_TERMS = {
    "根据", "据资", "资料", "料解", "解释", "释当", "当前", "前题", "题目",
    "题考", "考点", "并给", "给出", "来源", "知识", "识库", "上传", "我的",
    "请问", "一下", "什么", "怎么", "如何", "有关", "相关", "内容", "学习",
    # Function-word bigrams that are common at the end of a Chinese question
    # (for example “……的药是”) must not bridge two unrelated items.
    "的药", "药是", "的是", "一种", "这个", "那个", "资料", "source", "sources",
    "citation", "citations",
}


def _meaningful_lexical_overlap(query: str, content: str) -> int:
    """Count concept-bearing lexical overlap for citation eligibility.

    Dense/RRF ranking is deliberately still available to order candidates.
    A citation, however, needs at least two non-instruction lexical anchors.
    That accepts a real ``heart failure`` match and Chinese medical concepts,
    while allowing a truthful zero-hit result when the library has no direct
    source for the current question.
    """

    left = _terms(query)
    right = _terms(content)
    return sum(
        min(count, right.get(term, 0))
        for term, count in left.items()
        if term not in _RETRIEVAL_INSTRUCTION_TERMS
    )


class RagService:
    def __init__(self) -> None:
        self._embedding_provider: EmbeddingProvider | None = None
        self._reranker_provider: RerankerProvider | None = None
        self._provider_signature: tuple[str, str, str, str] | None = None
        self._reranker_signature: tuple[str, str, str, str] | None = None

    @staticmethod
    def _provider_signature_for(provider: object) -> tuple[str, str, str, str]:
        """Fingerprint all runtime inputs without retaining a secret value.

        Provider/model alone is insufficient: an instance owner can change a
        compatible endpoint or rotate its key while keeping both names the
        same. The hash makes the process-local cache follow those changes
        without putting the key into logs, API payloads, or diagnostics.
        """

        provider_id = str(getattr(provider, "provider_id", ""))
        model_id = str(getattr(provider, "model_id", ""))
        runtime_inputs = "\x00".join(str(getattr(provider, name, "")) for name in (
            "base_url", "api_key", "timeout_seconds", "cache_dir",
        ))
        return (type(provider).__name__, provider_id, model_id, _hash(runtime_inputs))

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        """Return the active provider, replacing stale process-local adapters."""

        provider = configured_embedding_provider(MODEL_CACHE)
        signature = self._provider_signature_for(provider)
        if self._embedding_provider is None or self._provider_signature != signature:
            self._embedding_provider = provider
            self._provider_signature = signature
        return self._embedding_provider

    @property
    def qdrant(self) -> QdrantClient:
        # A fresh local Qdrant volume can take several seconds to create its
        # first collection.  The client default is shorter than that on some
        # Docker Desktop machines, which turns a healthy clean-start into a
        # false Factory indexing failure.
        timeout = float(os.getenv('QDRANT_TIMEOUT_SECONDS', '30'))
        return QdrantClient(url=QDRANT_URL, timeout=timeout)

    @property
    def reranker_provider(self) -> RerankerProvider:
        provider = configured_reranker_provider(MODEL_CACHE)
        signature = self._provider_signature_for(provider)
        if self._reranker_provider is None or self._reranker_signature != signature:
            self._reranker_provider = provider
            self._reranker_signature = signature
        return self._reranker_provider

    def prewarm(self) -> dict[str, object]:
        """Initialize the dense embedding path before a Factory actor accepts work.

        This performs the real model load and one harmless embedding in the
        worker process.  It deliberately does not create a collection, index
        content, or mutate business data.
        """

        started = perf_counter()
        provider = self.embedding_provider
        vector = provider.embed_query("题伴题目生成服务就绪检查")
        return {
            "provider": provider.provider_id,
            "model": provider.model_id,
            "vector_size": len(vector),
            "elapsed_ms": round((perf_counter() - started) * 1000),
        }

    def index_markdown(
        self,
        path: Path,
        *,
        document_id: str = 'source-stage2-endoscopy-v1',
        document_name: str | None = None,
        domain_id: str = DEFAULT_DOMAIN_ID,
        child_size: int = 180,
        namespace: str = DEFAULT_KNOWLEDGE_NAMESPACE,
        source_id: str | None = None,
        source_uri: str | None = None,
        business_usage: str = 'knowledge_base',
        license_gate_status: str = 'allow_noncommercial',
        ai_ingestion_allowed: bool = True,
        version_label: str | None = None,
    ) -> list[str]:
        text = path.read_text(encoding='utf-8')
        resolved_document_name = document_name or path.name
        source_hash = _hash(text)
        chunks = list(_chunk_markdown(_strip_frontmatter(text), child_size))
        # Chunk identity changed in Stage 2 so identical uploads can coexist
        # without primary-key collisions.  Keep the previous runtime index
        # untouched for auditability; v2 is the only version eligible for new
        # benchmark/product retrieval and therefore can never mix both IDs.
        version_id = f'{document_id}-{source_hash[:12]}-{child_size}-v2'
        resolved_version_label = version_label or (
            f'retrieval-eval-v1-child-{child_size}-identity-v2'
            if document_id == 'source-stage2-endoscopy-v1'
            else f'factory-index-v1-child-{child_size}-identity-v2'
        )
        with SessionLocal() as session:
            document = session.get(SourceDocumentModel, document_id)
            if not document:
                session.add(SourceDocumentModel(document_id=document_id, domain_id=domain_id, bank_id=None, name=resolved_document_name, media_type='text/markdown', content_hash=source_hash, status='indexed', source_id=source_id, business_usage=business_usage, license_gate_status=license_gate_status, ai_ingestion_allowed=ai_ingestion_allowed, source_uri=source_uri or str(path.resolve()), namespace=namespace))
                session.flush()
            else:
                document.name = resolved_document_name
                document.namespace = namespace
                document.domain_id = domain_id
                document.source_id = source_id or document.source_id
                document.source_uri = source_uri or document.source_uri or str(path.resolve())
                document.business_usage = business_usage
                document.license_gate_status = license_gate_status
                document.ai_ingestion_allowed = ai_ingestion_allowed
            if not session.get(DocumentVersionModel, version_id):
                session.add(DocumentVersionModel(version_id=version_id, document_id=document_id, version_label=resolved_version_label, source_path=str(path.resolve()), content_hash=source_hash, parser='heading-aware-markdown', status='indexed'))
            for ordinal, (section, content) in enumerate(chunks):
                # The same allowed content may be uploaded more than once;
                # include document identity so globally keyed chunks retain
                # both provenance paths without a collision.
                chunk_id = f'chunk-{document_id[-12:]}-{source_hash[:8]}-{child_size}-{ordinal:02d}-v2'
                # Dramatiq may retry after a transient Qdrant failure.  The
                # relational chunk insert is idempotent across such retries.
                chunk = session.get(KnowledgeChunkModel, chunk_id)
                if chunk is None:
                    session.add(KnowledgeChunkModel(chunk_id=chunk_id, document_id=document_id, version_id=version_id, parent_section=section, page=_page_from_section(section), ordinal=ordinal, content=content, content_hash=_hash(content), token_count=len(content), namespace=namespace, source_uri=source_uri or str(path.resolve())))
                else:
                    # Re-indexing is idempotent but also refreshes parser
                    # output when a curated note's frontmatter or section
                    # handling changes.
                    chunk.parent_section = section
                    chunk.page = _page_from_section(section)
                    chunk.ordinal = ordinal
                    chunk.content = content
                    chunk.content_hash = _hash(content)
                    chunk.token_count = len(content)
                    chunk.namespace = namespace
                    chunk.source_uri = source_uri or str(path.resolve())
            session.commit()
        # The document rows are canonical and committed before vector work.
        # Rebuild all eligible chunks when the active vector signature changed
        # so an API query never mixes model A documents with a model B query.
        return self.rebuild_knowledge_index(document_ids=[document_id])

    def delete_documents(self, document_ids: list[str]) -> None:
        """Remove only the specified documents' derived vector points."""
        if not document_ids:
            return
        client = self.qdrant
        if not client.collection_exists(COLLECTION):
            return
        client.delete(
            COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[models.FieldCondition(key='document_id', match=models.MatchAny(any=document_ids))])
            ),
            wait=True,
        )

    def index_state(self) -> dict[str, object]:
        provider = self.embedding_provider
        with SessionLocal() as session:
            state = session.get(VectorIndexStateModel, KNOWLEDGE_INDEX_KEY)
            if state is None:
                return {
                    "provider": provider.provider_id,
                    "model": provider.model_id,
                    "status": "stale",
                    "vector_dimension": None,
                    "index_version": 0,
                }
            status = state.status
            # A ready marker is only valid for the exact active vector space.
            # This prevents an old test/local index (or a previous model) from
            # being queried with the current provider and from being reported
            # as ready in Settings.
            if status == "ready" and (
                state.provider != provider.provider_id
                or state.model_id != provider.model_id
                or not state.vector_dimension
            ):
                status = "stale"
            return {
                "provider": state.provider,
                "model": state.model_id,
                "status": status,
                "vector_dimension": state.vector_dimension,
                "index_version": state.index_version,
                "indexed_at": state.indexed_at,
                "error_message": state.error_message,
            }

    def mark_index_stale(self) -> dict[str, object]:
        provider = self.embedding_provider
        with SessionLocal() as session:
            state = session.get(VectorIndexStateModel, KNOWLEDGE_INDEX_KEY)
            if state is None:
                state = VectorIndexStateModel(
                    index_key=KNOWLEDGE_INDEX_KEY,
                    provider=provider.provider_id,
                    model_id=provider.model_id,
                    status="stale",
                )
                session.add(state)
            else:
                state.provider = provider.provider_id
                state.model_id = provider.model_id
                state.status = "stale"
                state.error_message = None
                state.index_version += 1
            session.commit()
        return self.index_state()

    def rebuild_knowledge_index(self, *, document_ids: list[str] | None = None) -> list[str]:
        """Build canonical vectors, incrementally for ordinary one-document work.

        Upload/reindex calls pass one or more document IDs. When the active
        provider and vector dimension are unchanged, only those documents are
        embedded and upserted; their old point IDs are removed *after* the new
        points succeed. First build, provider/model changes, dimension changes,
        and an unavailable collection use the full-corpus path.
        """

        provider = self.embedding_provider
        requested_ids = {str(value) for value in (document_ids or []) if str(value)}
        previous_ready = False
        previous_dimension: int | None = None
        incremental = False
        try:
            with SessionLocal() as session:
                state = session.get(VectorIndexStateModel, KNOWLEDGE_INDEX_KEY)
                previous_ready = bool(
                    state is not None
                    and state.status == "ready"
                    and state.provider == provider.provider_id
                    and state.model_id == provider.model_id
                    and state.vector_dimension
                )
                previous_dimension = state.vector_dimension if state is not None else None
                if requested_ids and previous_ready:
                    # A collection check is intentionally limited to the
                    # incremental decision. If no collection exists, a
                    # single-document call must bootstrap the complete index.
                    incremental = self.qdrant.collection_exists(COLLECTION)
                if state is None:
                    state = VectorIndexStateModel(
                        index_key=KNOWLEDGE_INDEX_KEY,
                        provider=provider.provider_id,
                        model_id=provider.model_id,
                        status="rebuilding",
                    )
                    session.add(state)
                else:
                    state.provider, state.model_id, state.status, state.error_message = provider.provider_id, provider.model_id, "rebuilding", None
                session.commit()

                statement = (
                    select(KnowledgeChunkModel, SourceDocumentModel, DocumentVersionModel)
                    .join(SourceDocumentModel, SourceDocumentModel.document_id == KnowledgeChunkModel.document_id)
                    .join(DocumentVersionModel, DocumentVersionModel.version_id == KnowledgeChunkModel.version_id)
                    .where(
                        SourceDocumentModel.business_usage == "knowledge_base",
                        SourceDocumentModel.business_usage != "benchmark_only",
                        SourceDocumentModel.business_usage != "excluded",
                        SourceDocumentModel.ai_ingestion_allowed.is_(True),
                        SourceDocumentModel.enabled.is_(True),
                        # ``indexing`` is an internal build state for the
                        # source currently being prepared; it is allowed into
                        # the worker's candidate set and becomes learner-
                        # retrievable only after KnowledgeService marks it
                        # ready. Other transitional states stay excluded.
                        SourceDocumentModel.status.not_in(["queued", "rebuilding", "uploaded", "failed", "disabled", "retired"]),
                        SourceDocumentModel.license_gate_status.in_(["allow", "allow_noncommercial"]),
                    )
                    .order_by(KnowledgeChunkModel.document_id, KnowledgeChunkModel.ordinal)
                )
                # An incompatible single-document request must still rebuild
                # every eligible document so the collection is one coherent
                # vector space. Compatible requests stay document-local.
                if incremental:
                    statement = statement.where(KnowledgeChunkModel.document_id.in_(requested_ids))
                versioned_rows = list(session.execute(statement).all())
                old_target_ids = set(session.scalars(
                    select(KnowledgeChunkModel.chunk_id).where(KnowledgeChunkModel.document_id.in_(requested_ids))
                )) if incremental else set()

            latest_version: dict[str, tuple[datetime, str]] = {}
            for chunk, document, version in versioned_rows:
                candidate = (version.created_at, version.version_id)
                current = latest_version.get(document.document_id)
                if current is None or candidate > current:
                    latest_version[document.document_id] = candidate
            rows = [
                (chunk, document)
                for chunk, document, version in versioned_rows
                if latest_version.get(document.document_id) == (version.created_at, version.version_id)
            ]

            if not rows:
                if incremental:
                    self._delete_point_ids(old_target_ids)
                    self._finish_index_state(provider, previous_dimension or provider.dimension())
                else:
                    self._replace_collection(provider, [])
                    self._finish_index_state(provider, 0)
                return []

            vectors = provider.embed_documents([chunk.content for chunk, _ in rows])
            if len(vectors) != len(rows) or any(not vector for vector in vectors):
                raise RuntimeError("embedding_vectors_invalid")
            points = [
                models.PointStruct(
                    id=_point_id(chunk.chunk_id),
                    vector=vector,
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "version_id": chunk.version_id,
                        "domain_id": document.domain_id,
                        "namespace": chunk.namespace,
                        "document_name": document.name,
                        "page": chunk.page,
                        "section": chunk.parent_section,
                        "source_uri": chunk.source_uri,
                        "content": chunk.content,
                    },
                )
                for (chunk, document), vector in zip(rows, vectors)
            ]
            if incremental:
                self.qdrant.upsert(COLLECTION, points=points, wait=True)
                current_ids = {chunk.chunk_id for chunk, _ in rows}
                self._delete_point_ids(old_target_ids - current_ids)
            else:
                self._replace_collection(provider, vectors)
                self.qdrant.upsert(COLLECTION, points=points, wait=True)
            self._finish_index_state(provider, len(vectors[0]))
            return [chunk.chunk_id for chunk, _ in rows]
        except Exception as exc:
            # A compatible incremental failure leaves the previous collection
            # usable. Mark its state ready with an error note so retrieval can
            # continue while the source remains visibly retryable.
            self._fail_index_state(provider, type(exc).__name__, preserve_ready=previous_ready and incremental)
            raise

    def _delete_point_ids(self, chunk_ids: set[str]) -> None:
        if not chunk_ids:
            return
        self.qdrant.delete(
            COLLECTION,
            points_selector=models.PointIdsList(points=[_point_id(chunk_id) for chunk_id in chunk_ids]),
            wait=True,
        )

    def _replace_collection(self, provider: EmbeddingProvider, vectors: list[list[float]]) -> None:
        client = self.qdrant
        dimension = len(vectors[0]) if vectors else provider.dimension()
        if client.collection_exists(COLLECTION):
            client.delete_collection(COLLECTION)
        client.create_collection(COLLECTION, vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE))

    def _finish_index_state(self, provider: EmbeddingProvider, dimension: int) -> None:
        from datetime import datetime

        with SessionLocal() as session:
            state = session.get(VectorIndexStateModel, KNOWLEDGE_INDEX_KEY)
            assert state is not None
            state.provider, state.model_id = provider.provider_id, provider.model_id
            state.vector_dimension, state.status, state.indexed_at, state.error_message = dimension, "ready", datetime.utcnow(), None
            session.commit()

    def _fail_index_state(self, provider: EmbeddingProvider, error: str, *, preserve_ready: bool = False) -> None:
        with SessionLocal() as session:
            state = session.get(VectorIndexStateModel, KNOWLEDGE_INDEX_KEY)
            if state is None:
                state = VectorIndexStateModel(index_key=KNOWLEDGE_INDEX_KEY, provider=provider.provider_id, model_id=provider.model_id, status="failed", error_message=error)
                session.add(state)
            else:
                state.status, state.error_message = ("ready" if preserve_ready else "failed"), error
            session.commit()

    def retrieve(
        self,
        query: str,
        mode: Literal['sparse', 'dense', 'hybrid', 'hybrid_rerank'] = 'hybrid',
        limit: int = 5,
        *,
        version_id: str | None = None,
        version_ids: list[str] | None = None,
        document_ids: list[str] | None = None,
        domain_id: str | None = None,
        namespace: str | None = None,
        namespaces: list[str] | None = None,
    ) -> list[Citation]:
        started = perf_counter()
        with SessionLocal() as session:
            # Product retrieval intentionally uses one frozen, benchmarked
            # version. Historical chunks remain for artifact reproducibility but
            # must never leak into Tutor citations.
            # An explicit version is required for frozen benchmark runs.  A
            # namespace-scoped product query intentionally searches all
            # approved documents in that namespace so newly curated KB notes
            # are visible to Tutor without changing the benchmark artifact.
            if version_id is None and not version_ids and not document_ids and namespace is None and not namespaces:
                active = session.scalar(
                    select(DocumentVersionModel.version_id)
                    .where(DocumentVersionModel.document_id == 'source-stage2-endoscopy-v1', DocumentVersionModel.version_label == 'retrieval-eval-v1-child-180-identity-v2')
                    .order_by(DocumentVersionModel.created_at.desc())
                )
                version_id = active
            statement = select(KnowledgeChunkModel).order_by(KnowledgeChunkModel.ordinal)
            if version_id:
                statement = statement.where(KnowledgeChunkModel.version_id == version_id)
            elif version_ids:
                statement = statement.where(KnowledgeChunkModel.version_id.in_(version_ids))
            if document_ids:
                statement = statement.where(KnowledgeChunkModel.document_id.in_(document_ids))
            if namespace:
                statement = statement.where(KnowledgeChunkModel.namespace == namespace)
            elif namespaces:
                statement = statement.where(KnowledgeChunkModel.namespace.in_(namespaces))
            # A benchmark row is never eligible even if a caller accidentally
            # points at a historical version.  License and ingestion are data
            # policy, not a UI convention.
            statement = statement.join(SourceDocumentModel, SourceDocumentModel.document_id == KnowledgeChunkModel.document_id).where(
                SourceDocumentModel.business_usage == 'knowledge_base',
                SourceDocumentModel.business_usage != 'benchmark_only',
                SourceDocumentModel.business_usage != 'excluded',
                SourceDocumentModel.ai_ingestion_allowed.is_(True),
                SourceDocumentModel.enabled.is_(True),
                # ``ready`` is the current lifecycle value.  ``indexed`` and
                # ``seed`` are retained for pre-V3.2 canonical sources and
                # SQLite fixtures whose content is already present in the
                # relational chunk graph.  Transitional/error states remain
                # excluded so a queued source cannot become a citation.
                SourceDocumentModel.status.not_in(['queued', 'rebuilding', 'indexing', 'uploaded', 'failed', 'disabled', 'retired']),
                SourceDocumentModel.license_gate_status.in_(['allow', 'allow_noncommercial']),
            )
            if version_id is None and not version_ids:
                # Historical versions remain in PostgreSQL for audit and
                # rollback, but product retrieval must describe the current
                # canonical version.  Without this relational gate, sparse
                # retrieval could cite an old chunk even though the rebuilt
                # Qdrant collection contains only the newest version.
                latest_versions = select(
                    DocumentVersionModel.version_id,
                    func.row_number().over(
                        partition_by=DocumentVersionModel.document_id,
                        order_by=(DocumentVersionModel.created_at.desc(), DocumentVersionModel.version_id.desc()),
                    ).label('version_rank'),
                ).subquery('latest_retrievable_versions')
                statement = statement.join(
                    latest_versions,
                    KnowledgeChunkModel.version_id == latest_versions.c.version_id,
                ).where(latest_versions.c.version_rank == 1)
            if domain_id:
                statement = statement.where(SourceDocumentModel.domain_id == domain_id)
            rows = list(session.scalars(statement))
            docs = {doc.document_id: doc for doc in session.scalars(select(SourceDocumentModel).where(SourceDocumentModel.document_id.in_({row.document_id for row in rows})))}
        if not rows:
            return []
        eligible_document_ids = sorted({row.document_id for row in rows})
        sparse = {row.chunk_id: _sparse_score(query, row.content) for row in rows}
        dense: dict[str, float] = {}
        state = self.index_state()
        active_provider = self.embedding_provider
        dense_allowed = (
            mode != "sparse"
            and state.get("status") == "ready"
            and state.get("provider") == active_provider.provider_id
            and state.get("model") == active_provider.model_id
        )
        if dense_allowed:
            vector = active_provider.embed_query(query)
            conditions = []
            if version_id:
                conditions.append(models.FieldCondition(key='version_id', match=models.MatchValue(value=version_id)))
            elif version_ids:
                conditions.append(models.FieldCondition(key='version_id', match=models.MatchAny(any=version_ids)))
            if document_ids:
                conditions.append(models.FieldCondition(key='document_id', match=models.MatchAny(any=document_ids)))
            if domain_id:
                conditions.append(models.FieldCondition(key='domain_id', match=models.MatchValue(value=domain_id)))
            if namespace:
                conditions.append(models.FieldCondition(key='namespace', match=models.MatchValue(value=namespace)))
            elif namespaces:
                conditions.append(models.FieldCondition(key='namespace', match=models.MatchAny(any=namespaces)))
            # Qdrant is a derived index. Keep its candidates aligned with the
            # governed relational source graph so retired documents cannot
            # occupy dense-retrieval result slots.
            conditions.append(models.FieldCondition(key='document_id', match=models.MatchAny(any=eligible_document_ids)))
            query_filter = models.Filter(must=conditions) if conditions else None
            try:
                result = self.qdrant.query_points(COLLECTION, query=vector, limit=max(limit * 3, 10), with_payload=True, query_filter=query_filter).points
                dense = {str(point.payload['chunk_id']): float(point.score) for point in result}
            except Exception:
                dense = {}
        scores: dict[str, float] = {}
        for row in rows:
            if mode == 'sparse':
                scores[row.chunk_id] = sparse[row.chunk_id]
            elif mode == 'dense' and dense_allowed:
                scores[row.chunk_id] = dense.get(row.chunk_id, 0.0)
            else:
                scores[row.chunk_id] = _rrf_rank(sparse, row.chunk_id) + _rrf_rank(dense, row.chunk_id)
        # RRF always gives every dense candidate a small positive score. That
        # is useful for ranking, but it is not evidence of relevance: without
        # this gate an unrelated query still received several citations from a
        # tiny corpus. A concrete lexical overlap is the conservative first
        # calibration for this bilingual, source-governed library. Cross-
        # language sources with no matching terms correctly produce zero hits
        # instead of an invented citation.
        candidates = [
            row
            for row in sorted(rows, key=lambda row: scores[row.chunk_id], reverse=True)
            if _meaningful_lexical_overlap(query, row.content) >= 2
        ][:max(limit * 4, 20)]
        if mode == 'hybrid_rerank' and candidates:
            # This is a learned cross-encoder inference, not a lexical score
            # boost.  Its score only orders candidate passages after hybrid RRF.
            try:
                rerank_scores = self.reranker_provider.score(query, [row.content for row in candidates])
                selected = [row for _, row in sorted(zip(rerank_scores, candidates), key=lambda item: float(item[0]), reverse=True)[:limit]]
                scores = {**scores, **{row.chunk_id: float(score) for score, row in zip(rerank_scores, candidates)}}
            except Exception:
                selected = candidates[:limit]
        else:
            selected = candidates[:limit]
        # Adjacent chunks from the same document/section seldom add evidence
        # value. Keep one best passage per section so citations remain compact.
        deduped: list[KnowledgeChunkModel] = []
        seen_sections: set[tuple[str, str]] = set()
        for row in selected:
            key = (row.document_id, row.parent_section)
            if key not in seen_sections:
                seen_sections.add(key)
                deduped.append(row)
        selected = deduped[:limit]
        _ = perf_counter() - started
        return [Citation(chunk_id=row.chunk_id, document_name=docs.get(row.document_id).name if row.document_id in docs else '教学资料', page=row.page, section=row.parent_section, snippet=row.content[:220], score=round(scores[row.chunk_id], 5), document_id=row.document_id, namespace=row.namespace, source_uri=docs.get(row.document_id).source_uri if row.document_id in docs else row.source_uri) for row in selected if scores[row.chunk_id] > 0]


def _point_id(value: str) -> int:
    return int(_hash(value)[:15], 16)


def _rrf_rank(scores: dict[str, float], chunk_id: str, k: int = 60) -> float:
    ranked = sorted(scores, key=scores.get, reverse=True)
    try:
        return 1 / (k + ranked.index(chunk_id) + 1)
    except ValueError:
        return 0.0


def _chunk_markdown(text: str, child_size: int) -> Iterable[tuple[str, str]]:
    section = '导言'
    buffer: list[str] = []
    for line in text.splitlines():
        if line.startswith('#'):
            if buffer:
                yield from _split_section(section, '\n'.join(buffer), child_size)
                buffer = []
            section = line.lstrip('#').strip()
        elif line.strip():
            buffer.append(line.strip())
    if buffer:
        yield from _split_section(section, '\n'.join(buffer), child_size)


def _split_section(section: str, content: str, child_size: int) -> Iterable[tuple[str, str]]:
    for index in range(0, len(content), child_size):
        yield section, content[index:index + child_size]


def _page_from_section(section: str) -> int:
    """Keep page provenance when a PDF parser has emitted a page heading.

    Markdown/TXT sources intentionally remain page 1.  This is provenance
    display only; it never supplies a citation that retrieval did not return.
    """

    match = re.search(r"(?:PDF\s*第|第)\s*(\d+)\s*页", section)
    return int(match.group(1)) if match else 1


def _strip_frontmatter(text: str) -> str:
    """Remove YAML metadata from retrieval text while retaining it in source files."""

    if not text.startswith('---'):
        return text
    closing = text.find('\n---', 3)
    if closing < 0:
        return text
    return text[closing + len('\n---'):]


rag_service = RagService()
