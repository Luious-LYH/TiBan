from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.llm_provider import llm_provider
from app.services.rag_service import rag_service
from app.services.runtime_settings_service import runtime_settings_service


router = APIRouter(prefix="/api/v3/settings", tags=["instance-runtime-settings"])


class LLMSettingsRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    base_url: str = Field(min_length=1, max_length=512)
    model: str = Field(min_length=1, max_length=160)
    api_key: str | None = Field(default=None, max_length=512)
    reasoning_effort: str | None = Field(default=None, max_length=32)


class LLMConnectionTestRequest(BaseModel):
    """Optional replacement values for an instance connection test.

    Leaving a value blank deliberately means "test the active server setting".
    That lets an operator verify the configured service without echoing a
    private endpoint or asking them to re-enter an existing secret.
    """

    provider: str | None = Field(default=None, min_length=1, max_length=64)
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    model: str | None = Field(default=None, min_length=1, max_length=160)
    api_key: str | None = Field(default=None, max_length=512)


class EmbeddingSettingsRequest(BaseModel):
    batch_size: int = Field(ge=1, le=64)
    mode: str = Field(default="api", pattern="^(api|local)$")
    provider: str = Field(default="siliconflow", min_length=1, max_length=80)
    base_url: str = Field(default="", max_length=512)
    api_key: str | None = Field(default=None, max_length=512)
    model: str = Field(default="BAAI/bge-m3", min_length=1, max_length=180)
    local_model: str = Field(default="BAAI/bge-small-zh-v1.5", min_length=1, max_length=180)
    reranker_mode: str = Field(default="api", pattern="^(api|local)$")
    reranker_provider: str = Field(default="siliconflow", min_length=1, max_length=80)
    reranker_base_url: str = Field(default="", max_length=512)
    reranker_api_key: str | None = Field(default=None, max_length=512)
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3", min_length=1, max_length=180)


class EmbeddingConnectionTestRequest(BaseModel):
    mode: str | None = Field(default=None, pattern="^(api|local)$")
    provider: str | None = Field(default=None, min_length=1, max_length=80)
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=512)
    model: str | None = Field(default=None, min_length=1, max_length=180)
    local_model: str | None = Field(default=None, min_length=1, max_length=180)


class LLMSettingsPublic(BaseModel):
    provider: str
    base_url_configured: bool
    api_key_configured: bool
    agent_available: bool
    agent_mode: str
    model: str
    reasoning_effort: str | None = None
    runtime_override: bool
    restores_default_on_restart: bool
    private_network_allowed: bool


class EmbeddingSettingsPublic(BaseModel):
    mode: str
    provider: str
    base_url_configured: bool
    api_key_configured: bool
    model: str
    local_model: str
    active_provider: str
    active_model: str
    reranker_mode: str
    reranker_provider: str
    reranker_model: str
    batch_size: int
    runtime_override: bool
    restores_default_on_restart: bool
    model_switch_supported: bool
    knowledge_index_status: str
    memory_index_status: str


class SettingsResponse(BaseModel):
    llm: LLMSettingsPublic
    embedding: EmbeddingSettingsPublic
    api_source: str


class LLMActionResponse(BaseModel):
    llm: LLMSettingsPublic
    api_source: str


class EmbeddingActionResponse(BaseModel):
    embedding: EmbeddingSettingsPublic
    api_source: str


class LLMTestResponse(BaseModel):
    ok: bool
    message: str
    model: str | None = None
    latency_ms: int | None = None
    error: str | None = None
    api_source: str


class EmbeddingTestResponse(BaseModel):
    ok: bool
    message: str | None = None
    result: dict[str, object] | None = None
    api_source: str


class IndexRebuildResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    api_source: str


@router.get("", response_model=SettingsResponse)
def get_settings() -> dict[str, object]:
    return {"llm": runtime_settings_service.llm_public(), "embedding": runtime_settings_service.embedding_public(), "api_source": "backend"}


@router.post("/llm/test", response_model=LLMTestResponse)
def test_llm(request: LLMConnectionTestRequest) -> dict[str, object]:
    from app.core import config

    runtime_settings_service.sync()
    base_url = (request.base_url or config.LLM_BASE_URL).strip()
    provider = (request.provider or config.LLM_PROVIDER).strip()
    model = (request.model or config.LLM_MODEL).strip()
    api_key = request.api_key or config.LLM_API_KEY
    preflight = llm_provider.preflight(base_url)
    if not preflight.get("ok"):
        return {"ok": False, "message": "连接地址不符合当前实例的安全策略。", "api_source": "backend"}
    result = llm_provider.chat(
        system_prompt="你是连接测试助手。只回复“连接成功”。",
        user_prompt="请完成一次最小文本连接测试。",
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        max_tokens=16,
        temperature=0,
        allow_fallback=False,
    )
    return {"ok": result.ok, "message": "连接成功" if result.ok else "模型服务未返回有效响应。", "model": result.model, "latency_ms": result.latency_ms, "error": result.error if not result.ok else None, "api_source": "backend"}


@router.post("/llm/apply", response_model=LLMActionResponse)
def apply_llm(request: LLMSettingsRequest) -> dict[str, object]:
    preflight = llm_provider.preflight(request.base_url)
    if not preflight.get("ok"):
        raise HTTPException(422, "连接地址不符合当前实例的安全策略。")
    try:
        llm = runtime_settings_service.apply_llm(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"llm": llm, "api_source": "backend"}


@router.post("/llm/restore", response_model=LLMActionResponse)
def restore_llm() -> dict[str, object]:
    return {"llm": runtime_settings_service.restore_llm(), "api_source": "backend"}


@router.post("/embedding/test", response_model=EmbeddingTestResponse)
def test_embedding(request: EmbeddingConnectionTestRequest) -> dict[str, object]:
    try:
        result = runtime_settings_service.test_embedding_config(**request.model_dump())
        return {"ok": True, "result": result, "api_source": "backend"}
    except Exception as exc:
        return {"ok": False, "message": "Embedding 服务暂不可用，请检查当前实例配置与网络。", "result": {"error_type": type(exc).__name__}, "api_source": "backend"}


@router.post("/embedding/apply", response_model=EmbeddingActionResponse)
def apply_embedding(request: EmbeddingSettingsRequest) -> dict[str, object]:
    try:
        embedding = runtime_settings_service.apply_embedding(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"embedding": embedding, "api_source": "backend"}


@router.post("/embedding/restore", response_model=EmbeddingActionResponse)
def restore_embedding() -> dict[str, object]:
    return {"embedding": runtime_settings_service.restore_embedding(), "api_source": "backend"}


@router.post('/indexes/rebuild', response_model=IndexRebuildResponse)
def rebuild_indexes() -> dict[str, object]:
    try:
        result = runtime_settings_service.enqueue_index_rebuild()
        return {**result, 'api_source': 'backend'}
    except Exception as exc:
        raise HTTPException(503, '无法创建索引重建任务。') from exc
