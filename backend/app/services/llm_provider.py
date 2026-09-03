import base64
import http.client
import ipaddress
import json
import mimetypes
import socket
import ssl
import time
import urllib.error
import urllib.parse
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
    usage: dict[str, int] | None = None

    def public_status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "ok": self.ok,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "image_attached": self.image_attached,
            "usage": self.usage or {},
        }


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, connect_host: str, timeout: int | float) -> None:
        super().__init__(host=host, port=port, timeout=timeout)
        self._connect_host = connect_host

    def connect(self) -> None:
        self.sock = socket.create_connection((self._connect_host, self.port), self.timeout, self.source_address)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, connect_host: str, timeout: int | float) -> None:
        super().__init__(host=host, port=port, timeout=timeout, context=ssl.create_default_context())
        self._connect_host = connect_host

    def connect(self) -> None:
        raw_sock = socket.create_connection((self._connect_host, self.port), self.timeout, self.source_address)
        self.sock = self._context.wrap_socket(raw_sock, server_hostname=self.host)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:  # type: ignore[override]
        return None


class LLMProvider:
    _TRANSIENT_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}
    _CHAT_RETRIES = 2
    # Some managed development networks intentionally map public domains to
    # RFC 2544 benchmark addresses and rely on the system HTTPS proxy.  Keep
    # the SSRF checks strict for every other hostname, but allow this exact
    # set of provider domains to use urllib's configured proxy when the
    # resolution is only that synthetic 198.18.0.0/15 mapping.
    _PUBLIC_PROVIDER_HOSTS = frozenset({
        "api.cloudflare.com",
        "api.siliconflow.cn",
        "open.bigmodel.cn",
        "openrouter.ai",
    })

    def _local_demo_provider_paths(self) -> list[Path]:
        return [
            config.PROJECT_DIR / ".demo_llm_providers.json",
            config.BACKEND_DIR / ".demo_llm_providers.json",
        ]

    def _local_demo_provider_entries(self) -> list[dict[str, Any]]:
        for path in self._local_demo_provider_paths():
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, list):
                entries = payload
            elif isinstance(payload, dict):
                entries = payload.get("providers", [])
            else:
                entries = []
            return [entry for entry in entries if isinstance(entry, dict)]
        return []

    def _local_demo_provider_attempts(self) -> list[dict[str, str]]:
        attempts: list[dict[str, str]] = []
        for entry in self._local_demo_provider_entries():
            base_url = self._normalize_base_url(str(entry.get("base_url") or entry.get("api_base") or ""))
            api_key = str(entry.get("api_key") or entry.get("key") or "").strip()
            model = str(entry.get("model") or config.LLM_MODEL or "gpt-5.6-sol").strip()
            provider = str(entry.get("provider") or "openai_compatible").strip()
            if provider and base_url and self._is_usable_api_key(api_key) and model and provider != "mock":
                attempts.append(
                    {
                        "provider": provider,
                        "base_url": base_url,
                        "api_key": api_key,
                        "model": model,
                    }
                )
        return attempts

    def _local_demo_provider_hosts(self) -> set[str]:
        hosts: set[str] = set()
        for attempt in self._local_demo_provider_attempts():
            try:
                parsed = urllib.parse.urlsplit(attempt["base_url"])
            except ValueError:
                continue
            hostname = self._parsed_hostname(parsed)
            if hostname:
                hosts.add(hostname)
        return hosts

    def status(self) -> dict[str, Any]:
        from app.services.runtime_settings_service import runtime_settings_service
        runtime_settings_service.sync()
        demo_attempts = self._local_demo_provider_attempts()
        demo_configured = bool(demo_attempts)
        primary_configured = bool(
            config.LLM_BASE_URL
            and self._is_usable_api_key(config.LLM_API_KEY)
            and config.LLM_PROVIDER != "mock"
        )
        fallback_configured = bool(
            config.LLM_FALLBACK_BASE_URL
            and self._is_usable_api_key(config.LLM_FALLBACK_API_KEY)
            and config.LLM_FALLBACK_PROVIDER != "mock"
        )
        final_fallback_configured = bool(
            config.LLM_FINAL_FALLBACK_BASE_URL
            and self._is_usable_api_key(config.LLM_FINAL_FALLBACK_API_KEY)
            and config.LLM_FINAL_FALLBACK_PROVIDER != "mock"
        )
        configured = demo_configured or primary_configured or fallback_configured or final_fallback_configured
        active_provider = demo_attempts[0]["provider"] if demo_configured else (
            config.LLM_PROVIDER if primary_configured else (
                config.LLM_FALLBACK_PROVIDER if fallback_configured else config.LLM_FINAL_FALLBACK_PROVIDER
            )
        )
        active_model = demo_attempts[0]["model"] if demo_configured else (
            config.LLM_MODEL if primary_configured else (
                config.LLM_FALLBACK_MODEL if fallback_configured else config.LLM_FINAL_FALLBACK_MODEL
            )
        )
        return {
            "configured": configured,
            "provider": active_provider,
            "base_url_configured": bool(demo_configured or config.LLM_BASE_URL or config.LLM_FALLBACK_BASE_URL or config.LLM_FINAL_FALLBACK_BASE_URL),
            "api_key_configured": bool(
                demo_configured
                or self._is_usable_api_key(config.LLM_API_KEY)
                or self._is_usable_api_key(config.LLM_FALLBACK_API_KEY)
                or self._is_usable_api_key(config.LLM_FINAL_FALLBACK_API_KEY)
            ),
            "model": active_model,
            "mode": "provider" if configured else "rule",
            "fallback_provider_configured": fallback_configured,
            "final_fallback_provider_configured": final_fallback_configured,
            "private_host_allowlist_configured": bool(config.LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST),
            "private_host_allowlist_count": len(config.LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST),
            "safety_notice": "真实 provider 仅用于公开教学样例和医生审核前辅助，不上传真实患者身份信息。",
        }

    def preflight(self, base_url: str | None = None) -> dict[str, Any]:
        from app.services.runtime_settings_service import runtime_settings_service
        runtime_settings_service.sync()
        raw_base_url = (base_url or "").strip()
        warnings: list[str] = []
        next_actions = [
            "确认 API Base 指向 OpenAI-compatible 服务根地址、/v1 或完整 /chat/completions。",
            "确认临时 key 或后端 .env key 可用后，再运行文本轻量自检。",
            "文本自检通过后，再运行视觉通道自检和公开样例级准入。",
        ]
        source = "temporary_base"
        if not raw_base_url or "api.example.com" in raw_base_url:
            if not config.LLM_BASE_URL:
                return {
                    "ok": False,
                    "safety_status": "missing_base_url",
                    "mode": "rule",
                    "normalized_preview": None,
                    "endpoint_paths": [],
                    "blocked_reason": "missing_base_url",
                    "warnings": ["未填写临时 API Base，后端 .env 也未配置 LLM_BASE_URL；当前会保持 rule 模式。"],
                    "next_actions": next_actions,
                    "private_host_allowlist_configured": bool(config.LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST),
                    "private_host_allowlist_used": False,
                    "key_required_for_call": True,
                    "request_sent": False,
                    "key_persisted": False,
                }
            raw_base_url = config.LLM_BASE_URL
            source = "backend_env"

        had_scheme = "://" in raw_base_url
        normalized = self._normalize_base_url(raw_base_url)
        try:
            parsed = urllib.parse.urlsplit(normalized)
        except ValueError:
            return {
                "ok": False,
                "safety_status": "blocked",
                "mode": "blocked",
                "normalized_preview": None,
                "endpoint_paths": [],
                "blocked_reason": "invalid_url",
                "warnings": warnings,
                "next_actions": self._preflight_next_actions("invalid_url"),
                "private_host_allowlist_configured": bool(config.LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST),
                "private_host_allowlist_used": False,
                "key_required_for_call": True,
                "request_sent": False,
                "key_persisted": False,
            }
        if not had_scheme:
            warnings.append("未写协议，外部域名已按 https:// 处理；localhost/127.0.0.1 已按 http:// 处理。")
        if parsed.query or parsed.fragment:
            warnings.append("query/fragment 会被丢弃，不会附加到 chat completions endpoint。")
        reason = self._base_url_block_reason(parsed)
        normalized_preview = self._safe_preflight_preview(parsed, source)
        if reason:
            return {
                "ok": False,
                "safety_status": "blocked",
                "mode": "blocked",
                "normalized_preview": normalized_preview,
                "endpoint_paths": [],
                "blocked_reason": reason,
                "warnings": warnings,
                "next_actions": self._preflight_next_actions(reason),
                "private_host_allowlist_configured": bool(config.LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST),
                "private_host_allowlist_used": False,
                "key_required_for_call": True,
                "request_sent": False,
                "key_persisted": False,
            }

        endpoints = self._chat_completion_endpoints(normalized)
        endpoint_paths = [urllib.parse.urlsplit(endpoint).path for endpoint in endpoints]
        private_allowlist_used = self._host_uses_private_allowlist(parsed)
        if parsed.scheme.lower() == "http":
            warnings.append("http 仅允许 localhost/127.0.0.1/[::1] 等本机调试地址。")
        if private_allowlist_used:
            warnings.append("该 Provider host 解析到私有/保留地址，已由后端 .env 的精确白名单显式放行；前端临时输入不能修改白名单。")
        if source == "backend_env":
            warnings.append("当前使用后端 .env 的 LLM_BASE_URL；为避免泄露，前端不回传完整 base 明文。")
        return {
            "ok": bool(endpoint_paths),
            "safety_status": "allowed",
            "mode": source,
            "normalized_preview": normalized_preview,
            "endpoint_paths": endpoint_paths,
            "blocked_reason": None,
            "warnings": warnings,
            "next_actions": next_actions,
            "private_host_allowlist_configured": bool(config.LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST),
            "private_host_allowlist_used": private_allowlist_used,
            "key_required_for_call": True,
            "request_sent": False,
            "key_persisted": False,
        }

    def runtime_request_config(self, *, model: str | None = None) -> dict[str, str] | None:
        """Return the active instance connection without exposing it publicly.

        Evaluation workers need to pin the selected runtime endpoint while the
        model name remains a per-candidate value.  The returned key is used
        only in the process-local/runtime-only evaluation secret handoff; it
        is never a database, artifact, log, trace, or broker field.
        """
        from app.services.runtime_settings_service import runtime_settings_service

        runtime_settings_service.sync()
        attempts = self._provider_attempts(
            base_url=None, api_key=None, model=model, provider=None, allow_fallback=False,
        )
        if not attempts:
            return None
        selected = dict(attempts[0])
        if model:
            selected["model"] = model
        return {key: str(value) for key, value in selected.items()}

    def _request_json(self, endpoint: str, body: dict[str, Any], api_key: str) -> tuple[int, bytes]:
        parsed = urllib.parse.urlsplit(endpoint)
        self._validate_base_url(parsed)
        hostname = self._parsed_hostname(parsed)
        if not hostname:
            raise ValueError("unsafe_base_url")
        scheme = parsed.scheme.lower()
        port = parsed.port or (443 if scheme == "https" else 80)
        # Use the standard opener for the explicitly allowlisted public
        # providers. It preserves the hostname for TLS and respects the
        # machine's configured HTTPS proxy, which is required in environments
        # whose DNS maps public hosts to 198.18/15. Redirects remain blocked.
        if scheme == "https" and hostname in self._PUBLIC_PROVIDER_HOSTS:
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            opener = urllib.request.build_opener(_NoRedirectHandler)
            try:
                with opener.open(request, timeout=config.LLM_TIMEOUT_SECONDS) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read()
        connect_host = self._resolve_connection_host(hostname, port)
        payload = json.dumps(body).encode("utf-8")
        path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        connection: http.client.HTTPConnection
        if scheme == "https":
            connection = _PinnedHTTPSConnection(hostname, port, connect_host, config.LLM_TIMEOUT_SECONDS)
        else:
            connection = _PinnedHTTPConnection(hostname, port, connect_host, config.LLM_TIMEOUT_SECONDS)
        try:
            connection.request("POST", path, body=payload, headers=headers)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

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
        allow_fallback: bool = True,
    ) -> LLMResult:
        from app.services.runtime_settings_service import runtime_settings_service
        runtime_settings_service.sync()
        image_data = self._image_data_url(image_path) if image_path else None
        image_attached = bool(image_data)
        attempts = self._provider_attempts(
            base_url=base_url,
            api_key=api_key,
            model=model,
            provider=provider,
            allow_fallback=allow_fallback,
        )
        if not attempts:
            return LLMResult(False, "", "rule", provider or config.LLM_PROVIDER, model or config.LLM_MODEL, "provider_not_configured", image_attached=image_attached)

        last_result: LLMResult | None = None
        for attempt in attempts:
            for retry_index in range(self._CHAT_RETRIES + 1):
                result = self._chat_once(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    image_data=image_data,
                    image_attached=image_attached,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    effective_provider=attempt["provider"],
                    effective_base_url=attempt["base_url"],
                    effective_api_key=attempt["api_key"],
                    effective_model=attempt["model"],
                )
                if result.ok:
                    return result
                last_result = result
                if retry_index < self._CHAT_RETRIES and self._is_transient_provider_error(result.error):
                    time.sleep(0.5 * (2**retry_index))
                    continue
                break
        return last_result or LLMResult(False, "", "rule", provider or config.LLM_PROVIDER, model or config.LLM_MODEL, "provider_not_configured", image_attached=image_attached)

    def _is_transient_provider_error(self, error: str | None) -> bool:
        if not error:
            return False
        return any(
            error.startswith(f"http_{status}")
            for status in self._TRANSIENT_HTTP_STATUSES
        ) or error in {"TimeoutError", "socket.timeout", "RemoteDisconnected", "ConnectionResetError"}

    def _provider_attempts(
        self,
        *,
        base_url: str | None,
        api_key: str | None,
        model: str | None,
        provider: str | None,
        allow_fallback: bool = True,
    ) -> list[dict[str, str]]:
        explicit_provider_requested = bool((base_url or "").strip() or (api_key or "").strip())
        candidates: list[dict[str, str | None]] = []
        if explicit_provider_requested:
            candidates.append(
                {
                    "provider": provider or config.LLM_PROVIDER,
                    "base_url": self._normalize_base_url(base_url or ""),
                    "api_key": api_key or "",
                    "model": model or config.LLM_MODEL,
                }
            )
        else:
            candidates.extend(self._local_demo_provider_attempts())
        if not explicit_provider_requested or allow_fallback:
            candidates.append(
                {
                    "provider": provider or config.LLM_PROVIDER,
                    "base_url": self._normalize_base_url(config.LLM_BASE_URL),
                    "api_key": config.LLM_API_KEY,
                    "model": model or config.LLM_MODEL,
                }
            )
        if allow_fallback:
            candidates.append(
                {
                    "provider": config.LLM_FALLBACK_PROVIDER,
                    "base_url": self._normalize_base_url(config.LLM_FALLBACK_BASE_URL),
                    "api_key": config.LLM_FALLBACK_API_KEY,
                    "model": config.LLM_FALLBACK_MODEL,
                }
            )
            candidates.append(
                {
                    "provider": config.LLM_FINAL_FALLBACK_PROVIDER,
                    "base_url": self._normalize_base_url(config.LLM_FINAL_FALLBACK_BASE_URL),
                    "api_key": config.LLM_FINAL_FALLBACK_API_KEY,
                    "model": config.LLM_FINAL_FALLBACK_MODEL,
                }
            )
        attempts: list[dict[str, str]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for candidate in candidates:
            provider_value = str(candidate["provider"] or "")
            base_value = str(candidate["base_url"] or "")
            key_value = str(candidate["api_key"] or "")
            model_value = str(candidate["model"] or "")
            if not (provider_value and base_value and self._is_usable_api_key(key_value) and provider_value != "mock"):
                continue
            fingerprint = (provider_value, base_value, key_value, model_value)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            attempts.append({
                "provider": provider_value,
                "base_url": base_value,
                "api_key": key_value,
                "model": model_value,
            })
        return attempts

    def _is_usable_api_key(self, value: str | None) -> bool:
        key = str(value or "").strip()
        if not key:
            return False
        lowered = key.lower()
        if lowered.startswith(("http://", "https://")):
            return False
        placeholders = {
            "sk-****",
            "your-api-key",
            "your_api_key",
            "api-key",
            "apikey",
            "test",
            "demo",
        }
        return lowered not in placeholders

    def _chat_once(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_data: str | None,
        image_attached: bool,
        temperature: float,
        max_tokens: int,
        effective_provider: str,
        effective_base_url: str,
        effective_api_key: str,
        effective_model: str,
    ) -> LLMResult:

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
        # Qwen3 on Workers AI may place the final short answer in
        # ``reasoning_content`` unless its chat template is explicitly told to
        # disable thinking.  Keep the public Tutor path answer-only; raw
        # private reasoning must never be surfaced to the learner.
        cloudflare_thinking_disabled = False
        try:
            cloudflare_thinking_disabled = (
                self._canonical_hostname(urllib.parse.urlsplit(effective_base_url).hostname or "")
                == "api.cloudflare.com"
            )
        except ValueError:
            pass
        if cloudflare_thinking_disabled:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        if config.LLM_MODEL_REASONING_EFFORT:
            body["model_reasoning_effort"] = config.LLM_MODEL_REASONING_EFFORT
        try:
            started = time.perf_counter()
            last_error = "provider_error"
            endpoints = self._chat_completion_endpoints(effective_base_url)
            for endpoint_index, endpoint in enumerate(endpoints):
                status, response_body = self._request_json(endpoint, body, effective_api_key)
                if 300 <= status < 400:
                    last_error = f"redirect_blocked_{status}"
                    return LLMResult(False, "", "provider", effective_provider, effective_model, last_error, image_attached=image_attached)
                if not 200 <= status < 300:
                    detail = response_body.decode("utf-8", errors="ignore")[:240]
                    last_error = f"http_{status}: {detail}"
                    if status in {404, 405} and endpoint_index < len(endpoints) - 1:
                        continue
                    return LLMResult(False, "", "provider", effective_provider, effective_model, last_error, image_attached=image_attached)
                payload = json.loads(response_body.decode("utf-8"))
                latency_ms = round((time.perf_counter() - started) * 1000)
                message = payload.get("choices", [{}])[0].get("message", {}) or {}
                raw_content = message.get("content")
                if isinstance(raw_content, str):
                    text = raw_content
                elif isinstance(raw_content, list):
                    text = "".join(
                        str(part.get("text", ""))
                        for part in raw_content
                        if isinstance(part, dict) and isinstance(part.get("text"), str)
                    )
                else:
                    # Cloudflare's OpenAI-compatible adapter currently emits
                    # the answer in reasoning_content when the Qwen chat
                    # template is in answer-only mode.  This branch is tightly
                    # scoped to that request shape, so a real private CoT from
                    # another provider can never leak into the UI.
                    text = message.get("reasoning_content", "") if cloudflare_thinking_disabled else ""
                text = self._clean_text(str(text))
                if not text or text.lower() == "none":
                    return LLMResult(False, "", "provider", effective_provider, effective_model, "empty_response", latency_ms, image_attached)
                raw_usage = payload.get("usage")
                usage = {
                    str(key): int(value)
                    for key, value in raw_usage.items()
                    if key in {"prompt_tokens", "completion_tokens", "total_tokens"} and isinstance(value, (int, float))
                } if isinstance(raw_usage, dict) else {}
                return LLMResult(True, text, "provider", effective_provider, effective_model, None, latency_ms, image_attached, usage)
            return LLMResult(False, "", "provider", effective_provider, effective_model, last_error, image_attached=image_attached)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:240]
            return LLMResult(False, "", "provider", effective_provider, effective_model, f"http_{exc.code}: {detail}", image_attached=image_attached)
        except Exception as exc:
            error = str(exc) if str(exc) == "unsafe_base_url" else type(exc).__name__
            return LLMResult(False, "", "provider", effective_provider, effective_model, error, image_attached=image_attached)

    def _chat_completion_endpoints(self, base_url: str) -> list[str]:
        cleaned = self._normalize_base_url(base_url)
        if not cleaned:
            return []
        try:
            parsed = urllib.parse.urlsplit(cleaned)
        except ValueError as exc:
            raise ValueError("unsafe_base_url") from exc
        self._validate_base_url(parsed)
        parsed = parsed._replace(query="", fragment="")
        path = parsed.path.rstrip("/")
        if path.endswith("/chat/completions"):
            return [urllib.parse.urlunsplit(parsed)]
        candidates = [self._replace_url_path(parsed, f"{path}/chat/completions")]
        if not path.endswith("/v1"):
            candidates.insert(0, self._replace_url_path(parsed, f"{path}/v1/chat/completions"))
        deduped: list[str] = []
        for candidate in candidates:
            if candidate not in deduped:
                deduped.append(candidate)
        return deduped

    def _normalize_base_url(self, base_url: str) -> str:
        cleaned = base_url.strip().rstrip("/")
        if cleaned and "://" not in cleaned:
            if cleaned.startswith(("localhost", "127.", "[::1]")):
                return f"http://{cleaned}"
            return f"https://{cleaned}"
        return cleaned

    def _validate_base_url(self, parsed: urllib.parse.SplitResult) -> None:
        reason = self._base_url_block_reason(parsed)
        if reason:
            raise ValueError("unsafe_base_url")

    def _base_url_block_reason(self, parsed: urllib.parse.SplitResult) -> str | None:
        scheme = parsed.scheme.lower()
        try:
            hostname = self._canonical_hostname(parsed.hostname or "")
            port = parsed.port
        except ValueError:
            return "invalid_port"
        if scheme not in {"https", "http"} or not parsed.netloc or not hostname:
            return "invalid_url"
        if port == 0:
            return "invalid_port"
        if parsed.username or parsed.password:
            return "credentials_in_url"
        if self._is_metadata_host(hostname):
            return "metadata_host_blocked"
        is_loopback = self._is_loopback_host(hostname)
        if is_loopback and port is None:
            return "loopback_port_required"
        if is_loopback and port is not None and port < 1024:
            return "loopback_port_blocked"
        if scheme == "http" and not is_loopback and not self._private_host_allowed(hostname):
            return "non_loopback_http_blocked"
        if not is_loopback and self._is_blocked_ip_literal(hostname) and not self._private_host_allowed(hostname):
            return "private_or_reserved_ip_blocked"
        if not is_loopback:
            resolution = self._resolution_safety(hostname, port)
            if resolution == "blocked":
                return "resolves_to_private_or_reserved_ip"
            if resolution == "private_allowlisted" and not self._private_host_allowed(hostname):
                if not self._is_synthetic_public_provider_resolution(hostname, port):
                    return "resolves_to_private_or_reserved_ip"
        return None

    def _is_synthetic_public_provider_resolution(self, hostname: str, port: int | None) -> bool:
        """Return true only for the known-provider RFC 2544 DNS mapping."""

        if self._canonical_hostname(hostname) not in self._PUBLIC_PROVIDER_HOSTS:
            return False
        try:
            resolved = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return False
        addresses = []
        for item in resolved:
            sockaddr = item[4]
            if sockaddr:
                try:
                    addresses.append(ipaddress.ip_address(sockaddr[0]))
                except ValueError:
                    return False
        return bool(addresses) and all(
            ipaddress.ip_address("198.18.0.0") <= address <= ipaddress.ip_address("198.19.255.255")
            for address in addresses
        )

    def _safe_preflight_preview(self, parsed: urllib.parse.SplitResult, source: str) -> str:
        path = parsed.path.rstrip("/")
        if source == "backend_env":
            return f"backend .env configured · path={path or '/'}"
        hostname = self._parsed_hostname(parsed)
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        try:
            port = parsed.port
        except ValueError:
            port = None
        netloc = f"{hostname}:{port}" if port else hostname
        sanitized = parsed._replace(netloc=netloc, query="", fragment="")
        return urllib.parse.urlunsplit(sanitized).rstrip("/")

    def _preflight_next_actions(self, reason: str) -> list[str]:
        reason_actions = {
            "invalid_url": "填写完整域名，例如 https://provider.example.com/v1；本机调试可用 http://127.0.0.1:端口。",
            "invalid_port": "端口号不合法；请填写 1-65535 范围内的端口，或去掉端口。",
            "credentials_in_url": "不要把用户名、密码或 token 放进 URL；key 只填入 API Key 输入框或后端 .env。",
            "metadata_host_blocked": "metadata 地址会被拒绝，避免云主机凭据泄露。",
            "non_loopback_http_blocked": "非本机 http 会被拒绝；外部 Provider 请使用 https。",
            "private_or_reserved_ip_blocked": "内网、链路本地、保留或组播 IP 会被拒绝；请使用公开 https Provider 或本机 loopback。",
            "resolves_to_private_or_reserved_ip": "该域名解析到内网/保留地址，默认会被拒绝；如这是你控制的私有 Provider 代理，请只在后端 .env 配置 LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST 精确放行该 host 并重启后端。",
            "missing_base_url": "填写临时 API Base，或在后端 .env 配置 LLM_BASE_URL。",
            "loopback_port_required": "本机调试地址必须显式填写端口，例如 http://127.0.0.1:8001/v1。",
            "loopback_port_blocked": "本机调试端口过低，可能指向系统服务；请使用明确的开发端口。",
        }
        return [
            reason_actions.get(reason, "检查 API Base 是否为安全的 OpenAI-compatible HTTPS endpoint。"),
            "预检通过后再填写临时 key 或后端 .env key，运行文本轻量自检。",
            "自检通过后再运行视觉通道自检和公开样例级准入。",
        ]

    def _is_loopback_host(self, hostname: str) -> bool:
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
            return True
        try:
            return ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            return False

    def _is_blocked_ip_literal(self, hostname: str) -> bool:
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return False
        return bool(
            address.is_private
            or address.is_link_local
            or address.is_unspecified
            or address.is_reserved
            or address.is_multicast
        )

    def _is_metadata_host(self, hostname: str) -> bool:
        if hostname in {"metadata", "metadata.google.internal"} or hostname.endswith(".metadata.google.internal"):
            return True
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return False
        return str(address) in {"169.254.169.254", "100.100.100.200", "fd00:ec2::254"}

    def _resolution_safety(self, hostname: str, port: int | None) -> str:
        try:
            resolved = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return "public"
        found_private_or_reserved = False
        for item in resolved:
            sockaddr = item[4]
            if not sockaddr:
                continue
            try:
                address = ipaddress.ip_address(sockaddr[0])
            except ValueError:
                continue
            if self._is_metadata_address(address):
                return "blocked"
            if address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast:
                return "blocked"
            if address.is_private or address.is_reserved:
                found_private_or_reserved = True
        return "private_allowlisted" if found_private_or_reserved else "public"

    def _resolves_to_blocked_address(self, hostname: str, port: int | None) -> bool:
        return self._resolution_safety(hostname, port) != "public"

    def _parsed_hostname(self, parsed: urllib.parse.SplitResult) -> str:
        try:
            return self._canonical_hostname(parsed.hostname or "")
        except ValueError:
            return ""

    def _resolve_connection_host(self, hostname: str, port: int) -> str:
        canonical_hostname = self._canonical_hostname(hostname)
        try:
            resolved = socket.getaddrinfo(canonical_hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("unsafe_base_url") from exc
        is_loopback = self._is_loopback_host(canonical_hostname)
        private_allowed = self._private_host_allowed(canonical_hostname)
        for item in resolved:
            sockaddr = item[4]
            if not sockaddr:
                continue
            candidate = sockaddr[0]
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if is_loopback and address.is_loopback:
                return candidate
            if self._is_metadata_address(address):
                continue
            if private_allowed and self._is_allowlisted_private_address(address):
                return candidate
            if not is_loopback and not (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_unspecified
                or address.is_reserved
                or address.is_multicast
            ):
                return candidate
        raise ValueError("unsafe_base_url")

    def _canonical_hostname(self, hostname: str) -> str:
        return hostname.strip().strip("[]").lower().rstrip(".")

    def _private_host_allowed(self, hostname: str) -> bool:
        canonical = self._canonical_hostname(hostname)
        if not canonical or self._is_loopback_host(canonical) or self._is_metadata_host(canonical):
            return False
        try:
            ipaddress.ip_address(canonical)
            return config.LLM_PROVIDER_ALLOW_PRIVATE_NETWORK and self._is_allowlisted_private_address(ipaddress.ip_address(canonical))
        except ValueError:
            return canonical in config.LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST or canonical in self._local_demo_provider_hosts()

    def _is_allowlisted_private_address(self, address: ipaddress._BaseAddress) -> bool:
        if self._is_metadata_address(address):
            return False
        if address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast:
            return False
        return bool(address.is_private or address.is_reserved)

    def _is_metadata_address(self, address: ipaddress._BaseAddress) -> bool:
        return str(address) in {"169.254.169.254", "100.100.100.200", "fd00:ec2::254"}

    def _host_uses_private_allowlist(self, parsed: urllib.parse.SplitResult) -> bool:
        hostname = self._parsed_hostname(parsed)
        if not self._private_host_allowed(hostname):
            return False
        try:
            port = parsed.port
        except ValueError:
            return False
        return self._resolution_safety(hostname, port) == "private_allowlisted"

    def _replace_url_path(self, parsed: urllib.parse.SplitResult, path: str) -> str:
        normalized_path = "/" + path.strip("/")
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))

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
        if image_path.startswith("eval://endobench/"):
            relative = image_path.removeprefix("eval://endobench/")
            try:
                from app.services.data_governance import resolve_local_asset

                return resolve_local_asset("endobench", f"EndoBench-Images/{relative}")
            except (ValueError, FileNotFoundError):
                return None
        return None

    def _clean_text(self, text: str) -> str:
        cleaned = text.strip()
        return cleaned[:4000]


llm_provider = LLMProvider()
