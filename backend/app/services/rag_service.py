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

    def index_markdown(self, path: Path, *, document_id: str = 'source-stage2-endoscopy-v1', child_size: int = 180) -> list[str]:
        text = path.read_text(encoding='utf-8')
        document_name = path.name
        source_hash = _hash(text)
        chunks = list(_chunk_markdown(text, child_size))
        # Chunk identity changed in Stage 2 so identical uploads can coexist
        # without primary-key collisions.  Keep the previous runtime index
        # untouched for auditability; v2 is the only version eligible for new
        # benchmark/product retrieval and therefore can never mix both IDs.
        version_id = f'{document_id}-{source_hash[:12]}-{child_size}-v2'
        version_label = (
            f'retrieval-eval-v1-child-{child_size}-identity-v2'
            if document_id == 'source-stage2-endoscopy-v1'
            else f'factory-index-v1-child-{child_size}-identity-v2'
        )
        with SessionLocal() as session:
            document = session.get(SourceDocumentModel, document_id)
            if not document:
                session.add(SourceDocumentModel(document_id=document_id, domain_id='endoscopy', bank_id=None, name=document_name, media_type='text/markdown', content_hash=source_hash, status='indexed'))
                session.flush()
            if not session.get(DocumentVersionModel, version_id):
                session.add(DocumentVersionModel(version_id=version_id, document_id=document_id, version_label=version_label, source_path=str(path.resolve()), content_hash=source_hash, parser='heading-aware-markdown', status='indexed'))
            for ordinal, (section, content) in enumerate(chunks):
                # The same allowed content may be uploaded more than once;
                # include document identity so globally keyed chunks retain
                # both provenance paths without a collision.
                chunk_id = f'chunk-{document_id[-12:]}-{source_hash[:8]}-{child_size}-{ordinal:02d}-v2'
                # Dramatiq may retry after a transient Qdrant failure.  The
                # relational chunk insert is idempotent across such retries.
                if session.get(KnowledgeChunkModel, chunk_id) is None:
                    session.add(KnowledgeChunkModel(chunk_id=chunk_id, document_id=document_id, version_id=version_id, parent_section=section, page=1, ordinal=ordinal, content=content, content_hash=_hash(content), token_count=len(content)))
            session.commit()
            rows = list(session.scalars(select(KnowledgeChunkModel).where(KnowledgeChunkModel.version_id == version_id).order_by(KnowledgeChunkModel.ordinal)))
            document = session.get(SourceDocumentModel, document_id)
            assert document is not None
            vectors = list(self.embedder.embed([row.content for row in rows]))
            client = self.qdrant
            if not client.collection_exists(COLLECTION):
                client.create_collection(COLLECTION, vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE))
            client.upsert(COLLECTION, points=[models.PointStruct(id=_point_id(row.chunk_id), vector=vector.tolist(), payload={'chunk_id': row.chunk_id, 'version_id': row.version_id, 'document_name': document.name, 'page': row.page, 'section': row.parent_section, 'content': row.content}) for row, vector in zip(rows, vectors)])
            return [row.chunk_id for row in rows]

    def retrieve(self, query: str, mode: Literal['sparse', 'dense', 'hybrid', 'hybrid_rerank'] = 'hybrid', limit: int = 5, *, version_id: str | None = None) -> list[Citation]:
        started = perf_counter()
        with SessionLocal() as session:
            # Product retrieval intentionally uses one frozen, benchmarked
            # version. Historical chunks remain for artifact reproducibility but
            # must never leak into Tutor citations.
            if version_id is None:
                active = session.scalar(
                    select(DocumentVersionModel.version_id)
                    .where(DocumentVersionModel.document_id == 'source-stage2-endoscopy-v1', DocumentVersionModel.version_label == 'retrieval-eval-v1-child-180-identity-v2')
                    .order_by(DocumentVersionModel.created_at.desc())
                )
                version_id = active
            statement = select(KnowledgeChunkModel).order_by(KnowledgeChunkModel.ordinal)
            if version_id:
                statement = statement.where(KnowledgeChunkModel.version_id == version_id)
            rows = list(session.scalars(statement))
            names = {row.document_id: session.get(SourceDocumentModel, row.document_id).name for row in rows if session.get(SourceDocumentModel, row.document_id)}
        if not rows:
            return []
        sparse = {row.chunk_id: _sparse_score(query, row.content) for row in rows}
        dense: dict[str, float] = {}
        if mode != 'sparse':
            vector = next(self.embedder.query_embed(query)).tolist()
            query_filter = models.Filter(must=[models.FieldCondition(key='version_id', match=models.MatchValue(value=version_id))]) if version_id else None
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
        return [Citation(chunk_id=row.chunk_id, document_name=names.get(row.document_id, '教学资料'), page=row.page, section=row.parent_section, snippet=row.content[:220], score=round(scores[row.chunk_id], 5)) for row in selected if scores[row.chunk_id] > 0]


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


rag_service = RagService()
