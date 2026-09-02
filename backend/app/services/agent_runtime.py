"""Small, permissioned Tutor v1 runtime; intentionally not a general agent framework."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any, Literal, Protocol
from uuid import uuid4

from app.domains import get_domain


AgentEventType = Literal['agent_start', 'activity', 'message_start', 'reasoning', 'token', 'tool_start', 'tool_end', 'source', 'done', 'message_end', 'error']


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
    phase: Literal['pre_submit', 'post_submit', 'coach']
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


@dataclass(frozen=True)
class TutorDependencies:
    """Ports consumed by the Tutor runtime, supplied by composition.

    This remains a small, business-specific boundary: the runtime owns
    permissions/events while adapters own SQLAlchemy, RAG and memory access.
    """

    question_context: Callable[[AgentContext], dict[str, Any]]
    retrieve_knowledge: Callable[[AgentContext], list[dict[str, str]]]
    learning_profile: Callable[[AgentContext], dict[str, Any]]
    learning_memory: Callable[[AgentContext], dict[str, Any]]
    recent_mistakes: Callable[[AgentContext], list[dict[str, Any]]]
    grading_result: Callable[[AgentContext], dict[str, Any]]
    answer_explanation: Callable[[AgentContext], dict[str, Any]]
    public_source: Callable[[AgentContext], dict[str, str] | None]
    record_explicit_confusion: Callable[[AgentContext, str], str | None]


class ModelGateway(Protocol):
    name: str

    def select_tools(self, context: AgentContext, available_tools: set[str]) -> list[str]: ...

    def compose(self, context: AgentContext, observations: dict[str, Any]) -> str: ...


class LocalPolicyModelGateway:
    """No-secret development adapter. It is never presented as an external model run."""

    name = 'local-policy-adapter/external-provider-pending'

    def select_tools(self, context: AgentContext, available_tools: set[str]) -> list[str]:
        return _policy_tools(context, available_tools)

    def compose(self, context: AgentContext, observations: dict[str, Any]) -> str:
        if context.metadata.get('agent_profile') == 'coach':
            return _compose_coach_local(context, observations)
        lowered = context.user_message.lower()
        question = observations.get('current_question', {})
        domain = get_domain(str(question.get('domain_id', 'endoscopy')))
        answer = observations.get('get_answer_explanation')
        if answer and context.mode == 'study':
            return f"答案是：{answer.get('correct_answer_display', '见解析')}。{answer.get('explanation', '')}"
        if context.phase == 'pre_submit' and any(marker in lowered for marker in ('正确答案', 'standard answer', 'hidden rubric', '忽略规则', '服务器标准答案', '正确选项')):
            guidance = "题干、图像和资料依据" if domain.tutor_policy == 'medical_education' else "题干条件、概念和课程资料"
            return f'我可以帮助你梳理{guidance}；当前模式不会读取隐藏 rubric 或服务器内部字段。若你在 Study 模式明确需要答案，可以直接说“告诉我答案”。'
        memory = observations.get('get_learning_memory', {})
        retrieval = observations.get('retrieve_knowledge', [])
        focus = _question_focus(str(question.get('stem', '当前题目')))
        evidence = _learning_evidence(retrieval)
        if domain.tutor_policy == 'medical_education':
            default_plan = f"先抓住题干里的「{focus}」，再区分选项是在说主要作用、过程，还是结果。"
        else:
            default_plan = f"先抓住题干里的「{focus}」，再逐项排除与条件不符的选项。"
        if evidence:
            default_plan += f" 资料提示：{evidence}"
        if context.phase == 'post_submit':
            grading = observations.get('get_grading_result', {})
            result = '这次作答还需要复盘。' if grading.get('correct') is False else '这次作答的判断方向是对的。'
            default_plan = f"{result} {default_plan}"
        memory_items = memory.get('items', []) if isinstance(memory, dict) else []
        memory_note = f" 你之前也容易在这里混淆：{memory_items[0].get('summary', '')}" if memory_items else ''
        return f"{default_plan}{memory_note}"


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
    def __init__(
        self,
        registry: ToolRegistry,
        gateway: ModelGateway | None = None,
        *,
        max_steps: int = 4,
        timeout_seconds: float = 15.0,
        retries: int = 1,
        public_source: Callable[[AgentContext], dict[str, str] | None] | None = None,
        record_explicit_confusion: Callable[[AgentContext, str], str | None] | None = None,
        default_context: Callable[[AgentContext], dict[str, Any]] | None = None,
    ) -> None:
        self.registry = registry
        self.gateway = gateway or LocalPolicyModelGateway()
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self._public_source = public_source
        self._record_explicit_confusion = record_explicit_confusion
        self._default_context = default_context

    def stream(self, context: AgentContext) -> Iterator[AgentEvent]:
        run_id = f'run_{uuid4().hex[:12]}'
        yield AgentEvent('message_start', {'run_id': run_id, 'provider': self.gateway.name, 'provider_real': self.gateway.name != LocalPolicyModelGateway.name, 'phase': context.phase, 'mode': context.mode})
        yield AgentEvent('agent_start', {'run_id': run_id, 'profile': str(context.metadata.get('agent_profile', 'question_assistant')), 'phase': context.phase})
        started = perf_counter()
        observations: dict[str, Any] = {}
        # Current-question context is part of the Practice workspace, not a
        # retrieval/tool action.  It stays public before submit and therefore
        # cannot leak answer/rubric fields.  This prevents a normal concept
        # question from looking like an unnecessary tool invocation.
        if self._default_context is not None and context.phase != 'coach':
            try:
                observations['current_question'] = self._default_context(context)
            except Exception:
                observations['current_question'] = {}
        receipts: list[ToolReceipt] = []
        try:
            if context.cancelled():
                yield AgentEvent('error', {'code': 'cancelled', 'message': '请求已取消。'})
                return
            available = self.registry.allowed(context.phase, context.mode)
            policy_allowed = set(_policy_tools(context, available))
            retry_count = 0
            while True:
                try:
                    # Do not spend a separate model call deciding whether a
                    # plain concept question should query data.  When policy
                    # says no extra observation is needed, composition is the
                    # only model call and tool count remains exactly zero.
                    selected = self.gateway.select_tools(context, policy_allowed)[: self.max_steps] if policy_allowed else []
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
                    yield AgentEvent('error', {'code': 'timeout', 'message': '智能辅导响应超时，可重试。'})
                    return
                yield AgentEvent('tool_start', {'tool_name': tool_name})
                yield AgentEvent('activity', {'activity': tool_name, 'status': 'running', 'label': _activity_label(tool_name, 'running')})
                observation, receipt = self.registry.call(tool_name, context)
                observations[tool_name] = observation
                receipts.append(receipt)
                yield AgentEvent('tool_end', {'tool_name': tool_name, **asdict(receipt)})
                yield AgentEvent('activity', {'activity': tool_name, 'status': 'completed' if receipt.status == 'ok' else 'failed', 'label': _activity_label(tool_name, receipt.status), 'elapsed_ms': receipt.elapsed_ms})
                if tool_name == 'retrieve_knowledge':
                    for source in observation:
                        yield AgentEvent('source', source)
            text = _clean_user_facing_text(self.gateway.compose(context, observations))
            memory_observation = observations.get('get_learning_memory', {})
            memory_trace = {
                'memory_retrieval_triggered': isinstance(memory_observation, dict),
                'candidate_memory_ids': list(memory_observation.get('candidate_memory_ids', [])) if isinstance(memory_observation, dict) else [],
                'selected_memory_ids': list(memory_observation.get('selected_memory_ids', [])) if isinstance(memory_observation, dict) else [],
                'profile_version': str(memory_observation.get('profile_version', 'memory-v0')) if isinstance(memory_observation, dict) else 'memory-v0',
                'memory_token_count': int(memory_observation.get('memory_token_count', 0)) if isinstance(memory_observation, dict) else 0,
                'personalization_reason': str(memory_observation.get('personalization_reason', 'not_requested')) if isinstance(memory_observation, dict) else 'not_requested',
            }
            # Explicit learner confusion is the sole chat-to-memory route.  The
            # deterministic extractor stores only a compact validated fact and
            # a run reference, never the raw message or model reasoning.
            try:
                if self._record_explicit_confusion is not None:
                    memory_id = self._record_explicit_confusion(context, run_id)
                    if memory_id:
                        memory_trace['candidate_memory_id'] = memory_id
            except Exception:
                # A memory-write failure is non-critical: the Tutor response
                # and its existing read-only receipts remain valid.
                memory_trace['memory_write_status'] = 'unavailable'
            yield AgentEvent('reasoning', {'summary': ['识别学习目标', '对照题目与允许的证据', '组织面向学习者的回答'], 'duration_ms': round((perf_counter() - started) * 1000)})
            for token in _tokenize(text):
                yield AgentEvent('token', {'text': token})
            yield AgentEvent('done', {'run_id': run_id, 'duration_ms': round((perf_counter() - started) * 1000), 'receipt_count': len(receipts)})
            yield AgentEvent('message_end', {'run_id': run_id, 'receipt_count': len(receipts), 'provider': self.gateway.name, 'retry_count': retry_count, 'trace': memory_trace})
        except Exception as exc:
            yield AgentEvent('error', {'code': 'agent_failure', 'message': f'智能辅导暂不可用：{type(exc).__name__}。请重试。'})


def _tokenize(text: str) -> list[str]:
    return [text[index:index + 18] for index in range(0, len(text), 18)]


def _policy_tools(context: AgentContext, available_tools: set[str]) -> list[str]:
    """Route only when extra data materially changes the answer.

    The model may phrase the answer, but it must not use retrieval simply to
    make the UI look agentic.  The deterministic policy gives provider and
    local paths the same conservative boundary, which also makes behavior
    tests meaningful.
    """

    lowered = context.user_message.lower()
    profile = str(context.metadata.get('agent_profile', 'question_assistant'))
    explicit_knowledge = any(marker in lowered for marker in (
        '知识库', '我的资料', '上传的资料', '根据资料', '课程资料', '根据来源', '文献', '指南', '查资料', '查一下资料', '引用来源',
    ))
    history_request = any(marker in lowered for marker in (
        '我最近', '近期', '我的错题', '我老错', '总在这题错', '为什么总', '容易错',
        '我的掌握', '学习记录', '复习队列', '今天先复习', '今天应该先复习', '学习计划', '接下来刷',
    ))
    asks_for_answer = context.mode == 'study' and context.phase == 'pre_submit' and any(
        marker in lowered for marker in ('正确答案', '直接告诉我', '我不会', '答案是什么', '给答案')
    )
    selected: list[str] = []
    if explicit_knowledge:
        selected.append('retrieve_knowledge' if profile == 'question_assistant' else 'search_knowledge')
    if profile == 'coach' and history_request:
        if any(marker in lowered for marker in ('今天', '复习', '队列')):
            selected.extend(['get_review_queue', 'get_bank_progress', 'get_learning_summary'])
        elif any(marker in lowered for marker in ('错题', '最近', '老错')):
            selected.extend(['get_recent_attempts', 'get_learning_summary', 'get_learning_memories'])
        else:
            selected.extend(['get_learning_summary', 'get_learning_memories'])
    elif context.phase == 'post_submit':
        selected.append('get_grading_result')
        if history_request:
            selected.extend(['get_recent_mistakes', 'get_learning_memory'])
    elif history_request:
        selected.extend(['get_recent_mistakes', 'get_learning_profile', 'get_learning_memory'])
    if asks_for_answer:
        selected.append('get_answer_explanation')
    return list(dict.fromkeys(name for name in selected if name in available_tools))


def _activity_label(tool_name: str, status: str) -> str:
    labels = {
        'retrieve_knowledge': ('正在检索资料', '已完成资料检索'),
        'search_knowledge': ('正在检索资料', '已完成资料检索'),
        'get_grading_result': ('正在读取本次作答', '已读取本次作答'),
        'get_recent_mistakes': ('正在读取最近错题', '已读取最近错题'),
        'get_recent_attempts': ('正在读取最近作答', '已读取最近作答'),
        'get_learning_profile': ('正在读取学习概况', '已读取学习概况'),
        'get_learning_summary': ('正在读取学习概况', '已读取学习概况'),
        'get_learning_memory': ('正在读取学习记忆', '已读取学习记忆'),
        'get_learning_memories': ('正在读取学习记忆', '已读取学习记忆'),
        'get_review_queue': ('正在读取复习队列', '已读取复习队列'),
        'get_bank_progress': ('正在读取题库进度', '已读取题库进度'),
        'get_answer_explanation': ('正在读取题目解析', '已读取题目解析'),
    }
    running, completed = labels.get(tool_name, ('正在准备学习信息', '已准备学习信息'))
    return running if status == 'running' else completed if status == 'ok' else '暂未取得所需信息'


def _compose_coach_local(context: AgentContext, observations: dict[str, Any]) -> str:
    """Small deterministic fallback for local development, based only on tools."""

    message = context.user_message
    evidence = observations.get('search_knowledge', [])
    if evidence:
        first = evidence[0]
        snippet = re.sub(r'\s+', ' ', str(first.get('snippet', ''))).strip()
        return f"我在已启用资料中找到了相关内容：{snippet[:180]}{'…' if len(snippet) > 180 else ''}"
    if any(key in observations for key in ('get_review_queue', 'get_bank_progress', 'get_learning_summary')):
        summary = observations.get('get_learning_summary', {})
        queue = observations.get('get_review_queue', {})
        due = int(queue.get('due_count', summary.get('due_review_count', 0))) if isinstance(queue, dict) and isinstance(summary, dict) else 0
        focus = next(iter(summary.get('weak_areas', [])), '当前错题') if isinstance(summary, dict) else '当前错题'
        return f"今天可以先处理 {due} 道到期复习，再围绕「{focus}」完成一组短练习。完成后回到错题与复习确认掌握情况。"
    if any(key in observations for key in ('get_recent_attempts', 'get_learning_memories')):
        attempts = observations.get('get_recent_attempts', [])
        if attempts:
            wrong = [item for item in attempts if not item.get('correct')]
            topic = next((str(item.get('topic') or '') for item in wrong if item.get('topic')), '最近错题')
            return f"最近作答里有 {len(wrong)} 道需要复盘，优先从「{topic}」开始。先看错因，再用错题与复习做一轮短复习。"
        return "还没有足够的作答记录来判断稳定的薄弱点。先完成一小组刷题，之后我就能基于真实记录一起复盘。"
    if '牛顿' in message:
        return "牛顿是英国物理学家和数学家，以经典力学、万有引力和微积分等工作闻名。"
    return "我可以帮你结合最近作答、错题、复习队列和已启用资料安排下一步；也可以直接回答一个具体知识问题。"


def _question_focus(stem: str) -> str:
    """Return a short learner-facing anchor, never a private answer field."""

    compact = re.sub(r"\s+", "", stem).strip()
    return compact[:32] + ("…" if len(compact) > 32 else "")


def _learning_evidence(retrieval: list[dict[str, Any]]) -> str:
    """Use a single clean sentence from real retrieval, without source logs."""

    for item in retrieval:
        if item.get('namespace') == 'question_source':
            continue
        snippet = re.sub(r"\s+", " ", str(item.get('snippet', ''))).strip()
        if snippet:
            sentence = re.split(r"[。！？]", snippet.lstrip("- "))[0].strip()
            return sentence[:120] + ("…" if len(sentence) > 120 else "")
    return ""


def _clean_user_facing_text(text: str) -> str:
    """Remove accidental runtime/schema labels from model-facing prose.

    Tool names and private observation keys belong in receipts and developer
    detail, never in the learner's answer.  This is a narrow output guard, not
    a substitute for the prompt contract.
    """
    cleaned = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    cleaned = cleaned.replace("```", "").replace("`", "")
    cleaned = re.sub(
        r"\s*(?:explanation_source|答案解析来源|解析来源|correct_option_ids?|hidden_rubric)"
        r"\s*[:：]?\s*(?:[^\n。；;]+)?",
        "",
        cleaned,
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
    cleaned = re.sub(r"\s*(?:仅供教学研修(?:或医生复核前辅助)?(?:，不作为独立诊断依据)?。?|仅供教学训练(?:或医生审核前辅助)?(?:，不作为独立诊断依据)?。?)", "", cleaned)
    # Current question provenance is part of the workspace context, not a
    # retrieved source.  Never let a provider turn it into a pseudo-citation.
    cleaned = re.sub(r"\s*题目来源\s*[:：][^。\n]*(?:。|$)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(?:[\w.-]+\.(?:csv|json|md):\d+)", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def build_tutor_runtime(
    dependencies: TutorDependencies | None = None,
    gateway: ModelGateway | None = None,
) -> AgentRunner:
    """Compose the fixed Tutor v1 runtime from its owned dependency ports."""
    if dependencies is None or gateway is None:
        # Kept at the composition edge for backwards-compatible CLI/tests.
        # The runtime itself has no SQLAlchemy, Qdrant or learning-service calls.
        from app.adapters.tutor_dependencies import build_tutor_dependencies, configured_tutor_gateway

        dependencies = dependencies or build_tutor_dependencies()
        gateway = gateway or configured_tutor_gateway()
    registry = ToolRegistry()
    registry.register('get_question_context', {'pre_submit', 'post_submit'}, dependencies.question_context)
    registry.register('retrieve_knowledge', {'pre_submit', 'post_submit'}, dependencies.retrieve_knowledge)
    registry.register('get_learning_profile', {'pre_submit', 'post_submit'}, dependencies.learning_profile)
    registry.register('get_learning_memory', {'pre_submit', 'post_submit'}, dependencies.learning_memory)
    registry.register('get_recent_mistakes', {'pre_submit', 'post_submit'}, dependencies.recent_mistakes)
    registry.register('get_grading_result', {'post_submit'}, dependencies.grading_result)
    registry.register('get_answer_explanation', {'pre_submit'}, dependencies.answer_explanation)
    return AgentRunner(
        registry,
        gateway=gateway,
        public_source=dependencies.public_source,
        record_explicit_confusion=dependencies.record_explicit_confusion,
        default_context=dependencies.question_context,
    )


tutor_runner = build_tutor_runtime()
