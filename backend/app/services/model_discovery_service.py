"""Safe, request-scoped discovery for OpenAI-compatible model catalogs.

The Evaluation Lab uses this service only to fill the editable candidate-model
draft.  Provider credentials and upstream payloads are deliberately never
persisted, logged, or returned to the browser.
"""

from __future__ import annotations

import http.client
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.core import config
from app.services.llm_provider import (
    _NoRedirectHandler,
    _PinnedHTTPConnection,
    _PinnedHTTPSConnection,
    llm_provider,
)


_VERSION_SEGMENT = re.compile(r"^v\d+$", re.IGNORECASE)
_MAX_RESPONSE_BYTES = 512 * 1024


class ModelDiscoveryService:
    """Discover a small normalized model list without becoming a URL proxy."""

    @staticmethod
    def build_models_url_candidates(base_url: str) -> list[str]:
        normalized = llm_provider._normalize_base_url(base_url)
        try:
            parsed = urllib.parse.urlsplit(normalized)
        except ValueError as exc:
            raise ValueError("Base URL 格式不正确。") from exc
        try:
            llm_provider._validate_base_url(parsed)
        except ValueError as exc:
            raise ValueError("自定义 API 地址不符合当前实例的安全策略。") from exc

        clean = urllib.parse.urlunsplit(parsed._replace(query="", fragment="")).rstrip("/")
        path = parsed.path.rstrip("/")
        if path.endswith("/models"):
            return [clean]
        if path.endswith("/chat/completions"):
            clean = clean.removesuffix("/chat/completions")
            path = urllib.parse.urlsplit(clean).path.rstrip("/")

        last_segment = path.rsplit("/", 1)[-1] if path else ""
        if _VERSION_SEGMENT.fullmatch(last_segment):
            candidates = [f"{clean}/models"]
            if last_segment.lower() != "v1":
                candidates.append(f"{clean}/v1/models")
        else:
            candidates = [f"{clean}/v1/models", f"{clean}/models"]
        return list(dict.fromkeys(candidates))

    @staticmethod
    def _parse_models(payload: object) -> list[dict[str, str | None]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("上游返回的模型列表格式不受支持。")
        seen: set[str] = set()
        models: list[dict[str, str | None]] = []
        for item in payload["data"]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            model_id = item["id"].strip()
            key = model_id.lower()
            if not model_id or key in seen:
                continue
            seen.add(key)
            display_name = item.get("display_name") or item.get("displayName")
            owned_by = item.get("owned_by")
            models.append({
                "id": model_id,
                "display_name": display_name.strip() if isinstance(display_name, str) and display_name.strip() else None,
                "owned_by": owned_by.strip() if isinstance(owned_by, str) and owned_by.strip() else None,
            })
        models.sort(key=lambda item: str(item["id"]).lower())
        return models

    @staticmethod
    def _get(endpoint: str, api_key: str) -> tuple[int, bytes]:
        parsed = urllib.parse.urlsplit(endpoint)
        llm_provider._validate_base_url(parsed)
        hostname = llm_provider._parsed_hostname(parsed)
        if not hostname:
            raise ValueError("unsafe_base_url")
        scheme = parsed.scheme.lower()
        port = parsed.port or (443 if scheme == "https" else 80)
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

        if scheme == "https" and hostname in llm_provider._PUBLIC_PROVIDER_HOSTS:
            request = urllib.request.Request(endpoint, headers=headers, method="GET")
            opener = urllib.request.build_opener(_NoRedirectHandler)
            try:
                with opener.open(request, timeout=min(15, config.LLM_TIMEOUT_SECONDS)) as response:
                    return response.status, response.read(_MAX_RESPONSE_BYTES + 1)
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read(_MAX_RESPONSE_BYTES + 1)

        connect_host = llm_provider._resolve_connection_host(hostname, port)
        path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        connection: http.client.HTTPConnection
        if scheme == "https":
            connection = _PinnedHTTPSConnection(hostname, port, connect_host, min(15, config.LLM_TIMEOUT_SECONDS))
        else:
            connection = _PinnedHTTPConnection(hostname, port, connect_host, min(15, config.LLM_TIMEOUT_SECONDS))
        try:
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            return response.status, response.read(_MAX_RESPONSE_BYTES + 1)
        finally:
            connection.close()

    def discover(self, *, base_url: str, api_key: str, api_format: str = "openai") -> dict[str, Any]:
        if api_format != "openai":
            raise ValueError("当前仅支持 OpenAI-compatible 模型列表接口。")
        key = api_key.strip()
        if not key:
            raise ValueError("请先填写 API Key。")
        endpoints = self.build_models_url_candidates(base_url)
        last_error = "未发现可用的模型列表接口。"
        for endpoint in endpoints:
            started = time.perf_counter()
            try:
                status, body = self._get(endpoint, key)
            except (OSError, socket.timeout, TimeoutError, http.client.HTTPException):
                last_error = "无法连接上游模型服务。"
                continue
            except ValueError:
                raise ValueError("自定义 API 地址不符合当前实例的安全策略。")
            if status in {401, 403}:
                raise ValueError("API Key 鉴权失败。")
            if status in {404, 405}:
                last_error = "上游未提供兼容的模型列表接口。"
                continue
            if status >= 400:
                raise ValueError(f"上游模型列表接口返回 HTTP {status}。")
            if len(body) > _MAX_RESPONSE_BYTES:
                raise ValueError("上游模型列表响应过大。")
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("上游返回的模型列表无法解析。") from exc
            models = self._parse_models(payload)
            if not models:
                raise ValueError("上游未返回可用的模型 ID。")
            return {
                "models": models,
                "latency_ms": round((time.perf_counter() - started) * 1000),
            }
        raise ValueError(last_error)


model_discovery_service = ModelDiscoveryService()
