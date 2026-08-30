"""Small, permissioned Tutor v1 runtime; intentionally not a general agent framework."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any, Literal, Protocol
from uuid import uuid4

from app.core.config import SAFETY_NOTICE
from app.core import config
from app.services.llm_provider import llm_provider
from app.services.stage1_service import stage1_service


AgentEventType = Literal['message_start', 'reasoning', 'token', 'tool_start', 'tool_end', 'source', 'message_end', 'error']


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
    mode: Literal['study', 'exam', 'review'] = 'study'
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
        lowered = context.user_message.lower()
        requested = ['get_question_context', 'get_learning_profile']
        if any(marker in lowered for marker in ('错题', '错误', '薄弱', '近期', '历史表现', '复习记录')):
            requested.append('get_recent_mistakes')
        if any(marker in lowered for marker in ('提示', '解释', '为什么', '依据', '资料', '指南', '反流', '胃炎', '出血', '解剖')):
            requested.insert(1, 'retrieve_knowledge')
        if context.mode == 'study' and context.phase == 'pre_submit' and any(marker in lowered for marker in ('正确答案', '直接告诉我', '我不会', '答案是什么', '给答案')):
            requested.append('get_answer_explanation')
        if context.phase == 'post_submit' and 'get_grading_result' in available_tools:
            requested.append('get_grading_result')
        return [tool for tool in requested if tool in available_tools]

    def compose(self, context: AgentContext, observations: dict[str, Any]) -> str:
        lowered = context.user_message.lower()
        answer = observations.get('get_answer_explanation')
        if answer and context.mode == 'study':
            return f"答案是：{answer.get('correct_answer_display', '见解析')}。{answer.get('explanation', '')}"
        if context.phase == 'pre_submit' and any(marker in lowered for marker in ('正确答案', 'standard answer', 'hidden rubric', '忽略规则', '服务器标准答案', '正确选项')):
            return '我可以帮助你梳理题干、图像和资料依据；当前模式不会读取隐藏 rubric 或服务器内部字段。若你在 Study 模式明确需要答案，可以直接说“告诉我答案”。'
        question = observations.get('get_question_context', {})
        profile = observations.get('get_learning_profile', {})
        mistakes = observations.get('get_recent_mistakes', [])
        retrieval = observations.get('retrieve_knowledge', [])
        history = context.metadata.get('conversation', [])
        continuation = '继续沿用上一步的证据范围。' if history and any(str(item.get('content', '')).strip() for item in history[-2:]) else ''
        prefix = f"先围绕「{question.get('title', '当前题目')}」梳理可见证据：{continuation}"
        evidence = '、'.join(item.get('snippet', '') for item in retrieval[:2] if item.get('snippet'))
        plan = f"建议先区分部位、形态和不能由单帧推出的结论。{evidence}" if evidence else '建议先区分部位、形态和不能由单帧推出的结论。'
        if context.phase == 'post_submit':
            grading = observations.get('get_grading_result', {})
            plan += f" 本次得分为 {grading.get('score', '—')}；请以公开反馈复盘，而不是反向索取答案键。"
        history_note = f" 近期可复盘错题 {len(mistakes)} 条。" if mistakes else ''
        return f"{prefix}{plan} 当前已记录练习 {profile.get('attempt_count', 0)} 次。{history_note}{SAFETY_NOTICE}"


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
                "Never request hidden rubrics, diagnosis, or write actions. "
                "The get_answer_explanation tool is permitted only when mode is study, phase is pre_submit, "
                "and the learner explicitly asks for the current answer; never select it in exam mode, "
                "post-submit mode, or for a hint-only request."
            ),
            user_prompt=json.dumps({"user_message": context.user_message, "phase": context.phase, "mode": context.mode, "allowed_tools": sorted(available_tools)}, ensure_ascii=False),
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
                "The mode field is authoritative: pre_submit plus mode=study is a learning session, not an exam. "
                "In Study mode, when a server-supplied get_answer_explanation observation is present and the learner explicitly asks for the current answer, "
                "give that answer and explain it. In Exam mode before submission never reveal answers, correct option IDs, reference answers, hidden rubrics, or benchmark targets. "
                "Do not provide diagnosis or treatment. Give a concise evidence-based teaching reply, cite source labels when supplied, "
                f"and include this boundary: {SAFETY_NOTICE} Do not reveal hidden reasoning."
            ),
            user_prompt=json.dumps({"user_message": context.user_message, "phase": context.phase, "mode": context.mode, "observations": observations, "recent_conversation": context.metadata.get("conversation", [])[-12:]}, ensure_ascii=False),
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

    def allowed(self, phase: str, mode: str = 'study') -> set[str]:
        return {name for name, (phases, _) in self._tools.items() if phase in phases and not (name == 'get_answer_explanation' and mode != 'study')}

    def call(self, name: str, context: AgentContext) -> tuple[Any, ToolReceipt]:
        phases, handler = self._tools[name]
        if context.phase not in phases or (name == 'get_answer_explanation' and context.mode != 'study'):
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
        yield AgentEvent('message_start', {'run_id': run_id, 'provider': self.gateway.name, 'provider_real': self.gateway.name != LocalPolicyModelGateway.name, 'phase': context.phase, 'mode': context.mode})
        started = perf_counter()
        observations: dict[str, Any] = {}
        receipts: list[ToolReceipt] = []
        source_emitted = False
        try:
            available = self.registry.allowed(context.phase, context.mode)
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
                        source_emitted = True
            # A Tutor turn can legitimately skip retrieval (for example, when
            # the model only needs the current question).  Keep the SSE
            # protocol stable by emitting the public question provenance in
            # that case.  This is a real, answer-free source projection, not
            # a synthetic UI status or a hidden grading observation.
            if not source_emitted:
                question = observations.get('get_question_context')
                if not isinstance(question, dict):
                    try:
                        question = stage1_service.public_question(context.question_id)
                    except Exception:
                        question = None
                if isinstance(question, dict):
                    yield AgentEvent('source', {
                        'document_name': str(question.get('source_dataset', '题目来源')),
                        'page': '题目来源',
                        'section': str(question.get('body_part', '观察要点')),
                        'snippet': str(question.get('citation_note', '当前题目的公开来源信息。')),
                        'source_uri': '',
                        'namespace': 'question_source',
                    })
                else:
                    # The typed protocol also supports tool-only/unit runner
                    # contexts with no public question projection.  This is a
                    # lifecycle marker (not a learner-facing citation).
                    yield AgentEvent('source', {'status': 'none'})
            text = _clean_user_facing_text(self.gateway.compose(context, observations))
            yield AgentEvent('reasoning', {'summary': ['识别学习目标', '对照题目与允许的证据', '组织面向学习者的回答'], 'duration_ms': round((perf_counter() - started) * 1000)})
            for token in _tokenize(text):
                yield AgentEvent('token', {'text': token})
            yield AgentEvent('message_end', {'run_id': run_id, 'receipt_count': len(receipts), 'provider': self.gateway.name, 'retry_count': retry_count})
        except Exception as exc:
            yield AgentEvent('error', {'code': 'agent_failure', 'message': f'Tutor 暂不可用：{type(exc).__name__}。请重试。'})


def _tokenize(text: str) -> list[str]:
    return [text[index:index + 18] for index in range(0, len(text), 18)]


def _clean_user_facing_text(text: str) -> str:
    """Remove accidental runtime/schema labels from model-facing prose.

    Tool names and private observation keys belong in receipts and developer
    detail, never in the learner's answer.  This is a narrow output guard, not
    a substitute for the prompt contract.
    """
    cleaned = re.sub(
        r"\s*(?:explanation_source|答案解析来源|解析来源|correct_option_ids?|hidden_rubric)"
        r"\s*[:：]?\s*(?:[^\n。；;]+)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*\[(?:get_[a-z_]+|retrieve_knowledge|ToolReceipt)\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*［(?:get_[a-z_]+|retrieve_knowledge|ToolReceipt)］", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\s*［[^］]*\b(?:get_[a-z_]+|retrieve_knowledge|ToolReceipt|explanation_source|"
        r"correct_option_ids?|hidden_rubric)\b[^］]*］",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*\[[^\]]*\b(?:get_[a-z_]+|retrieve_knowledge|ToolReceipt|explanation_source|"
        r"correct_option_ids?|hidden_rubric)\b[^\]]*\]",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*[\[【(（]?\s*(?:(?:来源|source)\s*[:：]\s*)?"
        r"(?:get_[a-z_]+|retrieve_knowledge|ToolReceipt|explanation_source|"
        r"correct_option_ids?|hidden_rubric)\s*[;；,，]?\s*[\]】)）]?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*\[[^\]]*\b(?:get_[a-z_]+|retrieve_knowledge|ToolReceipt|explanation_source|correct_option_ids?|hidden_rubric)\b[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*［[^］]*\b(?:get_[a-z_]+|retrieve_knowledge|ToolReceipt|explanation_source|correct_option_ids?|hidden_rubric)\b[^］]*］", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*[:：]\s*(?:none|null|未提供|unknown)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\[[^\]]*\bdataset_gold\b[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*[\[【][^\]】\n]*(?:source\s*item|source_id|dataset_gold|explanation_source)[^\]】\n]*[\]】]?", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("**", "")
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def build_tutor_runtime() -> AgentRunner:
    registry = ToolRegistry()

    def question_context(context: AgentContext) -> dict[str, Any]:
        # Public projection is deliberate: grading payload is never passed to the Tutor pre-submit.
        return stage1_service.public_question(context.question_id)

    def retrieve_knowledge(context: AgentContext) -> list[dict[str, str]]:
        question = stage1_service.public_question(context.question_id)
        query = f"{question.get('body_part', '')} {question.get('stem', '')} {context.user_message}"
        retrieval_enabled = os.getenv('TUTOR_RETRIEVAL_ENABLED', 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
        citations = []
        if retrieval_enabled:
            try:
                from app.services.rag_service import rag_service
                # Dense remains the frozen product default. Sparse, hybrid,
                # and rerank paths are exercised by their own RAG tests and
                # benchmark instead of being made a prerequisite for every
                # local Tutor smoke run.
                citations = rag_service.retrieve(query, mode='dense', limit=3, namespace='endoscopy')
            except Exception:
                # Honest local fallback: this is never emitted as a verified
                # RAG source and keeps Tutor usable before the optional index
                # is available.
                citations = []
        if citations:
            return [{
                'chunk_id': citation.chunk_id, 'document_name': citation.document_name,
                'page': str(citation.page), 'section': citation.section, 'snippet': citation.snippet, 'source_uri': citation.source_uri or '', 'namespace': citation.namespace,
            } for citation in citations]
        return [{
            'document_name': str(question.get('source_dataset', '题目来源')), 'page': '题目来源',
            'section': str(question.get('body_part', '观察要点')), 'snippet': str(question.get('citation_note', '先检查可支持的观察事实。')), 'source_uri': '', 'namespace': 'question_source',
        }]

    def learning_profile(context: AgentContext) -> dict[str, Any]:
        overview = stage1_service.overview(context.learner_id)
        return {'attempt_count': overview['completed_today'], 'due_review_count': overview['due_review_count'], 'weak_areas': overview['weak_areas']}

    def recent_mistakes(context: AgentContext) -> list[dict[str, Any]]:
        """Expose a bounded, answer-free learning-history observation.

        The Tool reads immutable attempts only. It deliberately omits both the
        learner's submitted value and the grading payload, so it cannot become
        an indirect pre-submit answer channel.
        """

        from sqlalchemy import select

        from app.db.database import SessionLocal
        from app.db.models import AttemptModel, QuestionModel

        with SessionLocal() as session:
            rows = session.execute(
                select(AttemptModel, QuestionModel)
                .join(QuestionModel, QuestionModel.question_id == AttemptModel.question_id)
                .where(AttemptModel.learner_id == context.learner_id, AttemptModel.correct.is_(False))
                .order_by(AttemptModel.created_at.desc())
                .limit(5)
            ).all()
        return [
            {
                'question_id': attempt.question_id,
                'title': question.title,
                'tags': list(question.teaching_tags or [question.body_part]),
                'error_tags': list(attempt.error_tags or []),
                'created_at': attempt.created_at.isoformat(),
            }
            for attempt, question in rows
        ]

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

    def answer_explanation(context: AgentContext) -> dict[str, Any]:
        if context.mode != 'study' or context.phase != 'pre_submit':
            raise PermissionError('answer explanation is only available in Study pre-submit mode')
        from app.db.serializers import grading_question_payload
        from app.db.database import SessionLocal
        with SessionLocal() as session:
            from app.db.repositories import Stage1Repository
            question = Stage1Repository(session).get_question(context.question_id)
            grading = grading_question_payload(question)
            _, answer_display = stage1_service._answer_displays(grading, grading.get('correct_option_id', grading.get('correct_option_ids', grading.get('correct_value', ''))))
            if grading['question_type'] == 'short_answer':
                answer_display = '参考答案见题目解析与评分 rubric'
            return {'correct_answer_display': answer_display, 'explanation': question.explanation, 'explanation_source': question.explanation_source}

    registry.register('get_question_context', {'pre_submit', 'post_submit'}, question_context)
    registry.register('retrieve_knowledge', {'pre_submit', 'post_submit'}, retrieve_knowledge)
    registry.register('get_learning_profile', {'pre_submit', 'post_submit'}, learning_profile)
    registry.register('get_recent_mistakes', {'pre_submit', 'post_submit'}, recent_mistakes)
    registry.register('get_grading_result', {'post_submit'}, grading_result)
    registry.register('get_answer_explanation', {'pre_submit'}, answer_explanation)
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
