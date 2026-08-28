"""Qdrant-backed dense retrieval plus transparent sparse/hybrid baselines."""

from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, Literal

from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models
from sentence_transformers import CrossEncoder
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import DocumentVersionModel, KnowledgeChunkModel, SourceDocumentModel


MODEL_NAME = 'BAAI/bge-small-zh-v1.5'
RERANK_MODEL = 'cross-encoder/ms-marco-MiniLM-L6-v2'
COLLECTION = 'endotutor_chunks_v1'
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
    namespace: str = 'medical_general'
    source_uri: str | None = None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _terms(value: str) -> Counter[str]:
    cleaned = re.sub(r'\s+', '', value.lower())
    return Counter(cleaned[index:index + 2] for index in range(max(len(cleaned) - 1, 0)))


def _sparse_score(query: str, content: str) -> float:
    left, right = _terms(query), _terms(content)
    if not left or not right:
        return 0.0
    return sum(min(left[key], right[key]) for key in left) / max(sum(left.values()), 1)


class RagService:
    def __init__(self) -> None:
        self._embedder: TextEmbedding | None = None
        self._reranker: CrossEncoder | None = None

    @property
    def embedder(self) -> TextEmbedding:
        if self._embedder is None:
            MODEL_CACHE.mkdir(parents=True, exist_ok=True)
            self._embedder = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(MODEL_CACHE))
        return self._embedder

    @property
    def qdrant(self) -> QdrantClient:
        return QdrantClient(url=os.getenv('QDRANT_URL', 'http://127.0.0.1:6333'))

    @property
    def reranker(self) -> CrossEncoder:
        if self._reranker is None:
            # Apache-2.0 cross encoder; cached inside the repository runtime so
            # Windows' default temporary cache never requires symlink privilege.
            self._reranker = CrossEncoder(RERANK_MODEL, cache_dir=str(MODEL_CACHE / 'cross-encoder'))
        return self._reranker

    def index_markdown(
        self,
        path: Path,
        *,
        document_id: str = 'source-stage2-endoscopy-v1',
        child_size: int = 180,
        namespace: str = 'medical_general',
        source_id: str | None = None,
        source_uri: str | None = None,
        business_usage: str = 'knowledge_base',
        license_gate_status: str = 'allow_noncommercial',
        ai_ingestion_allowed: bool = True,
        version_label: str | None = None,
    ) -> list[str]:
        text = path.read_text(encoding='utf-8')
        document_name = path.name
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
                session.add(SourceDocumentModel(document_id=document_id, domain_id='endoscopy', bank_id=None, name=document_name, media_type='text/markdown', content_hash=source_hash, status='indexed', source_id=source_id, business_usage=business_usage, license_gate_status=license_gate_status, ai_ingestion_allowed=ai_ingestion_allowed, source_uri=source_uri or str(path.resolve()), namespace=namespace))
                session.flush()
            else:
                document.namespace = namespace
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
                    session.add(KnowledgeChunkModel(chunk_id=chunk_id, document_id=document_id, version_id=version_id, parent_section=section, page=1, ordinal=ordinal, content=content, content_hash=_hash(content), token_count=len(content), namespace=namespace, source_uri=source_uri or str(path.resolve())))
                else:
                    # Re-indexing is idempotent but also refreshes parser
                    # output when a curated note's frontmatter or section
                    # handling changes.
                    chunk.parent_section = section
                    chunk.ordinal = ordinal
                    chunk.content = content
                    chunk.content_hash = _hash(content)
                    chunk.token_count = len(content)
                    chunk.namespace = namespace
                    chunk.source_uri = source_uri or str(path.resolve())
            session.commit()
            rows = list(session.scalars(select(KnowledgeChunkModel).where(KnowledgeChunkModel.version_id == version_id).order_by(KnowledgeChunkModel.ordinal)))
            document = session.get(SourceDocumentModel, document_id)
            assert document is not None
            vectors = list(self.embedder.embed([row.content for row in rows]))
            client = self.qdrant
            if not client.collection_exists(COLLECTION):
                client.create_collection(COLLECTION, vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE))
            client.upsert(COLLECTION, points=[models.PointStruct(id=_point_id(row.chunk_id), vector=vector.tolist(), payload={'chunk_id': row.chunk_id, 'document_id': row.document_id, 'version_id': row.version_id, 'namespace': row.namespace, 'document_name': document.name, 'page': row.page, 'section': row.parent_section, 'source_uri': row.source_uri, 'content': row.content}) for row, vector in zip(rows, vectors)])
            return [row.chunk_id for row in rows]

    def retrieve(
        self,
        query: str,
        mode: Literal['sparse', 'dense', 'hybrid', 'hybrid_rerank'] = 'hybrid',
        limit: int = 5,
        *,
        version_id: str | None = None,
        version_ids: list[str] | None = None,
        document_ids: list[str] | None = None,
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
                SourceDocumentModel.business_usage != 'benchmark_only',
                SourceDocumentModel.business_usage != 'excluded',
                SourceDocumentModel.ai_ingestion_allowed.is_(True),
                SourceDocumentModel.license_gate_status.in_(['allow', 'allow_noncommercial']),
            )
            rows = list(session.scalars(statement))
            docs = {doc.document_id: doc for doc in session.scalars(select(SourceDocumentModel).where(SourceDocumentModel.document_id.in_({row.document_id for row in rows})))}
        if not rows:
            return []
        sparse = {row.chunk_id: _sparse_score(query, row.content) for row in rows}
        dense: dict[str, float] = {}
        if mode != 'sparse':
            vector = next(self.embedder.query_embed(query)).tolist()
            conditions = []
            if version_id:
                conditions.append(models.FieldCondition(key='version_id', match=models.MatchValue(value=version_id)))
            elif version_ids:
                conditions.append(models.FieldCondition(key='version_id', match=models.MatchAny(any=version_ids)))
            if document_ids:
                conditions.append(models.FieldCondition(key='document_id', match=models.MatchAny(any=document_ids)))
            if namespace:
                conditions.append(models.FieldCondition(key='namespace', match=models.MatchValue(value=namespace)))
            elif namespaces:
                conditions.append(models.FieldCondition(key='namespace', match=models.MatchAny(any=namespaces)))
            query_filter = models.Filter(must=conditions) if conditions else None
            result = self.qdrant.query_points(COLLECTION, query=vector, limit=max(limit * 3, 10), with_payload=True, query_filter=query_filter).points
            dense = {str(point.payload['chunk_id']): float(point.score) for point in result}
        scores: dict[str, float] = {}
        for row in rows:
            if mode == 'sparse':
                scores[row.chunk_id] = sparse[row.chunk_id]
            elif mode == 'dense':
                scores[row.chunk_id] = dense.get(row.chunk_id, 0.0)
            else:
                scores[row.chunk_id] = _rrf_rank(sparse, row.chunk_id) + _rrf_rank(dense, row.chunk_id)
        candidates = sorted(rows, key=lambda row: scores[row.chunk_id], reverse=True)[:max(limit * 4, 20)]
        if mode == 'hybrid_rerank' and candidates:
            # This is a learned cross-encoder inference, not a lexical score
            # boost.  Its score only orders candidate passages after hybrid RRF.
            rerank_scores = self.reranker.predict([(query, row.content) for row in candidates], show_progress_bar=False)
            selected = [row for _, row in sorted(zip(rerank_scores, candidates), key=lambda item: float(item[0]), reverse=True)[:limit]]
            scores = {**scores, **{row.chunk_id: float(score) for score, row in zip(rerank_scores, candidates)}}
        else:
            selected = candidates[:limit]
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


def _strip_frontmatter(text: str) -> str:
    """Remove YAML metadata from retrieval text while retaining it in source files."""

    if not text.startswith('---'):
        return text
    closing = text.find('\n---', 3)
    if closing < 0:
        return text
    return text[closing + len('\n---'):]


rag_service = RagService()
