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
from typing import Any, Iterable, Literal

from qdrant_client import QdrantClient, models
from sqlalchemy import func, or_, select

from app.core.config import DEFAULT_DOMAIN_ID, DEFAULT_KNOWLEDGE_NAMESPACE, QDRANT_URL
from app.db.database import SessionLocal
from app.db.models import (
    DocumentVersionModel,
    KnowledgeChunkModel,
    KnowledgeEntityModel,
    KnowledgeMediaAssetModel,
    KnowledgeRelationModel,
    SourceDocumentModel,
    VectorIndexStateModel,
)
from app.services.embedding_provider import EmbeddingProvider, ImageEmbeddingProvider, RerankerProvider, configured_embedding_provider, configured_image_embedding_provider, configured_reranker_provider


MODEL_NAME = 'BAAI/bge-m3'
RERANK_MODEL = 'BAAI/bge-reranker-v2-m3'
COLLECTION = 'tiban_knowledge_v32'
KNOWLEDGE_INDEX_KEY = 'knowledge'
IMAGE_COLLECTION = 'tiban_knowledge_image_v35'
IMAGE_INDEX_KEY = 'knowledge_images'
MODEL_CACHE = Path(os.getenv('ENDO_EMBEDDING_CACHE', Path(__file__).resolve().parents[2] / 'runtime' / 'fastembed'))
_IMAGE_QUERY_TERMS = (
    "结肠镜", "盲肠", "回盲瓣", "直肠", "上消化道", "胃镜", "食管", "十二指肠",
    "内镜", "息肉", "腺瘤", "图像记录", "图像", "colonoscopy", "cecum", "ileocecal",
    "gastroscopy", "endoscopy", "polyp", "adenoma", "image documentation",
)


def _clip_query_text(query: str) -> str:
    """Keep a learner's image query inside CLIP's short text context.

    The original question is still used by BGE-M3 text retrieval.  CLIP has a
    much smaller token window, especially for CJK text, so image search uses
    only explicit controlled concepts when present; otherwise it keeps a
    bounded prefix rather than failing the whole multimodal evidence path.
    """

    compact = re.sub(r"\s+", " ", query).strip()
    lowered = compact.lower()
    matched = [term for term in _IMAGE_QUERY_TERMS if term.lower() in lowered]
    if matched:
        return " ".join(dict.fromkeys(matched))[:72]
    return compact[:24]


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
    media_asset_ids: tuple[str, ...] = ()
    image_urls: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalProfile:
    """A serialisable, small retrieval contract shared by product and Eval Lab.

    Keeping this data object beside ``RagService`` is deliberate: an evaluation
    profile changes the same code path used by Tutor and Mentor rather than a
    look-alike evaluator retriever.  Values are bounded here so a persisted
    experiment cannot ask a worker to perform an accidental exhaustive search.
    """

    name: str = "TiBan Default"
    mode: Literal['sparse', 'dense', 'hybrid'] = 'hybrid'
    top_k: int = 5
    candidate_pool: int = 20
    rerank_enabled: bool = False
    rrf_k: int = 60
    section_dedupe: bool = True

    @classmethod
    def from_value(cls, value: "RetrievalProfile | dict[str, object] | None", *, fallback_mode: str, fallback_limit: int) -> "RetrievalProfile":
        if isinstance(value, cls):
            return value
        raw = value or {}
        legacy_rerank = fallback_mode == 'hybrid_rerank'
        mode = str(raw.get('mode', 'hybrid' if legacy_rerank else fallback_mode))
        if mode not in {'sparse', 'dense', 'hybrid'}:
            mode = 'hybrid'
        return cls(
            name=str(raw.get('name') or 'TiBan Default')[:80],
            mode=mode,  # type: ignore[arg-type]
            top_k=max(1, min(12, int(raw.get('top_k', fallback_limit)))),
            candidate_pool=max(1, min(80, int(raw.get('candidate_pool', max(fallback_limit * 4, 20))))),
            rerank_enabled=bool(raw.get('rerank_enabled', legacy_rerank)),
            rrf_k=max(1, min(240, int(raw.get('rrf_k', 60)))),
            section_dedupe=bool(raw.get('section_dedupe', True)),
        )

    def public(self) -> dict[str, object]:
        return {
            'name': self.name, 'mode': self.mode, 'top_k': self.top_k,
            'candidate_pool': self.candidate_pool, 'rerank_enabled': self.rerank_enabled,
            'rrf_k': self.rrf_k, 'section_dedupe': self.section_dedupe,
        }


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

    def delete_image_documents(self, document_ids: list[str]) -> None:
        """Remove only the specified knowledge-media points, if indexed."""

        if not document_ids:
            return
        client = self.qdrant
        if not client.collection_exists(IMAGE_COLLECTION):
            return
        client.delete(
            IMAGE_COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchAny(any=document_ids))])
            ),
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

    def image_index_state(self) -> dict[str, object]:
        """Return the truthful state of the optional knowledge-image index."""

        # Do not load CLIP just to render the Knowledge page.  The configured
        # provider/model pair is enough to detect a stale derived index.
        from app.core import config

        expected_provider = config.IMAGE_EMBEDDING_PROVIDER or "clip"
        expected_model = config.IMAGE_EMBEDDING_MODEL
        with SessionLocal() as session:
            state = session.get(VectorIndexStateModel, IMAGE_INDEX_KEY)
            if state is None:
                return {
                    "provider": expected_provider,
                    "model": expected_model,
                    "status": "stale",
                    "vector_dimension": None,
                    "index_version": 0,
                }
            status = state.status
            if status in {"ready", "empty"} and (
                state.provider != expected_provider
                or state.model_id != expected_model
                or (status == "ready" and not state.vector_dimension)
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

    def rebuild_knowledge_image_index(self, *, document_ids: list[str] | None = None) -> list[str]:
        """Build the real image/text vector space for current knowledge media.

        The update is document-scoped when the provider signature and Qdrant
        collection are compatible; a provider/model/dimension change forces a
        coherent full replacement.  A failed image build is surfaced to the
        source while the text collection remains usable.
        """

        requested_ids = {str(value) for value in (document_ids or []) if str(value)}
        provider: ImageEmbeddingProvider | None = None
        try:
            provider = configured_image_embedding_provider()
            with SessionLocal() as session:
                state = session.get(VectorIndexStateModel, IMAGE_INDEX_KEY)
                previous_ready = bool(
                    state is not None
                    and state.status == "ready"
                    and state.provider == provider.provider_id
                    and state.model_id == provider.model_id
                    and state.vector_dimension
                )
                previous_dimension = int(state.vector_dimension or 0) if state else 0
            collection_exists = self.qdrant.collection_exists(IMAGE_COLLECTION)
            incremental = bool(requested_ids and previous_ready and collection_exists)
            with SessionLocal() as session:
                latest_versions = select(
                    DocumentVersionModel.version_id,
                    DocumentVersionModel.document_id,
                    func.row_number().over(
                        partition_by=DocumentVersionModel.document_id,
                        order_by=(DocumentVersionModel.created_at.desc(), DocumentVersionModel.version_id.desc()),
                    ).label("version_rank"),
                ).subquery("latest_knowledge_image_versions")
                statement = (
                    select(KnowledgeMediaAssetModel, SourceDocumentModel)
                    .join(SourceDocumentModel, SourceDocumentModel.document_id == KnowledgeMediaAssetModel.document_id)
                    .join(latest_versions, KnowledgeMediaAssetModel.version_id == latest_versions.c.version_id)
                    .where(
                        latest_versions.c.version_rank == 1,
                        KnowledgeMediaAssetModel.status == "ready",
                        SourceDocumentModel.business_usage == "knowledge_base",
                        SourceDocumentModel.ai_ingestion_allowed.is_(True),
                        SourceDocumentModel.enabled.is_(True),
                        SourceDocumentModel.status.not_in(["queued", "rebuilding", "indexing", "uploaded", "failed", "disabled", "retired"]),
                        SourceDocumentModel.license_gate_status.in_(["allow", "allow_noncommercial"]),
                    )
                    .order_by(KnowledgeMediaAssetModel.document_id, KnowledgeMediaAssetModel.ordinal)
                )
                if requested_ids:
                    statement = statement.where(KnowledgeMediaAssetModel.document_id.in_(requested_ids))
                rows = list(session.execute(statement).all())
                old_asset_ids = set(session.scalars(
                    select(KnowledgeMediaAssetModel.asset_id).where(KnowledgeMediaAssetModel.document_id.in_(requested_ids))
                )) if incremental else set()
            if not rows:
                if incremental:
                    self._delete_image_point_ids(old_asset_ids)
                    self._set_image_index_state(provider, "empty" if not requested_ids else "ready", previous_dimension if requested_ids else 0, None)
                else:
                    if collection_exists:
                        self.qdrant.delete_collection(IMAGE_COLLECTION)
                    self._set_image_index_state(provider, "empty", 0, None)
                self._set_source_image_status(requested_ids, "empty", None)
                return []

            paths = []
            assets = []
            documents = []
            from app.services.knowledge_multimodal_service import KNOWLEDGE_MEDIA_ROOT

            for asset, document in rows:
                path = (KNOWLEDGE_MEDIA_ROOT / asset.storage_path).resolve()
                if KNOWLEDGE_MEDIA_ROOT.resolve() not in path.parents or not path.is_file():
                    raise FileNotFoundError(asset.asset_id)
                paths.append(path)
                assets.append(asset)
                documents.append(document)
            vectors = provider.embed_images(paths)
            if len(vectors) != len(assets) or any(not vector for vector in vectors):
                raise RuntimeError("image_embedding_vectors_invalid")
            dimension = len(vectors[0])
            if any(len(vector) != dimension for vector in vectors):
                raise RuntimeError("image_embedding_vector_dimensions_inconsistent")
            if incremental and previous_dimension and dimension != previous_dimension:
                incremental = False
            evidence_by_asset = self._image_evidence_metadata([asset.asset_id for asset in assets])
            points = [
                models.PointStruct(
                    id=_point_id(f"knowledge-image:{asset.asset_id}"),
                    vector=vector,
                    payload={
                        "asset_id": asset.asset_id,
                        "document_id": asset.document_id,
                        "version_id": asset.version_id,
                        "domain_id": document.domain_id,
                        "namespace": document.namespace,
                        "document_name": document.name,
                        "page": asset.page,
                        "ordinal": asset.ordinal,
                        "mime_type": asset.mime_type,
                        "width": asset.width,
                        "height": asset.height,
                        "caption": evidence_by_asset.get(asset.asset_id, {}).get("caption", asset.alt_text or ""),
                        "section": evidence_by_asset.get(asset.asset_id, {}).get("section", ""),
                        "concepts": evidence_by_asset.get(asset.asset_id, {}).get("concepts", []),
                        "linked_chunk_id": evidence_by_asset.get(asset.asset_id, {}).get("chunk_id", ""),
                    },
                )
                for asset, document, vector in zip(assets, documents, vectors)
            ]
            if incremental:
                # A source can be re-parsed into a different asset set.  The
                # previous asset IDs may already have been removed from the
                # relational database, so deleting only those IDs would leave
                # stale logo/page-furniture vectors behind.  Remove the
                # document slice first, then atomically repopulate it with
                # the caption-qualified assets built above.
                self.delete_image_documents(list(requested_ids))
                self.qdrant.upsert(IMAGE_COLLECTION, points=points, wait=True)
            else:
                if self.qdrant.collection_exists(IMAGE_COLLECTION):
                    self.qdrant.delete_collection(IMAGE_COLLECTION)
                self.qdrant.create_collection(
                    IMAGE_COLLECTION,
                    vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
                )
                self.qdrant.upsert(IMAGE_COLLECTION, points=points, wait=True)
            self._set_image_index_state(provider, "ready", dimension, None)
            self._set_source_image_status({asset.document_id for asset in assets} | requested_ids, "ready", None)
            return [asset.asset_id for asset in assets]
        except Exception as exc:
            if provider is None:
                provider_id, model_id = self._configured_image_identity()
            else:
                provider_id, model_id = provider.provider_id, provider.model_id
            self._set_image_index_state_identity(provider_id, model_id, "failed", None, type(exc).__name__)
            self._set_source_image_status(requested_ids, "failed", type(exc).__name__)
            raise

    @staticmethod
    def _image_evidence_metadata(asset_ids: list[str]) -> dict[str, dict[str, object]]:
        """Build compact, explainable image metadata from relational truth."""

        if not asset_ids:
            return {}
        requested = set(asset_ids)
        metadata: dict[str, dict[str, object]] = {}
        with SessionLocal() as session:
            assets = {
                item.asset_id: item
                for item in session.scalars(select(KnowledgeMediaAssetModel).where(
                    KnowledgeMediaAssetModel.asset_id.in_(requested),
                    KnowledgeMediaAssetModel.status == "ready",
                ))
            }
            document_ids = {item.document_id for item in assets.values()}
            chunks = list(session.scalars(select(KnowledgeChunkModel).where(
                KnowledgeChunkModel.document_id.in_(document_ids),
            ))) if document_ids else []
            for asset_id, asset in assets.items():
                linked = next((chunk for chunk in chunks if asset_id in (chunk.media_asset_ids or [])), None)
                concepts: list[str] = []
                if linked is not None:
                    relations = list(session.scalars(select(KnowledgeRelationModel).where(
                        KnowledgeRelationModel.chunk_id == linked.chunk_id,
                        KnowledgeRelationModel.relation_type == "depicted_in_figure",
                    )))
                    entity_ids = {relation.source_entity_id for relation in relations}
                    if entity_ids:
                        concepts = list(session.scalars(select(KnowledgeEntityModel.canonical_name).where(
                            KnowledgeEntityModel.entity_id.in_(entity_ids),
                            KnowledgeEntityModel.entity_type == "concept",
                        )))
                metadata[asset_id] = {
                    "caption": asset.alt_text or "资料中的教学图片",
                    "section": linked.parent_section if linked is not None else f"第 {asset.page} 页",
                    "chunk_id": linked.chunk_id if linked is not None else "",
                    "concepts": concepts[:6],
                }
        return metadata

    @staticmethod
    def _configured_image_identity() -> tuple[str, str]:
        from app.core import config

        return config.IMAGE_EMBEDDING_PROVIDER or "clip", config.IMAGE_EMBEDDING_MODEL

    @staticmethod
    def _safe_source_uri(value: str | None) -> str | None:
        """Expose only an intentional external reference, never a local path."""

        raw = str(value or "").strip()
        return raw if raw.startswith(("https://", "http://")) else None

    def _set_image_index_state(self, provider: ImageEmbeddingProvider, status: str, dimension: int, error: str | None) -> None:
        self._set_image_index_state_identity(provider.provider_id, provider.model_id, status, dimension, error)

    @staticmethod
    def _set_image_index_state_identity(provider_id: str, model_id: str, status: str, dimension: int | None, error: str | None) -> None:
        with SessionLocal() as session:
            state = session.get(VectorIndexStateModel, IMAGE_INDEX_KEY)
            if state is None:
                state = VectorIndexStateModel(index_key=IMAGE_INDEX_KEY, provider=provider_id, model_id=model_id, status=status)
                session.add(state)
            else:
                state.provider, state.model_id, state.status = provider_id, model_id, status
                state.index_version += 1
            state.vector_dimension, state.error_message = dimension, error
            state.indexed_at = datetime.utcnow() if status in {"ready", "empty"} else None
            session.commit()

    @staticmethod
    def _set_source_image_status(document_ids: set[str], status: str, error: str | None) -> None:
        if not document_ids:
            return
        from app.services.knowledge_multimodal_service import knowledge_multimodal_service

        knowledge_multimodal_service.set_image_index_status(document_ids, status, error)

    def _delete_image_point_ids(self, asset_ids: set[str]) -> None:
        if not asset_ids or not self.qdrant.collection_exists(IMAGE_COLLECTION):
            return
        self.qdrant.delete(
            IMAGE_COLLECTION,
            points_selector=models.PointIdsList(points=[_point_id(f"knowledge-image:{asset_id}") for asset_id in asset_ids]),
            wait=True,
        )

    def retrieve_multimodal(
        self,
        query: str,
        *,
        limit: int = 5,
        domain_id: str | None = None,
        namespaces: list[str] | None = None,
        include_images: bool = True,
        include_graph: bool = True,
    ) -> dict[str, object]:
        """Retrieve text, related images and one-hop evidence graph context."""

        active_namespaces = namespaces if namespaces is not None else ["system", "user", "qbank_explanations"]
        citations = self.retrieve(
            query,
            mode="hybrid",
            limit=limit,
            domain_id=domain_id,
            namespaces=active_namespaces,
        )
        image_results: list[dict[str, object]] = []
        image_state = self.image_index_state()
        if include_images and image_state.get("status") == "ready":
            try:
                image_provider = configured_image_embedding_provider()
                if image_state.get("provider") == image_provider.provider_id and image_state.get("model") == image_provider.model_id:
                    vector = image_provider.embed_text(_clip_query_text(query))
                    with SessionLocal() as session:
                        image_documents_statement = select(SourceDocumentModel).where(
                            SourceDocumentModel.business_usage == "knowledge_base",
                            SourceDocumentModel.ai_ingestion_allowed.is_(True),
                            SourceDocumentModel.enabled.is_(True),
                            SourceDocumentModel.status.not_in(["queued", "rebuilding", "indexing", "uploaded", "failed", "disabled", "retired"]),
                            SourceDocumentModel.license_gate_status.in_(["allow", "allow_noncommercial"]),
                        )
                        if domain_id:
                            image_documents_statement = image_documents_statement.where(SourceDocumentModel.domain_id == domain_id)
                        if active_namespaces:
                            image_documents_statement = image_documents_statement.where(SourceDocumentModel.namespace.in_(active_namespaces))
                        image_documents = {
                            item.document_id: item
                            for item in session.scalars(image_documents_statement)
                        }
                    conditions = [models.FieldCondition(key="document_id", match=models.MatchAny(any=list(image_documents)))] if image_documents else []
                    if domain_id:
                        conditions.append(models.FieldCondition(key="domain_id", match=models.MatchValue(value=domain_id)))
                    image_filter = models.Filter(must=conditions) if conditions else None
                    points = self.qdrant.query_points(IMAGE_COLLECTION, query=vector, limit=max(limit * 4, 20), with_payload=True, query_filter=image_filter).points
                    for point in points:
                        payload = point.payload or {}
                        asset_id = str(payload.get("asset_id") or "")
                        document_id = str(payload.get("document_id") or "")
                        document = image_documents.get(document_id)
                        if not asset_id or document is None:
                            continue
                        image_results.append({
                            "asset_id": asset_id,
                            "url": f"/api/v3/knowledge/media/{asset_id}",
                            "document_id": document_id,
                            "document_name": document.name,
                            "namespace": document.namespace,
                            "page": int(payload.get("page") or 1),
                            "score": round(float(point.score), 5),
                            "width": int(payload.get("width") or 0),
                            "height": int(payload.get("height") or 0),
                            "mime_type": str(payload.get("mime_type") or "image/jpeg"),
                            "caption": str(payload.get("caption") or "资料中的教学图片"),
                            "section": str(payload.get("section") or f"第 {int(payload.get('page') or 1)} 页"),
                            "concepts": list(payload.get("concepts") or []),
                            "linked_chunk_id": str(payload.get("linked_chunk_id") or ""),
                            # This is a retrieval similarity, not a model
                            # confidence.  Evidence-graph bonuses are applied
                            # separately below and remain explainable.
                            "clip_score": round(float(point.score), 5),
                            "retrieval_channels": ["clip"],
                            "evidence_links": ["图文语义匹配"],
                        })
            except Exception:
                # The text citations remain useful.  The source status already
                # tells the operator whether the image index needs rebuilding.
                image_results = []

        graph_paths: list[dict[str, object]] = []
        graph_citations: list[Citation] = []
        if include_graph:
            if citations:
                graph_citations, graph_paths = self._expand_graph(citations, domain_id=domain_id, limit=limit)
            graph_images, image_paths = self._graph_related_images(
                citations, query=query, domain_id=domain_id, namespaces=active_namespaces, limit=limit,
            )
            graph_paths.extend(image_paths)
            image_results = self._merge_image_results(image_results, graph_images)
        image_results = self._fuse_image_results(image_results, citations=citations, limit=limit)
        linked_citations, image_to_text_paths = self._image_linked_citations(
            image_results, domain_id=domain_id, namespaces=active_namespaces, limit=limit,
        )
        graph_paths.extend(image_to_text_paths)
        merged: list[Citation] = list(citations)
        known = {item.chunk_id for item in merged}
        for item in graph_citations:
            if item.chunk_id not in known:
                merged.append(item)
                known.add(item.chunk_id)
        for item in linked_citations:
            if item.chunk_id not in known:
                merged.append(item)
                known.add(item.chunk_id)
        # Graph expansion is additive context: retain the requested lexical
        # results and append only the bounded, evidence-backed neighbours.  A
        # plain ``[:limit]`` here would silently discard every graph result as
        # soon as the base retriever filled the requested top-k.
        return {
            "citations": merged[: limit + len(graph_citations) + len(linked_citations)],
            "image_results": image_results,
            "graph_paths": graph_paths,
            "image_index_status": image_state.get("status", "stale"),
            "graph_status": "ready" if graph_paths else "empty",
        }

    @staticmethod
    def _merge_image_results(primary: list[dict[str, object]], additions: list[dict[str, object]]) -> list[dict[str, object]]:
        merged = {str(item.get("asset_id")): dict(item) for item in primary if item.get("asset_id")}
        for item in additions:
            asset_id = str(item.get("asset_id") or "")
            if not asset_id:
                continue
            if asset_id not in merged:
                merged[asset_id] = dict(item)
                continue
            existing = merged[asset_id]
            existing["retrieval_channels"] = list(dict.fromkeys([
                *list(existing.get("retrieval_channels") or []),
                *list(item.get("retrieval_channels") or []),
            ]))
            existing["evidence_links"] = list(dict.fromkeys([
                *list(existing.get("evidence_links") or []),
                *list(item.get("evidence_links") or []),
            ]))
            existing["graph_match_count"] = int(existing.get("graph_match_count") or 0) + int(item.get("graph_match_count") or 0)
        return list(merged.values())

    @staticmethod
    def _fuse_image_results(
        images: list[dict[str, object]], *, citations: list[Citation], limit: int,
    ) -> list[dict[str, object]]:
        """Rank image evidence using visible, provenance-backed signals only.

        CLIP supplies a cross-modal similarity.  A bounded bonus is added when
        the governed graph matched a caption concept and when a textual hit is
        on the same source page.  The resulting ``evidence_association_bonus``
        is intentionally named as an association signal rather than exposed as
        a fabricated probability or model confidence.
        """

        if limit <= 0:
            return []
        citation_pages = {(item.document_id, item.page) for item in citations}
        fused: list[dict[str, object]] = []
        for image in images:
            item = dict(image)
            graph_matches = min(int(item.get("graph_match_count") or 0), 2)
            # Direct caption/concept matches are stronger evidence than a
            # weak cross-language CLIP similarity.  The cap keeps the boost
            # bounded while allowing a Figure that matches two governed
            # query concepts to outrank an unrelated visual near-neighbour.
            association_bonus = graph_matches * 0.12
            if (str(item.get("document_id") or ""), int(item.get("page") or 0)) in citation_pages:
                association_bonus += 0.03
                links = list(item.get("evidence_links") or [])
                if "与相关文字证据同页" not in links:
                    item["evidence_links"] = [*links, "与相关文字证据同页"]
            item["evidence_association_bonus"] = round(association_bonus, 3)
            item["retrieval_score"] = round(float(item.get("clip_score") or 0.0) + association_bonus, 5)
            fused.append(item)
        return sorted(
            fused,
            key=lambda item: (
                -float(item.get("retrieval_score") or 0.0),
                -int(item.get("graph_match_count") or 0),
                int(item.get("page") or 0),
                str(item.get("asset_id") or ""),
            ),
        )[:limit]

    def _graph_related_images(
        self,
        citations: list[Citation],
        *,
        query: str = "",
        domain_id: str | None,
        namespaces: list[str] | None = None,
        limit: int,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Expand text or governed query concepts to captioned figures.

        The canonical captions in a source may be English while a learner asks
        in Chinese.  Controlled concept aliases (for example ``结肠镜`` ↔
        ``colonoscopy``) provide a transparent bridge only for vocabulary that
        the source graph actually contains; this is evidence expansion, not
        a hidden translation or model-generated claim.
        """

        seed_ids = {item.chunk_id for item in citations if item.chunk_id}
        query_concepts: set[str] = set()
        if query.strip():
            from app.services.knowledge_multimodal_service import knowledge_multimodal_service

            query_concepts = set(knowledge_multimodal_service._entity_names(query))
        if not seed_ids and not query_concepts:
            return [], []
        with SessionLocal() as session:
            seed_chunks = list(session.scalars(select(KnowledgeChunkModel).where(KnowledgeChunkModel.chunk_id.in_(seed_ids))))
            doc_ids = {chunk.document_id for chunk in seed_chunks}
            document_statement = select(SourceDocumentModel).where(
                SourceDocumentModel.business_usage == "knowledge_base",
                SourceDocumentModel.enabled.is_(True),
                SourceDocumentModel.ai_ingestion_allowed.is_(True),
                SourceDocumentModel.status.not_in(["queued", "rebuilding", "indexing", "uploaded", "failed", "disabled", "retired"]),
                SourceDocumentModel.license_gate_status.in_(["allow", "allow_noncommercial"]),
            )
            # A lexical text hit can belong to a different eligible source.
            # When the query itself contains a governed concept, retain the
            # domain-wide candidate set so that concept → Figure expansion can
            # contribute the matching image rather than being shadowed by an
            # unrelated text top-k result.
            if doc_ids and not query_concepts:
                document_statement = document_statement.where(SourceDocumentModel.document_id.in_(doc_ids))
            if domain_id:
                document_statement = document_statement.where(SourceDocumentModel.domain_id == domain_id)
            if namespaces:
                document_statement = document_statement.where(SourceDocumentModel.namespace.in_(namespaces))
            docs = {item.document_id: item for item in session.scalars(document_statement)}
            if domain_id:
                docs = {key: value for key, value in docs.items() if value.domain_id == domain_id}
            if not docs:
                return [], []
            seed_relations = list(session.scalars(select(KnowledgeRelationModel).where(
                KnowledgeRelationModel.chunk_id.in_(seed_ids),
                KnowledgeRelationModel.document_id.in_(docs),
            )))
            concept_ids = {
                value
                for relation in seed_relations
                if relation.relation_type != "depicted_in_figure"
                for value in (relation.source_entity_id, relation.target_entity_id)
            }
            if query_concepts:
                concept_ids.update(session.scalars(select(KnowledgeEntityModel.entity_id).where(
                    KnowledgeEntityModel.document_id.in_(docs),
                    KnowledgeEntityModel.entity_type == "concept",
                    KnowledgeEntityModel.canonical_name.in_(query_concepts),
                )))
            if not concept_ids:
                return [], []
            image_relations = list(session.scalars(select(KnowledgeRelationModel).where(
                KnowledgeRelationModel.document_id.in_(docs),
                KnowledgeRelationModel.relation_type == "depicted_in_figure",
                KnowledgeRelationModel.source_entity_id.in_(concept_ids),
            )))
            figure_ids = {item.target_entity_id for item in image_relations}
            figures = {
                item.entity_id: item
                for item in session.scalars(select(KnowledgeEntityModel).where(
                    KnowledgeEntityModel.entity_id.in_(figure_ids),
                    KnowledgeEntityModel.entity_type == "figure",
                ))
            }
            asset_ids = {
                str(asset_id)
                for figure in figures.values()
                for asset_id in figure.properties.get("media_asset_ids", [])
            }
            assets = {
                item.asset_id: item
                for item in session.scalars(select(KnowledgeMediaAssetModel).where(
                    KnowledgeMediaAssetModel.asset_id.in_(asset_ids),
                    KnowledgeMediaAssetModel.status == "ready",
                ))
            }
            entities = {
                item.entity_id: item
                for item in session.scalars(select(KnowledgeEntityModel).where(
                    KnowledgeEntityModel.entity_id.in_(concept_ids | figure_ids),
                ))
            }
        results: list[dict[str, object]] = []
        paths: list[dict[str, object]] = []
        for relation in image_relations:
            figure = figures.get(relation.target_entity_id)
            concept = entities.get(relation.source_entity_id)
            if figure is None or concept is None:
                continue
            for asset_id in figure.properties.get("media_asset_ids", []):
                asset = assets.get(str(asset_id))
                if asset is None:
                    continue
                results.append({
                    "asset_id": asset.asset_id,
                    "url": f"/api/v3/knowledge/media/{asset.asset_id}",
                    "document_id": asset.document_id,
                    "document_name": docs[asset.document_id].name,
                    "namespace": docs[asset.document_id].namespace,
                    "page": asset.page,
                    "width": asset.width,
                    "height": asset.height,
                    "mime_type": asset.mime_type,
                    "caption": asset.alt_text or "资料中的教学图片",
                    "section": str(figure.properties.get("section") or f"第 {asset.page} 页"),
                    "concepts": list(figure.properties.get("concepts") or [concept.canonical_name]),
                    "linked_chunk_id": relation.chunk_id,
                    "graph_match_count": 1,
                    "retrieval_channels": ["caption_concept_graph"],
                    "evidence_links": [f"资料关联：{concept.canonical_name} → 图示"],
                })
                paths.append({
                    "from": concept.canonical_name,
                    "to": asset.alt_text or "资料图片",
                    "relation": "depicted_in_figure",
                    "chunk_id": relation.chunk_id,
                    "asset_id": asset.asset_id,
                })
        # Keep enough candidates to aggregate multiple concept edges before
        # ``_fuse_image_results`` applies the final user-facing limit.  Cutting
        # here can discard the second figure in a page simply because relation
        # storage order happened to list a generic concept first.
        candidate_limit = max(limit * 4, limit)
        return self._merge_image_results([], results)[:candidate_limit], paths[:candidate_limit]

    def _image_linked_citations(
        self,
        images: list[dict[str, object]],
        *,
        domain_id: str | None,
        namespaces: list[str] | None = None,
        limit: int,
    ) -> tuple[list[Citation], list[dict[str, object]]]:
        """Return the caption's linked text, completing the image-to-text hop."""

        linked_ids = {str(item.get("linked_chunk_id") or "") for item in images} - {""}
        if not linked_ids:
            return [], []
        with SessionLocal() as session:
            chunks = list(session.scalars(select(KnowledgeChunkModel).where(KnowledgeChunkModel.chunk_id.in_(linked_ids))))
            docs = {item.document_id: item for item in session.scalars(select(SourceDocumentModel).where(
                SourceDocumentModel.document_id.in_({chunk.document_id for chunk in chunks}),
            ))}
        citations: list[Citation] = []
        paths: list[dict[str, object]] = []
        for chunk in chunks:
            document = docs.get(chunk.document_id)
            if document is None or (domain_id and document.domain_id != domain_id) or (namespaces and chunk.namespace not in namespaces):
                continue
            assets = tuple(str(value) for value in (chunk.media_asset_ids or []) if str(value).strip())
            citations.append(Citation(
                chunk_id=chunk.chunk_id, document_name=document.name, page=chunk.page,
                section=chunk.parent_section, snippet=chunk.content[:220], score=0.0,
                document_id=chunk.document_id, namespace=chunk.namespace,
                source_uri=self._safe_source_uri(document.source_uri), media_asset_ids=assets,
                image_urls=tuple(f"/api/v3/knowledge/media/{asset_id}" for asset_id in assets),
            ))
            paths.append({"from": "相关资料图片", "to": chunk.parent_section, "relation": "caption_supports_text", "chunk_id": chunk.chunk_id})
        return citations[:limit], paths[:limit]

    def _expand_graph(self, citations: list[Citation], *, domain_id: str | None, limit: int) -> tuple[list[Citation], list[dict[str, object]]]:
        seed_chunk_ids = {item.chunk_id for item in citations if item.chunk_id}
        if not seed_chunk_ids or limit <= 0:
            return [], []

        with SessionLocal() as session:
            seed_chunks = list(session.scalars(select(KnowledgeChunkModel).where(KnowledgeChunkModel.chunk_id.in_(seed_chunk_ids))))
            if not seed_chunks:
                return [], []
            seed_document_ids = {chunk.document_id for chunk in seed_chunks}
            seed_version_ids = {chunk.version_id for chunk in seed_chunks}
            eligible_docs = list(session.scalars(
                select(SourceDocumentModel).where(
                    SourceDocumentModel.document_id.in_(seed_document_ids),
                    SourceDocumentModel.business_usage == "knowledge_base",
                    SourceDocumentModel.business_usage != "benchmark_only",
                    SourceDocumentModel.business_usage != "excluded",
                    SourceDocumentModel.ai_ingestion_allowed.is_(True),
                    SourceDocumentModel.enabled.is_(True),
                    SourceDocumentModel.status.not_in(["queued", "rebuilding", "indexing", "uploaded", "failed", "disabled", "retired"]),
                    SourceDocumentModel.license_gate_status.in_(["allow", "allow_noncommercial"]),
                )
            ))
            docs = {document.document_id: document for document in eligible_docs}
            if not docs:
                return [], []

            seed_relations = list(session.scalars(
                select(KnowledgeRelationModel).where(
                    KnowledgeRelationModel.document_id.in_(docs.keys()),
                    KnowledgeRelationModel.chunk_id.in_(seed_chunk_ids),
                ).order_by(
                    KnowledgeRelationModel.confidence.desc(),
                    KnowledgeRelationModel.relation_id,
                ).limit(max(limit * 4, 8))
            ))
            if not seed_relations:
                return [], []

            seed_entity_ids = {
                entity_id
                for relation in seed_relations
                for entity_id in (relation.source_entity_id, relation.target_entity_id)
            }
            if not seed_entity_ids:
                return [], []

            # The graph is deliberately one hop: a neighbour relation must
            # share an entity with a seed relation, belong to the same source
            # document, and point at a chunk from the same frozen version.
            # This prevents a stale version, disabled source, or unrelated
            # domain from becoming learner-facing evidence.
            neighbour_relations = list(session.scalars(
                select(KnowledgeRelationModel).where(
                    KnowledgeRelationModel.document_id.in_(docs.keys()),
                    or_(
                        KnowledgeRelationModel.source_entity_id.in_(seed_entity_ids),
                        KnowledgeRelationModel.target_entity_id.in_(seed_entity_ids),
                    ),
                ).order_by(
                    KnowledgeRelationModel.confidence.desc(),
                    KnowledgeRelationModel.relation_id,
                ).limit(max(limit * 16, 32))
            ))
            neighbour_relations = [
                relation for relation in neighbour_relations
                if relation.chunk_id not in seed_chunk_ids
            ]
            if not neighbour_relations:
                return [], []

            neighbour_chunk_ids = {relation.chunk_id for relation in neighbour_relations}
            chunks = {
                chunk.chunk_id: chunk
                for chunk in session.scalars(select(KnowledgeChunkModel).where(
                    KnowledgeChunkModel.chunk_id.in_(neighbour_chunk_ids),
                    KnowledgeChunkModel.document_id.in_(docs),
                    KnowledgeChunkModel.version_id.in_(seed_version_ids),
                ))
            }
            if not chunks:
                return [], []

            entity_ids = seed_entity_ids | {
                entity_id
                for relation in neighbour_relations
                for entity_id in (relation.source_entity_id, relation.target_entity_id)
            }
            entities = {
                entity.entity_id: entity
                for entity in session.scalars(select(KnowledgeEntityModel).where(
                    KnowledgeEntityModel.entity_id.in_(entity_ids),
                    KnowledgeEntityModel.document_id.in_(docs.keys()),
                ))
            }

        # Keep the strongest relation for each neighbouring chunk.  Stable
        # sorting makes Tutor/Mentor citations deterministic across databases.
        best_relation_by_chunk: dict[str, KnowledgeRelationModel] = {}
        for relation in neighbour_relations:
            if relation.chunk_id not in chunks:
                continue
            previous = best_relation_by_chunk.get(relation.chunk_id)
            if previous is None or float(relation.confidence) > float(previous.confidence):
                best_relation_by_chunk[relation.chunk_id] = relation

        ordered_relations = sorted(
            best_relation_by_chunk.values(),
            key=lambda relation: (-float(relation.confidence), relation.chunk_id),
        )[:limit]
        paths: list[dict[str, object]] = []
        extra: list[Citation] = []
        for relation in ordered_relations:
            chunk = chunks[relation.chunk_id]
            document = docs.get(chunk.document_id)
            if document is None or (domain_id and document.domain_id != domain_id):
                continue
            shared_entities = seed_entity_ids.intersection({relation.source_entity_id, relation.target_entity_id})
            seed_chunk_id = next(
                (
                    seed_relation.chunk_id
                    for seed_relation in seed_relations
                    if shared_entities.intersection({seed_relation.source_entity_id, seed_relation.target_entity_id})
                ),
                "",
            )
            source_entity = entities.get(relation.source_entity_id)
            target_entity = entities.get(relation.target_entity_id)
            if source_entity is None or target_entity is None:
                continue
            paths.append({
                "from": source_entity.canonical_name,
                "to": target_entity.canonical_name,
                "relation": relation.relation_type,
                "chunk_id": relation.chunk_id,
                "seed_chunk_id": seed_chunk_id,
                "confidence": round(float(relation.confidence), 3),
            })
            asset_ids = tuple(str(value) for value in (chunk.media_asset_ids or []) if str(value).strip())
            extra.append(Citation(
                chunk_id=chunk.chunk_id,
                document_name=document.name,
                page=chunk.page,
                section=chunk.parent_section,
                snippet=chunk.content[:220],
                score=round(float(relation.confidence) * 0.01, 5),
                document_id=chunk.document_id,
                namespace=chunk.namespace,
                source_uri=self._safe_source_uri(document.source_uri),
                media_asset_ids=asset_ids,
                image_urls=tuple(f"/api/v3/knowledge/media/{asset_id}" for asset_id in asset_ids),
            ))
        return extra[:limit], paths[:limit * 2]

    def retrieve(
        self,
        query: str,
        mode: Literal['sparse', 'dense', 'hybrid', 'hybrid_rerank'] = 'hybrid',
        limit: int = 5,
        *,
        profile: RetrievalProfile | dict[str, object] | None = None,
        version_id: str | None = None,
        version_ids: list[str] | None = None,
        document_ids: list[str] | None = None,
        domain_id: str | None = None,
        namespace: str | None = None,
        namespaces: list[str] | None = None,
    ) -> list[Citation]:
        active_profile = RetrievalProfile.from_value(profile, fallback_mode=mode, fallback_limit=limit)
        mode = active_profile.mode
        limit = active_profile.top_k
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
                result = self.qdrant.query_points(COLLECTION, query=vector, limit=active_profile.candidate_pool, with_payload=True, query_filter=query_filter).points
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
                scores[row.chunk_id] = _rrf_rank(sparse, row.chunk_id, active_profile.rrf_k) + _rrf_rank(dense, row.chunk_id, active_profile.rrf_k)
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
        ][:active_profile.candidate_pool]
        if active_profile.rerank_enabled and candidates:
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
        if active_profile.section_dedupe:
            deduped: list[KnowledgeChunkModel] = []
            seen_sections: set[tuple[str, str]] = set()
            for row in selected:
                key = (row.document_id, row.parent_section)
                if key not in seen_sections:
                    seen_sections.add(key)
                    deduped.append(row)
            selected = deduped[:limit]
        _ = perf_counter() - started
        citations: list[Citation] = []
        for row in selected:
            if scores[row.chunk_id] <= 0:
                continue
            asset_ids = tuple(str(value) for value in (row.media_asset_ids or []) if str(value).strip())
            citations.append(Citation(
                chunk_id=row.chunk_id,
                document_name=docs.get(row.document_id).name if row.document_id in docs else '教学资料',
                page=row.page,
                section=row.parent_section,
                snippet=row.content[:220],
                score=round(scores[row.chunk_id], 5),
                document_id=row.document_id,
                namespace=row.namespace,
                source_uri=self._safe_source_uri(docs.get(row.document_id).source_uri if row.document_id in docs else row.source_uri),
                media_asset_ids=asset_ids,
                image_urls=tuple(f"/api/v3/knowledge/media/{asset_id}" for asset_id in asset_ids),
            ))
        return citations


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
