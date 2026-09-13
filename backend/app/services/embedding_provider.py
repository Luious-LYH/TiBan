"""Instance-scoped embedding and reranking providers for derived indexes.

PostgreSQL/source files remain canonical.  This module deliberately exposes a
small synchronous interface because the current FastAPI/RAG path is
synchronous; background workers call the same provider without a second
embedding architecture.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from app.core import config

if TYPE_CHECKING:
    from fastembed import TextEmbedding


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


class ImageEmbeddingProvider(Protocol):
    """A real shared image/text embedding space for knowledge media."""

    provider_id: str
    model_id: str

    def embed_images(self, image_paths: list[Path]) -> list[list[float]]: ...
    def embed_text(self, text: str) -> list[float]: ...
    def dimension(self) -> int: ...


@dataclass
class OpenAICompatibleEmbeddingProvider:
    provider_id: str
    model_id: str
    base_url: str
    api_key: str
    timeout_seconds: float
    _dimension: int | None = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a document sequence without letting one flaky remote batch restart it.

        Remote OpenAI-compatible endpoints do not share one reliable request
        ceiling.  A batch that is safe for a short chat prompt can be rejected
        or have its connection reset when it contains many 450-token document
        chunks.  Keep successfully completed batches in memory, retry only the
        failed request, and reduce *subsequent* batches when the transport
        proves that the current size is too large.  The caller still receives
        an all-or-nothing vector list, so a failed rebuild never creates a
        mixed vector space.
        """

        if not texts:
            return []
        batch_size = max(1, embedding_batch_size())
        vectors: list[list[float]] = []
        expected_dimension: int | None = None
        cursor = 0
        # Start with the owner-configured value.  If a provider resets a large
        # request, lower only this invocation's working size; a later run can
        # use the configured maximum again after the provider recovers.
        working_batch_size = batch_size
        while cursor < len(texts):
            batch = texts[cursor:cursor + min(working_batch_size, len(texts) - cursor)]
            try:
                batch_vectors = self._embed_batch_with_retry(batch)
            except RuntimeError as exc:
                if not self._is_retryable_transport_error(exc) or len(batch) <= 1:
                    raise
                # Retry the same uncompleted slice at a safer size.  Vectors
                # for all preceding slices remain intact and are not requested
                # again, which substantially reduces recovery time for long
                # teaching documents.
                working_batch_size = max(1, len(batch) // 2)
                continue
            if expected_dimension is None:
                expected_dimension = len(batch_vectors[0])
            if any(len(vector) != expected_dimension for vector in batch_vectors):
                raise RuntimeError("embedding_vector_dimensions_inconsistent")
            vectors.extend(batch_vectors)
            cursor += len(batch)
        if len(vectors) != len(texts) or expected_dimension is None:
            raise RuntimeError("embedding_vectors_invalid")
        self._dimension = expected_dimension
        return vectors

    def _embed_batch_with_retry(self, batch: list[str]) -> list[list[float]]:
        """Request and validate one batch, retrying only transient failures."""

        last_error: RuntimeError | None = None
        for attempt in range(3):
            try:
                payload = self._request({"model": self.model_id, "input": batch, "encoding_format": "float"})
                return self._decode_batch(payload, expected_count=len(batch))
            except RuntimeError as exc:
                if not self._is_retryable_transport_error(exc):
                    raise
                last_error = exc
                if attempt < 2:
                    # Bounded backoff gives a shared endpoint time to recover
                    # without turning one source import into an unbounded job.
                    time.sleep(0.2 * (2 ** attempt))
        assert last_error is not None
        raise last_error

    @staticmethod
    def _decode_batch(payload: dict[str, object], *, expected_count: int) -> list[list[float]]:
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != expected_count:
            raise RuntimeError("embedding_response_invalid")
        items = [item for item in data if isinstance(item, dict)]
        if len(items) != expected_count:
            raise RuntimeError("embedding_vectors_invalid")
        # OpenAI-compatible servers may return an explicit per-batch index;
        # preserve input order even if the response is not ordered.
        if all("index" in item for item in items):
            ordered: list[dict[str, object] | None] = [None] * expected_count
            for item in items:
                try:
                    index = int(item["index"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError("embedding_response_invalid") from exc
                if index < 0 or index >= expected_count or ordered[index] is not None:
                    raise RuntimeError("embedding_response_invalid")
                ordered[index] = item
            if any(item is None for item in ordered):
                raise RuntimeError("embedding_response_invalid")
            items = [item for item in ordered if item is not None]
        vectors: list[list[float]] = []
        for item in items:
            try:
                vector = list(map(float, item.get("embedding", [])))
            except (TypeError, ValueError) as exc:
                raise RuntimeError("embedding_vectors_invalid") from exc
            if not vector:
                raise RuntimeError("embedding_vectors_invalid")
            vectors.append(vector)
        if len(vectors) != expected_count:
            raise RuntimeError("embedding_vectors_invalid")
        return vectors

    @staticmethod
    def _is_retryable_transport_error(exc: RuntimeError) -> bool:
        """Classify retryable service/network failures without leaking URLs."""

        message = str(exc).lower()
        if message.startswith("embedding_unavailable:"):
            return True
        if not message.startswith("embedding_http_"):
            return False
        # 408/425/429 and 5xx responses are service availability signals. A
        # malformed success response remains a hard contract error instead.
        try:
            status = int(message.split(":", 1)[0].rsplit("_", 1)[1])
        except (IndexError, ValueError):
            return False
        return status in {408, 409, 425, 429} or status >= 500

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
            # FastEmbed remains available to source/developer installs, while
            # the desktop bundle uses the configured remote Embedding API and
            # should not carry the optional torch stack.
            from importlib import import_module

            TextEmbedding = import_module("fastembed").TextEmbedding
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


@dataclass
class ClipImageEmbeddingProvider:
    """Local CLIP encoder: image and text vectors share one semantic space.

    The model is lazy-loaded.  A missing model/dependency is allowed to fail at
    the knowledge indexing boundary where the source can show a truthful
    ``image_index_status=failed`` while its text index remains usable.
    """

    provider_id: str
    model_id: str
    cache_dir: Path
    _model: object | None = None
    _dimension: int | None = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # The demo ships or prewarms this cache separately from source
            # files.  Do not block a learner query on Hugging Face metadata
            # checks after a restart: if the local model is absent, retrieval
            # reports its unavailable state truthfully instead of hanging.
            self._model = SentenceTransformer(
                self.model_id,
                cache_folder=str(self.cache_dir),
                local_files_only=True,
            )
        return self._model

    def embed_images(self, image_paths: list[Path]) -> list[list[float]]:
        if not image_paths:
            return []
        from PIL import Image

        images = []
        try:
            for path in image_paths:
                with Image.open(path) as image:
                    images.append(image.convert("RGB"))
            values = self.model.encode(images, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
            vectors = [[float(value) for value in row] for row in values]
        finally:
            for image in images:
                image.close()
        self._dimension = len(vectors[0]) if vectors else self._dimension
        return vectors

    def embed_text(self, text: str) -> list[float]:
        values = self.model.encode([text], convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
        vector = [float(value) for value in values[0]]
        self._dimension = len(vector)
        return vector

    def dimension(self) -> int:
        if self._dimension is None:
            self.embed_text("TiBan knowledge image readiness probe")
        assert self._dimension is not None
        return self._dimension


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


@lru_cache(maxsize=1)
def configured_image_embedding_provider() -> ImageEmbeddingProvider:
    """Return the configured real image/text encoder or a failing adapter.

    ``IMAGE_EMBEDDING_MODE=disabled`` is useful for a deliberately text-only
    deployment; it must be visible as an unavailable image index rather than a
    fake hash/vector implementation.
    """

    if config.IMAGE_EMBEDDING_MODE != "local":
        raise RuntimeError("image_embedding_mode_not_supported")
    # CLIP is lazy but substantial to load.  The image index and retrieval
    # paths use one configured model space, so keep the provider for the
    # process instead of reloading weights for every Tutor, Mentor, or query.
    # Image-provider configuration is process-scoped and takes effect after
    # the normal service restart.
    return ClipImageEmbeddingProvider(
        provider_id=config.IMAGE_EMBEDDING_PROVIDER or "clip",
        model_id=config.IMAGE_EMBEDDING_MODEL,
        cache_dir=config.IMAGE_EMBEDDING_CACHE,
    )
