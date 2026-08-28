"""Small, permissioned Tutor v1 runtime; intentionally not a general agent framework."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any, Literal, Protocol
from uuid import uuid4

from app.core.config import SAFETY_NOTICE
from app.core import config
from app.services.llm_provider import llm_provider
from app.services.stage1_service import stage1_service


AgentEventType = Literal['message_start', 'token', 'tool_start', 'tool_end', 'source', 'message_end', 'error']


@dataclass(frozen=True)
class AgentEvent:
    event: AgentEventType
    data: dict[str, Any]


@dataclass(frozen=True)
class ToolReceipt:
    tool_name: str
    elapsed_ms: int
    status: Literal['ok', 'denied', 'error']
    summary: str


@dataclass
class AgentContext:
    question_id: str
    learner_id: str
    user_message: str
    phase: Literal['pre_submit', 'post_submit']
    attempt_id: str | None = None
    cancelled: Callable[[], bool] = lambda: False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    run_id: str
    text: str
    receipts: list[ToolReceipt]
    sources: list[dict[str, str]]
    provider: str
    retry_count: int
    completed: bool


class ModelGateway(Protocol):
    name: str

    def select_tools(self, context: AgentContext, available_tools: set[str]) -> list[str]: ...

    def compose(self, context: AgentContext, observations: dict[str, Any]) -> str: ...


class LocalPolicyModelGateway:
    """No-secret development adapter. It is never presented as an external model run."""

    name = 'local-policy-adapter/external-provider-pending'

    def select_tools(self, context: AgentContext, available_tools: set[str]) -> list[str]:
        requested = ['get_question_context', 'retrieve_knowledge', 'get_learning_profile']
        if context.phase == 'post_submit' and 'get_grading_result' in available_tools:
            requested.append('get_grading_result')
        return [tool for tool in requested if tool in available_tools]

    def compose(self, context: AgentContext, observations: dict[str, Any]) -> str:
        lowered = context.user_message.lower()
        if context.phase == 'pre_submit' and any(marker in lowered for marker in ('正确答案', 'standard answer', 'hidden rubric', '忽略规则', '服务器标准答案')):
            return '提交前我只能协助你观察证据、定位资料和规划学习；不会读取或透露标准答案、隐藏 rubric 或评分目标。请先描述可见的部位、形态和支持事实。'
        question = observations.get('get_question_context', {})
        profile = observations.get('get_learning_profile', {})
        retrieval = observations.get('retrieve_knowledge', [])
        history = context.metadata.get('conversation', [])
        continuation = '继续沿用上一步的证据范围。' if history and any(str(item.get('content', '')).strip() for item in history[-2:]) else ''
        prefix = f"先围绕「{question.get('title', '当前题目')}」梳理可见证据：{continuation}"
        evidence = '、'.join(item.get('snippet', '') for item in retrieval[:2] if item.get('snippet'))
        plan = f"建议先区分部位、形态和不能由单帧推出的结论。{evidence}" if evidence else '建议先区分部位、形态和不能由单帧推出的结论。'
        if context.phase == 'post_submit':
            grading = observations.get('get_grading_result', {})
            plan += f" 本次得分为 {grading.get('score', '—')}；请以公开反馈复盘，而不是反向索取答案键。"
        return f"{prefix}{plan} 当前已记录练习 {profile.get('attempt_count', 0)} 次。{SAFETY_NOTICE}"


class OpenAICompatibleTutorGateway:
    """Opt-in provider gateway; no request is made unless explicitly enabled.

    The gateway receives only the already permission-filtered tool names and
    observations. It deliberately never asks a model to reveal reasoning or
    select a data-write tool.
    """

    name = "openai-compatible-tutor"

    def select_tools(self, context: AgentContext, available_tools: set[str]) -> list[str]:
        result = llm_provider.chat(
            system_prompt=(
                "You are a medical education tutor tool planner. Return JSON only: "
                '{"tools":[...]} . Select only names in the allowed list. '
                "Never request answers, hidden rubrics, diagnosis, or write actions."
            ),
            user_prompt=json.dumps({"user_message": context.user_message, "phase": context.phase, "allowed_tools": sorted(available_tools)}, ensure_ascii=False),
            temperature=0,
            max_tokens=120,
        )
        if not result.ok:
            raise RuntimeError(result.error or "provider_tool_planning_failed")
        try:
            names = json.loads(result.text).get("tools", [])
        except (json.JSONDecodeError, AttributeError) as exc:
            raise RuntimeError("provider_tool_plan_not_json") from exc
        return [str(name) for name in names if str(name) in available_tools]

    def compose(self, context: AgentContext, observations: dict[str, Any]) -> str:
        result = llm_provider.chat(
            system_prompt=(
                "You are a safe Chinese medical education tutor. Use only supplied observations. "
                "Before submission never reveal answers, correct option IDs, reference answers, hidden rubrics, or benchmark targets. "
                "Do not provide diagnosis or treatment. Give a concise evidence-based teaching reply, cite source labels when supplied, "
                f"and include this boundary: {SAFETY_NOTICE} Do not reveal hidden reasoning."
            ),
            user_prompt=json.dumps({"user_message": context.user_message, "phase": context.phase, "observations": observations, "recent_conversation": context.metadata.get("conversation", [])[-12:]}, ensure_ascii=False),
            temperature=0.2,
            max_tokens=420,
        )
        if not result.ok:
            raise RuntimeError(result.error or "provider_compose_failed")
        return result.text


ToolHandler = Callable[[AgentContext], Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[set[str], ToolHandler]] = {}

    def register(self, name: str, phases: set[str], handler: ToolHandler) -> None:
        self._tools[name] = (phases, handler)

    def allowed(self, phase: str) -> set[str]:
        return {name for name, (phases, _) in self._tools.items() if phase in phases}

    def call(self, name: str, context: AgentContext) -> tuple[Any, ToolReceipt]:
        phases, handler = self._tools[name]
        if context.phase not in phases:
            return {}, ToolReceipt(name, 0, 'denied', '该工具不在当前提交阶段的权限范围内。')
        started = perf_counter()
        try:
            value = handler(context)
            return value, ToolReceipt(name, round((perf_counter() - started) * 1000), 'ok', '已取得允许的观察数据。')
        except Exception as exc:  # converted to a typed receipt; never exposed as chain-of-thought
            return {}, ToolReceipt(name, round((perf_counter() - started) * 1000), 'error', f'工具暂不可用：{type(exc).__name__}')


class AgentRunner:
    def __init__(self, registry: ToolRegistry, gateway: ModelGateway | None = None, *, max_steps: int = 4, timeout_seconds: float = 15.0, retries: int = 1) -> None:
        self.registry = registry
        self.gateway = gateway or LocalPolicyModelGateway()
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    def stream(self, context: AgentContext) -> Iterator[AgentEvent]:
        run_id = f'run_{uuid4().hex[:12]}'
        yield AgentEvent('message_start', {'run_id': run_id, 'provider': self.gateway.name, 'phase': context.phase})
        started = perf_counter()
        observations: dict[str, Any] = {}
        receipts: list[ToolReceipt] = []
        try:
            available = self.registry.allowed(context.phase)
            retry_count = 0
            while True:
                try:
                    selected = self.gateway.select_tools(context, available)[: self.max_steps]
                    break
                except Exception as exc:
                    if retry_count >= self.retries:
                        yield AgentEvent('error', {'code': 'gateway_failure', 'message': f'模型网关不可用：{type(exc).__name__}。请重试。'})
                        return
                    retry_count += 1
            for tool_name in selected:
                if context.cancelled():
                    yield AgentEvent('error', {'code': 'cancelled', 'message': '请求已取消。'})
                    return
                if perf_counter() - started > self.timeout_seconds:
                    yield AgentEvent('error', {'code': 'timeout', 'message': 'Tutor 响应超时，可重试。'})
                    return
                yield AgentEvent('tool_start', {'tool_name': tool_name})
                observation, receipt = self.registry.call(tool_name, context)
                observations[tool_name] = observation
                receipts.append(receipt)
                yield AgentEvent('tool_end', {'tool_name': tool_name, **asdict(receipt)})
                if tool_name == 'retrieve_knowledge':
                    for source in observation:
                        yield AgentEvent('source', source)
            text = self.gateway.compose(context, observations)
            for token in _tokenize(text):
                yield AgentEvent('token', {'text': token})
            yield AgentEvent('message_end', {'run_id': run_id, 'receipt_count': len(receipts), 'provider': self.gateway.name, 'retry_count': retry_count})
        except Exception as exc:
            yield AgentEvent('error', {'code': 'agent_failure', 'message': f'Tutor 暂不可用：{type(exc).__name__}。请重试。'})


def _tokenize(text: str) -> list[str]:
    return [text[index:index + 18] for index in range(0, len(text), 18)]


def build_tutor_runtime() -> AgentRunner:
    registry = ToolRegistry()

    def question_context(context: AgentContext) -> dict[str, Any]:
        # Public projection is deliberate: grading payload is never passed to the Tutor pre-submit.
        return stage1_service.public_question(context.question_id)

    def retrieve_knowledge(context: AgentContext) -> list[dict[str, str]]:
        question = stage1_service.public_question(context.question_id)
        query = f"{question.get('body_part', '')} {question.get('stem', '')} {context.user_message}"
        try:
            from app.services.rag_service import rag_service
            citations = rag_service.retrieve(query, mode='hybrid', limit=3)
        except Exception:
            # Honest local fallback: this is never emitted as a verified RAG
            # source and keeps the Tutor usable before the optional index starts.
            citations = []
        if citations:
            return [{
                'chunk_id': citation.chunk_id, 'document_name': citation.document_name,
                'page': str(citation.page), 'section': citation.section, 'snippet': citation.snippet,
            } for citation in citations]
        return [{
            'document_name': str(question.get('source_dataset', '教学资料')), 'page': '教学样例（index 未就绪）',
            'section': str(question.get('body_part', '观察要点')), 'snippet': str(question.get('citation_note', '先检查可支持的观察事实。')),
        }]

    def learning_profile(context: AgentContext) -> dict[str, Any]:
        overview = stage1_service.overview(context.learner_id)
        return {'attempt_count': overview['completed_today'], 'due_review_count': overview['due_review_count'], 'weak_areas': overview['weak_areas']}

    def grading_result(context: AgentContext) -> dict[str, Any]:
        if not context.attempt_id:
            raise ValueError('attempt_id required post submit')
        from app.db.database import SessionLocal
        from app.db.models import AttemptModel

        with SessionLocal() as session:
            attempt = session.get(AttemptModel, context.attempt_id)
            if not attempt or attempt.learner_id != context.learner_id:
                raise ValueError('attempt not found')
            return {'score': attempt.score, 'correct': attempt.correct, 'error_tags': attempt.error_tags}

    registry.register('get_question_context', {'pre_submit', 'post_submit'}, question_context)
    registry.register('retrieve_knowledge', {'pre_submit', 'post_submit'}, retrieve_knowledge)
    registry.register('get_learning_profile', {'pre_submit', 'post_submit'}, learning_profile)
    registry.register('get_grading_result', {'post_submit'}, grading_result)
    # This explicit opt-in protects local test/demo runs from accidental paid
    # provider calls. The default adapter remains visibly labelled as local.
    provider_enabled = os.getenv('TUTOR_PROVIDER_ENABLED', '').strip().lower() == 'true'
    gateway: ModelGateway
    if provider_enabled and config.LLM_BASE_URL and config.LLM_API_KEY:
        gateway = OpenAICompatibleTutorGateway()
    else:
        gateway = LocalPolicyModelGateway()
    return AgentRunner(registry, gateway=gateway)


tutor_runner = build_tutor_runtime()
