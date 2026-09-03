"""Instance-scoped embedding and reranking providers for derived indexes.

PostgreSQL/source files remain canonical.  This module deliberately exposes a
small synchronous interface because the current FastAPI/RAG path is
synchronous; background workers call the same provider without a second
embedding architecture.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastembed import TextEmbedding

from app.core import config


class EmbeddingProvider(Protocol):
    provider_id: str
    model_id: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    def dimension(self) -> int: ...


class RerankerProvider(Protocol):
    provider_id: str
    model_id: str

    def score(self, query: str, documents: list[str]) -> list[float]: ...


@dataclass
class OpenAICompatibleEmbeddingProvider:
    provider_id: str
    model_id: str
    base_url: str
    api_key: str
    timeout_seconds: float
    _dimension: int | None = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = self._request({"model": self.model_id, "input": texts, "encoding_format": "float"})
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise RuntimeError("embedding_response_invalid")
        vectors = [list(map(float, item.get("embedding", []))) for item in data if isinstance(item, dict)]
        if len(vectors) != len(texts) or not vectors or not vectors[0]:
            raise RuntimeError("embedding_vectors_invalid")
        if any(len(vector) != len(vectors[0]) for vector in vectors):
            raise RuntimeError("embedding_vector_dimensions_inconsistent")
        self._dimension = len(vectors[0])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def dimension(self) -> int:
        if self._dimension is None:
            self.embed_query("TiBan embedding readiness probe")
        assert self._dimension is not None
        return self._dimension

    def _request(self, body: dict[str, object]) -> dict[str, object]:
        endpoint = self.base_url.rstrip("/")
        endpoint = endpoint if endpoint.endswith("/embeddings") else f"{endpoint}/embeddings"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:200]
            raise RuntimeError(f"embedding_http_{exc.code}:{detail}") from exc
        except Exception as exc:
            raise RuntimeError(f"embedding_unavailable:{type(exc).__name__}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("embedding_response_invalid")
        return payload


@dataclass
class LocalFastEmbedProvider:
    provider_id: str
    model_id: str
    cache_dir: Path
    _embedder: TextEmbedding | None = None
    _dimension: int | None = None

    @property
    def embedder(self) -> TextEmbedding:
        if self._embedder is None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._embedder = TextEmbedding(model_name=self.model_id, cache_dir=str(self.cache_dir))
        return self._embedder

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = [vector.tolist() for vector in self.embedder.embed(texts, batch_size=embedding_batch_size())]
        if vectors:
            self._dimension = len(vectors[0])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vector = next(self.embedder.query_embed(text)).tolist()
        self._dimension = len(vector)
        return vector

    def dimension(self) -> int:
        if self._dimension is None:
            self.embed_query("TiBan embedding readiness probe")
        assert self._dimension is not None
        return self._dimension


@dataclass
class OpenAICompatibleRerankerProvider:
    provider_id: str
    model_id: str
    base_url: str
    api_key: str
    timeout_seconds: float

    def score(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        endpoint = self.base_url.rstrip("/")
        endpoint = endpoint if endpoint.endswith("/rerank") else f"{endpoint}/rerank"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps({"model": self.model_id, "query": query, "documents": documents}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"reranker_unavailable:{type(exc).__name__}") from exc
        values = payload.get("results", payload.get("data", [])) if isinstance(payload, dict) else []
        scores = [0.0] * len(documents)
        for index, item in enumerate(values if isinstance(values, list) else []):
            if not isinstance(item, dict):
                continue
            position = int(item.get("index", index))
            if 0 <= position < len(scores):
                scores[position] = float(item.get("relevance_score", item.get("score", 0.0)))
        return scores


@dataclass
class LocalCrossEncoderProvider:
    provider_id: str
    model_id: str
    cache_dir: Path
    _model: object | None = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_id, cache_dir=str(self.cache_dir / "cross-encoder"))
        return self._model

    def score(self, query: str, documents: list[str]) -> list[float]:
        return [float(value) for value in self.model.predict([(query, item) for item in documents], show_progress_bar=False)]


def embedding_batch_size() -> int:
    from app.services.runtime_settings_service import runtime_settings_service

    return runtime_settings_service.embedding_batch_size()


def configured_embedding_provider(cache_dir: Path) -> EmbeddingProvider:
    """Resolve exactly one active provider; missing API credentials use Local.

    The selected provider/model is recorded in index metadata, so this fallback
    cannot accidentally query vectors produced by a different vector space.
    """

    from app.services.runtime_settings_service import runtime_settings_service

    runtime_settings_service.sync()
    if config.EMBEDDING_MODE == "api" and config.EMBEDDING_API_KEY.strip():
        return OpenAICompatibleEmbeddingProvider(
            provider_id=config.EMBEDDING_PROVIDER or "openai_compatible",
            model_id=config.EMBEDDING_MODEL,
            base_url=config.EMBEDDING_BASE_URL,
            api_key=config.EMBEDDING_API_KEY,
            timeout_seconds=config.EMBEDDING_TIMEOUT_SECONDS,
        )
    return LocalFastEmbedProvider("local_fastembed", config.EMBEDDING_LOCAL_MODEL, cache_dir)


def configured_reranker_provider(cache_dir: Path) -> RerankerProvider:
    from app.services.runtime_settings_service import runtime_settings_service

    runtime_settings_service.sync()
    if config.RERANKER_MODE == "api" and config.RERANKER_API_KEY.strip():
        return OpenAICompatibleRerankerProvider(
            provider_id=config.RERANKER_PROVIDER or "openai_compatible",
            model_id=config.RERANKER_MODEL,
            base_url=config.RERANKER_BASE_URL,
            api_key=config.RERANKER_API_KEY,
            timeout_seconds=config.EMBEDDING_TIMEOUT_SECONDS,
        )
    return LocalCrossEncoderProvider("local_cross_encoder", "cross-encoder/ms-marco-MiniLM-L6-v2", cache_dir)
