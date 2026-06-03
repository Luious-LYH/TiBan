import base64
import json
import mimetypes
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core import config


@dataclass
class LLMResult:
    ok: bool
    text: str
    mode: str
    provider: str
    model: str
    error: str | None = None
    latency_ms: int | None = None
    image_attached: bool = False

    def public_status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "ok": self.ok,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "image_attached": self.image_attached,
        }


class LLMProvider:
    def status(self) -> dict[str, Any]:
        configured = bool(config.LLM_BASE_URL and config.LLM_API_KEY and config.LLM_PROVIDER != "mock")
        return {
            "configured": configured,
            "provider": config.LLM_PROVIDER,
            "base_url_configured": bool(config.LLM_BASE_URL),
            "api_key_configured": bool(config.LLM_API_KEY),
            "model": config.LLM_MODEL,
            "mode": "provider" if configured else "rule",
            "safety_notice": "真实 provider 仅用于公开教学样例和医生审核前辅助，不上传真实患者身份信息。",
        }

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_path: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 700,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> LLMResult:
        effective_provider = provider or config.LLM_PROVIDER
        effective_base_url = (base_url if base_url is not None else config.LLM_BASE_URL).rstrip("/")
        effective_api_key = api_key if api_key is not None else config.LLM_API_KEY
        effective_model = model or config.LLM_MODEL
        image_data = self._image_data_url(image_path) if image_path else None
        image_attached = bool(image_data)
        if not (effective_base_url and effective_api_key and effective_provider != "mock"):
            return LLMResult(False, "", "rule", effective_provider, effective_model, "provider_not_configured", image_attached=image_attached)

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        user_content: str | list[dict[str, Any]]
        if image_data:
            user_content = [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_data}},
            ]
        else:
            user_content = user_prompt
        messages.append({"role": "user", "content": user_content})

        body = {
            "model": effective_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        endpoint = f"{effective_base_url}/chat/completions"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {effective_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            import time

            started = time.perf_counter()
            with urllib.request.urlopen(request, timeout=config.LLM_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
            latency_ms = round((time.perf_counter() - started) * 1000)
            text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            text = self._clean_text(str(text))
            if not text:
                return LLMResult(False, "", "provider", effective_provider, effective_model, "empty_response", latency_ms, image_attached)
            return LLMResult(True, text, "provider", effective_provider, effective_model, None, latency_ms, image_attached)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:240]
            return LLMResult(False, "", "provider", effective_provider, effective_model, f"http_{exc.code}: {detail}", image_attached=image_attached)
        except Exception as exc:
            return LLMResult(False, "", "provider", effective_provider, effective_model, type(exc).__name__, image_attached=image_attached)

    def _image_data_url(self, image_path: str | None) -> str | None:
        if not image_path:
            return None
        path = self._resolve_public_image(image_path)
        if not path or not path.exists() or path.stat().st_size > 2_500_000:
            return None
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _resolve_public_image(self, image_path: str) -> Path | None:
        if image_path.startswith("/assets/real_samples/"):
            return config.PROJECT_DIR / "frontend" / "public" / image_path.lstrip("/")
        if image_path.startswith("assets/real_samples/"):
            return config.PROJECT_DIR / "frontend" / "public" / image_path
        if image_path.startswith("uploads/"):
            resolved = (config.UPLOAD_DIR / image_path.removeprefix("uploads/")).resolve()
            upload_root = config.UPLOAD_DIR.resolve()
            if upload_root == resolved or upload_root in resolved.parents:
                return resolved
        return None

    def _clean_text(self, text: str) -> str:
        cleaned = text.strip()
        return cleaned[:4000]


llm_provider = LLMProvider()
