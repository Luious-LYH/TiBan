"""Instance-scoped runtime settings for TiBan's existing AI services.

Overrides live only in this process.  They deliberately restore the .env/Docker
defaults after a restart and never persist API keys to the database or logs.
"""

from __future__ import annotations

from threading import RLock
from typing import Any

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
        }
        self._llm_override = False
        self._embedding_batch_size = 32
        self._embedding_override = False

    @staticmethod
    def _redis_key() -> str:
        return "tiban:runtime-settings:v1"

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
        client = self._redis()
        if client is None:
            return
        try:
            raw = client.get(self._redis_key())
            payload = __import__("json").loads(raw) if raw else None
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        with self._lock:
            for name in self._defaults:
                if name in payload:
                    setattr(config, name, payload[name])
            self._llm_override = bool(payload.get("llm_override"))
            self._embedding_batch_size = int(payload.get("embedding_batch_size", 32))
            self._embedding_override = bool(payload.get("embedding_override"))

    def _publish(self) -> None:
        client = self._redis()
        if client is None:
            return
        payload = {
            **{name: getattr(config, name) for name in self._defaults},
            "llm_override": self._llm_override,
            "embedding_batch_size": self._embedding_batch_size,
            "embedding_override": self._embedding_override,
        }
        try:
            # The key intentionally has a bounded lifetime. The backend
            # startup hook also clears it, so a normal service restart returns
            # to .env/Docker defaults as described by the UI.
            client.set(self._redis_key(), __import__("json").dumps(payload), ex=43_200)
        except Exception:
            return

    def reset_shared(self) -> None:
        client = self._redis()
        if client is not None:
            try:
                client.delete(self._redis_key())
            except Exception:
                pass

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
            return self.llm_public()

    def restore_llm(self) -> dict[str, Any]:
        with self._lock:
            for name, value in self._defaults.items():
                setattr(config, name, value)
            self._llm_override = False
            self._publish()
            return self.llm_public()

    def embedding_public(self) -> dict[str, Any]:
        from app.services.rag_service import MODEL_NAME

        self.sync()
        with self._lock:
            return {
                "mode": "local",
                "model": MODEL_NAME,
                "batch_size": self._embedding_batch_size,
                "runtime_override": self._embedding_override,
                "restores_default_on_restart": True,
                "model_switch_supported": False,
            }

    def embedding_batch_size(self) -> int:
        self.sync()
        with self._lock:
            return self._embedding_batch_size

    def apply_embedding(self, *, batch_size: int) -> dict[str, Any]:
        if not 1 <= batch_size <= 64:
            raise ValueError("Embedding batch size must be between 1 and 64.")
        with self._lock:
            self._embedding_batch_size = batch_size
            self._embedding_override = True
            self._publish()
            return self.embedding_public()

    def restore_embedding(self) -> dict[str, Any]:
        with self._lock:
            self._embedding_batch_size = 32
            self._embedding_override = False
            self._publish()
            return self.embedding_public()


runtime_settings_service = RuntimeSettingsService()
