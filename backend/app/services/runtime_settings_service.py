"""Instance-scoped runtime settings for TiBan's existing AI services.

Overrides live only in this process.  They deliberately restore the .env/Docker
defaults after a restart and never persist API keys to the database or logs.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from app.core import config


class RuntimeSettingsService:
    def __init__(self) -> None:
        self._lock = RLock()
        self._defaults = {
            "LLM_PROVIDER": config.LLM_PROVIDER,
            "LLM_BASE_URL": config.LLM_BASE_URL,
            "LLM_API_KEY": config.LLM_API_KEY,
            "LLM_MODEL": config.LLM_MODEL,
            "LLM_MODEL_REASONING_EFFORT": config.LLM_MODEL_REASONING_EFFORT,
            "FACTORY_PROVIDER_ENABLED": config.FACTORY_PROVIDER_ENABLED,
            "EMBEDDING_MODE": config.EMBEDDING_MODE,
            "EMBEDDING_PROVIDER": config.EMBEDDING_PROVIDER,
            "EMBEDDING_BASE_URL": config.EMBEDDING_BASE_URL,
            "EMBEDDING_API_KEY": config.EMBEDDING_API_KEY,
            "EMBEDDING_MODEL": config.EMBEDDING_MODEL,
            "EMBEDDING_LOCAL_MODEL": config.EMBEDDING_LOCAL_MODEL,
            "RERANKER_MODE": config.RERANKER_MODE,
            "RERANKER_PROVIDER": config.RERANKER_PROVIDER,
            "RERANKER_BASE_URL": config.RERANKER_BASE_URL,
            "RERANKER_API_KEY": config.RERANKER_API_KEY,
            "RERANKER_MODEL": config.RERANKER_MODEL,
        }
        self._llm_override = False
        self._embedding_batch_size = 32
        self._embedding_override = False

    _LLM_SETTING_NAMES = (
        "LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL",
        "LLM_MODEL_REASONING_EFFORT", "FACTORY_PROVIDER_ENABLED",
    )
    _EMBEDDING_SETTING_NAMES = (
        "EMBEDDING_MODE", "EMBEDDING_PROVIDER", "EMBEDDING_BASE_URL",
        "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "EMBEDDING_LOCAL_MODEL",
        "RERANKER_MODE", "RERANKER_PROVIDER", "RERANKER_BASE_URL",
        "RERANKER_API_KEY", "RERANKER_MODEL",
    )

    @staticmethod
    def _redis_key() -> str:
        return "tiban:runtime-settings:v1"

    @staticmethod
    def _runtime_file() -> Path:
        """Shared, ignored runtime-only settings for API/Worker processes.

        Redis intentionally carries only non-secret settings.  The API and
        Dramatiq worker are separate processes (and, in Compose, separate
        containers), so an applied instance key also needs a short-lived
        shared location.  This file is never returned by an API and is
        removed on service startup/restore; it is not canonical application
        data and lives below the already ignored runtime directory.
        """

        return Path(config.RUNTIME_DATA_DIR) / ".runtime-settings.json"

    @classmethod
    def _read_runtime_file(cls) -> dict[str, Any]:
        try:
            payload = json.loads(cls._runtime_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _write_runtime_file(cls, payload: dict[str, Any]) -> None:
        path = cls._runtime_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=".runtime-settings-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = handle.name
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            # API keys are runtime secrets, not shared application data.  On
            # POSIX hosts only the service account should be able to read the
            # file.  Windows ignores this mode, but the file remains outside
            # the frontend and is still deleted on restart/restore.
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        finally:
            if temporary_path:
                try:
                    Path(temporary_path).unlink(missing_ok=True)
                except OSError:
                    pass

    def _redis(self):
        try:
            import redis
            return redis.Redis.from_url(__import__("os").getenv("REDIS_URL", "redis://127.0.0.1:56379/0"), socket_connect_timeout=0.3, socket_timeout=0.3, decode_responses=True)
        except Exception:
            return None

    def sync(self) -> None:
        """Refresh a process from the short-lived shared runtime override.

        API and Dramatiq run in different processes. Redis is already part of
        the runtime, so this makes a deliberately applied instance setting
        visible to the next Tutor/Factory call without introducing a database
        table or persisting a secret in the browser.
        """
        # The local runtime file is the only cross-process carrier for secret
        # values.  Redis remains useful for non-secret settings and for
        # environments where the runtime directory is not shared.
        payload = self._read_runtime_file()
        client = self._redis()
        if client is not None:
            try:
                raw = client.get(self._redis_key())
                redis_payload = json.loads(raw) if raw else None
                if isinstance(redis_payload, dict):
                    payload = {**redis_payload, **payload}
            except Exception:
                pass
        if not payload:
            return
        with self._lock:
            for name in self._defaults:
                if name in payload:
                    setattr(config, name, payload[name])
            self._llm_override = bool(payload.get("llm_override"))
            self._embedding_batch_size = int(payload.get("embedding_batch_size", 32))
            self._embedding_override = bool(payload.get("embedding_override"))

    def _publish(self) -> None:
        payload = {
            **{name: getattr(config, name) for name in self._defaults},
            "llm_override": self._llm_override,
            "embedding_batch_size": self._embedding_batch_size,
            "embedding_override": self._embedding_override,
        }
        # Write the short-lived local carrier first so a Worker that starts
        # between this call and Redis publication still receives the same
        # instance configuration.  Secrets never enter Redis.
        self._write_runtime_file(payload)
        client = self._redis()
        if client is None:
            return
        redis_payload = {
            **{
                name: value
                for name, value in payload.items()
                if name not in {"LLM_API_KEY", "EMBEDDING_API_KEY", "RERANKER_API_KEY"}
            },
        }
        try:
            # The key intentionally has a bounded lifetime. The backend
            # startup hook also clears it, so a normal service restart returns
            # to .env/Docker defaults as described by the UI.
            client.set(self._redis_key(), json.dumps(redis_payload), ex=43_200)
        except Exception:
            return

    @staticmethod
    def _refresh_agent_runtimes() -> None:
        """Refresh long-lived Agent adapters after an instance setting change.

        The runners are created once at module composition time.  Mutating
        ``config`` alone is insufficient for the Mentor, whose gateway keeps
        a provider-enabled flag, and it makes the runtime behavior dependent
        on whether the process happened to be restarted.  Keep this refresh at
        the settings boundary so both agents continue to share the one
        authoritative runtime architecture.
        """

        from app.services.agent_runtime import refresh_tutor_runtime_gateway
        from app.services.mentor_agent_service import refresh_mentor_runtime_gateway

        refresh_tutor_runtime_gateway()
        refresh_mentor_runtime_gateway()

    def reset_shared(self) -> None:
        # The FastAPI startup hook can be exercised more than once in a test
        # process, and a development reload may reuse the module instance.
        # Restore the captured .env/Docker defaults in memory as well as
        # removing the cross-process carrier; otherwise a prior instance
        # override could survive a nominal restart in the same interpreter.
        with self._lock:
            for name, value in self._defaults.items():
                setattr(config, name, value)
            self._llm_override = False
            self._embedding_batch_size = 32
            self._embedding_override = False
        client = self._redis()
        if client is not None:
            try:
                client.delete(self._redis_key())
            except Exception:
                pass
        try:
            self._runtime_file().unlink(missing_ok=True)
        except OSError:
            pass
        self._refresh_agent_runtimes()

    @staticmethod
    def _key_configured(value: str | None) -> bool:
        return bool(value and len(value.strip()) >= 6 and value.strip().lower() not in {"none", "placeholder", "your_api_key"})

    def llm_public(self) -> dict[str, Any]:
        self.sync()
        with self._lock:
            return {
                "provider": config.LLM_PROVIDER,
                "base_url_configured": bool(config.LLM_BASE_URL),
                "api_key_configured": self._key_configured(config.LLM_API_KEY),
                "model": config.LLM_MODEL,
                "reasoning_effort": config.LLM_MODEL_REASONING_EFFORT or None,
                "runtime_override": self._llm_override,
                "restores_default_on_restart": True,
                "private_network_allowed": config.LLM_PROVIDER_ALLOW_PRIVATE_NETWORK,
            }

    def apply_llm(self, *, provider: str, base_url: str, model: str, api_key: str | None, reasoning_effort: str | None) -> dict[str, Any]:
        with self._lock:
            config.LLM_PROVIDER = provider.strip() or config.LLM_PROVIDER
            config.LLM_BASE_URL = base_url.strip().rstrip("/")
            config.LLM_MODEL = model.strip() or config.LLM_MODEL
            if api_key and api_key.strip():
                config.LLM_API_KEY = api_key.strip()
            if reasoning_effort is not None:
                config.LLM_MODEL_REASONING_EFFORT = reasoning_effort.strip().lower()
            config.FACTORY_PROVIDER_ENABLED = True
            self._llm_override = True
            self._publish()
        self._refresh_agent_runtimes()
        return self.llm_public()

    def restore_llm(self) -> dict[str, Any]:
        with self._lock:
            for name in self._LLM_SETTING_NAMES:
                setattr(config, name, self._defaults[name])
            self._llm_override = False
            self._publish()
        self._refresh_agent_runtimes()
        return self.llm_public()

    def embedding_public(self) -> dict[str, Any]:
        from app.services.rag_service import rag_service
        from app.services.semantic_memory_service import MEMORY_INDEX_KEY
        from app.db.database import SessionLocal
        from app.db.models import VectorIndexStateModel

        self.sync()
        with self._lock:
            provider = rag_service.embedding_provider
            with SessionLocal() as session:
                states = {
                    row.index_key: row
                    for row in session.scalars(__import__("sqlalchemy").select(VectorIndexStateModel).where(VectorIndexStateModel.index_key.in_(["knowledge", MEMORY_INDEX_KEY])))
                }
            return {
                "mode": config.EMBEDDING_MODE,
                "provider": config.EMBEDDING_PROVIDER,
                "base_url_configured": bool(config.EMBEDDING_BASE_URL),
                "api_key_configured": self._key_configured(config.EMBEDDING_API_KEY),
                "model": config.EMBEDDING_MODEL,
                "local_model": config.EMBEDDING_LOCAL_MODEL,
                "active_provider": provider.provider_id,
                "active_model": provider.model_id,
                "reranker_mode": config.RERANKER_MODE,
                "reranker_provider": config.RERANKER_PROVIDER,
                "reranker_model": config.RERANKER_MODEL,
                "batch_size": self._embedding_batch_size,
                "runtime_override": self._embedding_override,
                "restores_default_on_restart": True,
                "model_switch_supported": True,
                "knowledge_index_status": states.get("knowledge").status if states.get("knowledge") else "stale",
                "memory_index_status": states.get(MEMORY_INDEX_KEY).status if states.get(MEMORY_INDEX_KEY) else "stale",
            }

    def embedding_batch_size(self) -> int:
        self.sync()
        with self._lock:
            return self._embedding_batch_size

    def apply_embedding(
        self,
        *,
        batch_size: int,
        mode: str = "api",
        provider: str = "siliconflow",
        base_url: str = "",
        api_key: str | None = None,
        model: str = "BAAI/bge-m3",
        local_model: str = "BAAI/bge-small-zh-v1.5",
        reranker_mode: str = "api",
        reranker_provider: str = "siliconflow",
        reranker_base_url: str = "",
        reranker_api_key: str | None = None,
        reranker_model: str = "BAAI/bge-reranker-v2-m3",
    ) -> dict[str, Any]:
        if not 1 <= batch_size <= 64:
            raise ValueError("Embedding batch size must be between 1 and 64.")
        if mode not in {"api", "local"}:
            raise ValueError("Embedding mode must be api or local.")
        if reranker_mode not in {"api", "local"}:
            raise ValueError("Reranker mode must be api or local.")
        with self._lock:
            self._embedding_batch_size = batch_size
            config.EMBEDDING_MODE = mode
            config.EMBEDDING_PROVIDER = provider.strip() or config.EMBEDDING_PROVIDER
            config.EMBEDDING_BASE_URL = base_url.strip().rstrip("/") or config.EMBEDDING_BASE_URL
            config.EMBEDDING_MODEL = model.strip() or config.EMBEDDING_MODEL
            config.EMBEDDING_LOCAL_MODEL = local_model.strip() or config.EMBEDDING_LOCAL_MODEL
            if api_key and api_key.strip():
                config.EMBEDDING_API_KEY = api_key.strip()
            config.RERANKER_MODE = reranker_mode
            config.RERANKER_PROVIDER = reranker_provider.strip() or config.RERANKER_PROVIDER
            # The default SiliconFlow deployment exposes both endpoints from
            # the same OpenAI-compatible base. An explicit reranker URL is
            # supported for self-hosted instances; otherwise follow the
            # embedding endpoint supplied in this single instance settings
            # form instead of leaving a stale URL active.
            config.RERANKER_BASE_URL = (
                reranker_base_url.strip().rstrip("/")
                or config.EMBEDDING_BASE_URL
                or config.RERANKER_BASE_URL
            )
            config.RERANKER_MODEL = reranker_model.strip() or config.RERANKER_MODEL
            if reranker_api_key and reranker_api_key.strip():
                config.RERANKER_API_KEY = reranker_api_key.strip()
            elif api_key and api_key.strip():
                # Keep the compact UI convenient for providers that use one
                # instance key for embeddings and reranking.
                config.RERANKER_API_KEY = api_key.strip()
            self._embedding_override = True
            self._publish()
        # A provider/model switch invalidates both derived indexes. Canonical
        # source text and Learning Memory are untouched until a real rebuild.
        from app.services.rag_service import rag_service
        from app.services.semantic_memory_service import semantic_memory_service

        rag_service.mark_index_stale()
        semantic_memory_service.mark_index_stale()
        return self.embedding_public()

    def restore_embedding(self) -> dict[str, Any]:
        with self._lock:
            self._embedding_batch_size = 32
            for name in (
                "EMBEDDING_MODE", "EMBEDDING_PROVIDER", "EMBEDDING_BASE_URL", "EMBEDDING_API_KEY",
                "EMBEDDING_MODEL", "EMBEDDING_LOCAL_MODEL", "RERANKER_MODE", "RERANKER_PROVIDER",
                "RERANKER_BASE_URL", "RERANKER_API_KEY", "RERANKER_MODEL",
            ):
                setattr(config, name, self._defaults[name])
            self._embedding_override = False
            self._publish()
        from app.services.rag_service import rag_service
        from app.services.semantic_memory_service import semantic_memory_service

        rag_service.mark_index_stale()
        semantic_memory_service.mark_index_stale()
        return self.embedding_public()

    def test_embedding_config(
        self,
        *,
        mode: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        local_model: str | None = None,
    ) -> dict[str, Any]:
        """Probe supplied settings without mutating the active runtime."""

        from pathlib import Path

        from app.services.embedding_provider import LocalFastEmbedProvider, OpenAICompatibleEmbeddingProvider

        self.sync()
        selected_mode = mode or config.EMBEDDING_MODE
        selected_provider = provider or config.EMBEDDING_PROVIDER
        selected_base_url = (base_url or config.EMBEDDING_BASE_URL).strip()
        selected_key = api_key or config.EMBEDDING_API_KEY
        selected_model = model or config.EMBEDDING_MODEL
        if selected_mode == 'api':
            if not selected_base_url or not selected_key:
                raise ValueError('API 模式需要可用的 Base URL 与 API Key。')
            active = OpenAICompatibleEmbeddingProvider(
                provider_id=selected_provider, model_id=selected_model, base_url=selected_base_url,
                api_key=selected_key, timeout_seconds=config.EMBEDDING_TIMEOUT_SECONDS,
            )
        elif selected_mode == 'local':
            active = LocalFastEmbedProvider(
                provider_id='local_fastembed', model_id=local_model or config.EMBEDDING_LOCAL_MODEL,
                cache_dir=Path(config.RUNTIME_DATA_DIR) / 'fastembed',
            )
        else:
            raise ValueError('Embedding 模式必须是 api 或 local。')
        vector = active.embed_query('TiBan embedding readiness probe')
        return {'provider': active.provider_id, 'model': active.model_id, 'dimension': len(vector)}

    def enqueue_index_rebuild(self) -> dict[str, Any]:
        """Queue one rebuild for both derived indexes; canonical data is untouched."""

        from sqlalchemy import select

        from app.db.database import SessionLocal
        from app.db.models import BackgroundJobModel
        from app.services.rag_service import rag_service
        from app.services.semantic_memory_service import semantic_memory_service

        rag_service.mark_index_stale()
        semantic_memory_service.mark_index_stale()
        with SessionLocal() as session:
            current = session.scalar(select(BackgroundJobModel).where(
                BackgroundJobModel.job_type == 'vector_index_rebuild',
                BackgroundJobModel.status.in_(['queued', 'running']),
            ).order_by(BackgroundJobModel.created_at.desc()))
            if current is not None:
                return {'job_id': current.job_id, 'status': current.status, 'stage': current.stage, 'progress': current.progress}
            row = BackgroundJobModel(
                job_id=f'index_rebuild_{uuid4().hex[:12]}', job_type='vector_index_rebuild', target_id='all',
                status='queued', stage='queued', progress=0, idempotency_key=f'index-rebuild:{uuid4().hex[:12]}',
                detail={'requested_at': datetime.utcnow().isoformat()},
            )
            session.add(row)
            session.commit()
        result_status, result_stage, result_progress = row.status, row.stage, row.progress
        try:
            from app.workers.background_worker import rebuild_vector_indexes_actor

            rebuild_vector_indexes_actor.send(row.job_id)
        except Exception as exc:
            result_status, result_stage = 'failed', 'dispatch_failed'
            with SessionLocal() as session:
                failed = session.get(BackgroundJobModel, row.job_id)
                if failed is not None:
                    failed.status, failed.stage = 'failed', 'dispatch_failed'
                    failed.error_message = type(exc).__name__
                    failed.completed_at = datetime.utcnow()
                    session.commit()
        return {'job_id': row.job_id, 'status': result_status, 'stage': result_stage, 'progress': result_progress}

    def process_index_rebuild(self, job_id: str) -> dict[str, Any]:
        """Worker-side implementation for the single active vector representation."""

        from app.db.database import SessionLocal
        from app.db.models import BackgroundJobModel
        from app.services.rag_service import rag_service
        from app.services.semantic_memory_service import semantic_memory_service

        with SessionLocal() as session:
            job = session.get(BackgroundJobModel, job_id)
            if job is None or job.job_type != 'vector_index_rebuild':
                raise KeyError(job_id)
            if job.status == 'completed':
                return {'job_id': job_id, 'status': 'completed'}
            job.status, job.stage, job.progress, job.started_at = 'running', '重建知识索引', 15, datetime.utcnow()
            session.commit()
        try:
            knowledge_chunks = len(rag_service.rebuild_knowledge_index())
            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                assert job is not None
                job.stage, job.progress = '重建学习记忆索引', 70
                session.commit()
            memories = semantic_memory_service.rebuild()
            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                assert job is not None
                job.status, job.stage, job.progress, job.completed_at = 'completed', '完成', 100, datetime.utcnow()
                job.detail = {**dict(job.detail or {}), 'knowledge_chunks': knowledge_chunks, 'memory_items': memories}
                session.commit()
            return {'job_id': job_id, 'status': 'completed', 'knowledge_chunks': knowledge_chunks, 'memory_items': memories}
        except Exception as exc:
            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                if job is not None:
                    job.status, job.stage, job.error_message, job.completed_at = 'failed', 'failed', type(exc).__name__, datetime.utcnow()
                    session.commit()
            raise


runtime_settings_service = RuntimeSettingsService()
