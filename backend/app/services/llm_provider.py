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

    def preflight(self, base_url: str | None = None) -> dict[str, Any]:
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
                "key_required_for_call": True,
                "request_sent": False,
                "key_persisted": False,
            }

        endpoints = self._chat_completion_endpoints(normalized)
        endpoint_paths = [urllib.parse.urlsplit(endpoint).path for endpoint in endpoints]
        if parsed.scheme.lower() == "http":
            warnings.append("http 仅允许 localhost/127.0.0.1/[::1] 等本机调试地址。")
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
            "key_required_for_call": True,
            "request_sent": False,
            "key_persisted": False,
        }

    def _request_json(self, endpoint: str, body: dict[str, Any], api_key: str) -> tuple[int, bytes]:
        parsed = urllib.parse.urlsplit(endpoint)
        self._validate_base_url(parsed)
        hostname = self._parsed_hostname(parsed)
        if not hostname:
            raise ValueError("unsafe_base_url")
        scheme = parsed.scheme.lower()
        port = parsed.port or (443 if scheme == "https" else 80)
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
    ) -> LLMResult:
        effective_provider = provider or config.LLM_PROVIDER
        effective_base_url = self._normalize_base_url(base_url if base_url is not None else config.LLM_BASE_URL)
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
                text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
                text = self._clean_text(str(text))
                if not text:
                    return LLMResult(False, "", "provider", effective_provider, effective_model, "empty_response", latency_ms, image_attached)
                return LLMResult(True, text, "provider", effective_provider, effective_model, None, latency_ms, image_attached)
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
            hostname = (parsed.hostname or "").lower()
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
        if scheme == "http" and not is_loopback:
            return "non_loopback_http_blocked"
        if not is_loopback and self._is_blocked_ip_literal(hostname):
            return "private_or_reserved_ip_blocked"
        if not is_loopback and self._resolves_to_blocked_address(hostname, port):
            return "resolves_to_private_or_reserved_ip"
        return None

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
            "resolves_to_private_or_reserved_ip": "该域名解析到内网/保留地址，后端会拒绝；请检查 DNS 或改用公开 Provider endpoint。",
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

    def _resolves_to_blocked_address(self, hostname: str, port: int | None) -> bool:
        try:
            resolved = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return False
        for item in resolved:
            sockaddr = item[4]
            if not sockaddr:
                continue
            try:
                address = ipaddress.ip_address(sockaddr[0])
            except ValueError:
                continue
            if (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_unspecified
                or address.is_reserved
                or address.is_multicast
            ):
                return True
        return False

    def _parsed_hostname(self, parsed: urllib.parse.SplitResult) -> str:
        try:
            return (parsed.hostname or "").lower()
        except ValueError:
            return ""

    def _resolve_connection_host(self, hostname: str, port: int) -> str:
        try:
            resolved = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("unsafe_base_url") from exc
        is_loopback = self._is_loopback_host(hostname)
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
        return None

    def _clean_text(self, text: str) -> str:
        cleaned = text.strip()
        return cleaned[:4000]


llm_provider = LLMProvider()
