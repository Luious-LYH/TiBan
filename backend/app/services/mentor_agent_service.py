"""Persistent cross-session Mentor Agent on the shared controlled runtime."""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from typing import Any, Iterator
from uuid import uuid4

from sqlalchemy import delete, select

from app.application.errors import normalize_provider_error
from app.db.database import SessionLocal
from app.db.models import AgentConversationModel, AgentMessageModel, AttemptModel, QuestionBankModel, QuestionModel, ReviewCardModel
from app.db.repositories import Stage1Repository
from app.services.agent_runtime import AgentContext, AgentEvent, AgentRunner, LocalPolicyModelGateway, ToolRegistry
from app.services.learning_memory_service import learning_memory_service
from app.services.llm_provider import llm_provider
from app.services.semantic_memory_service import semantic_memory_service
from app.services.stage1_service import stage1_service


MENTOR_PROMPT = (Path(__file__).resolve().parents[1] / "agents" / "prompts" / "mentor_agent.md").read_text(encoding="utf-8")


def _requests_reference_images(message: str) -> bool:
    """Whether a Mentor turn should place retrieved figures in the reply.

    Retrieval itself remains available for normal source questions, but an
    inline figure is intentionally opt-in. That prevents ordinary learning
    replies from turning into a gallery while making requests such as “给我
    相关图片” feel immediate and useful in the chat transcript.
    """

    lowered = message.lower()
    phrases = (
        "相关图片", "资料图片", "给我图片", "给张图", "返回图片", "展示图片", "找图片",
        "看看图片", "看图", "配图", "图示", "图片看看",
        "show me an image", "show me image", "show image", "related image", "return image",
    )
    return any(phrase in lowered for phrase in phrases)


def _provider_failure_fallback(context: AgentContext, observations: dict[str, Any]) -> str:
    """Keep a successful evidence retrieval useful if generation is offline.

    This never substitutes a visual interpretation. It only states the
    document/page provenance already returned by the governed retriever, so a
    learner who explicitly asked for an image still receives a useful, honest
    answer and the matching figure card.
    """

    retrieval = observations.get("search_knowledge")
    if _requests_reference_images(context.user_message) and isinstance(retrieval, list):
        references: list[str] = []
        for item in retrieval:
            if not isinstance(item, dict) or not item.get("show_in_chat") or not item.get("image_urls"):
                continue
            label = f"{str(item.get('document_name') or '学习资料')}第 {str(item.get('page') or '?')} 页"
            if label not in references:
                references.append(label)
        if references:
            return f"已找到与问题相关的资料图片，出处为{'、'.join(references[:3])}。图片已附在本条回答中，可点击查看原图。"
        return "当前已启用资料中没有检索到可追溯的相关图片。"
    return LocalPolicyModelGateway().compose(context, observations)


def _context_image_paths(context: AgentContext, observations: dict[str, Any] | None = None) -> list[str]:
    # A mentor reply can cite several nearby figures. Bound that visual
    # context after user-attached imagery so the normal response remains fast
    # and the model receives only the strongest retrieved evidence set.
    direct_paths = [str(path) for path in context.image_paths if str(path).strip()]
    evidence_paths: list[str] = []
    for observation in (observations or {}).values():
        if not isinstance(observation, list):
            continue
        for item in observation:
            if not isinstance(item, dict):
                continue
            urls = item.get("image_urls", [])
            if isinstance(urls, list):
                evidence_paths.extend(str(url) for url in urls if str(url).strip())
    return list(dict.fromkeys([*direct_paths, *evidence_paths]))[:4]


class MentorGateway:
    """Mentor shares the installed Provider but has a long-term prompt boundary."""

    @property
    def _provider_enabled(self) -> bool:
        # Runtime settings may be applied by another API request/process after
        # this long-lived runner was composed. Read the shared provider status
        # at the gateway seam so Mentor does not keep a stale rule/provider or
        # vision capability snapshot.
        try:
            return bool(llm_provider.status().get("configured"))
        except Exception:
            return False

    @property
    def name(self) -> str:
        return "openai-compatible-learning-mentor" if self._provider_enabled else "local-learning-mentor"

    @property
    def supports_vision(self) -> bool:
        if not self._provider_enabled:
            return False
        try:
            return bool(llm_provider.status().get("vision_configured"))
        except Exception:
            return False

    def select_tools(self, context: AgentContext, available_tools: set[str]) -> list[str]:
        # AgentRunner has already applied the shared policy gate.  Returning
        # the small permitted set avoids another LLM request just to decide
        # whether a user said “my recent errors”.
        return sorted(available_tools)

    def compose(self, context: AgentContext, observations: dict[str, Any]) -> str:
        if not self._provider_enabled:
            return LocalPolicyModelGateway().compose(context, observations)
        result = llm_provider.chat(
            system_prompt=MENTOR_PROMPT + "\n\nUse only supplied deterministic learning state, semantic memory, tool observations, and real citations. Do not invent history or sources. Do not output tool names, JSON, internal IDs, hidden reasoning, diagnosis, or treatment advice.",
            user_prompt=(
                f"用户问题：{context.user_message}\n\n"
                f"已构建的长期学习上下文：{context.metadata.get('mentor_context', {})}\n\n"
                f"允许的学习观察：{observations}\n\n"
                f"最近对话：{context.metadata.get('conversation', [])[-12:]}"
            ),
            image_paths=_context_image_paths(context, observations),
            temperature=0.2,
            max_tokens=440,
        )
        if not result.ok:
            return _provider_failure_fallback(context, observations)
        return result.text


def _learning_summary(context: AgentContext) -> dict[str, Any]:
    overview = stage1_service.overview(context.learner_id)
    return {
        "completed_today": int(overview.get("completed_today", 0)),
        "due_review_count": int(overview.get("due_review_count", 0)),
        "weak_areas": list(overview.get("weak_areas", []))[:5],
    }


def _recent_attempts(context: AgentContext) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        rows = list(session.execute(
            select(AttemptModel, QuestionModel, QuestionBankModel)
            .join(QuestionModel, QuestionModel.question_id == AttemptModel.question_id)
            .join(QuestionBankModel, QuestionBankModel.bank_id == QuestionModel.bank_id)
            .where(
                AttemptModel.learner_id == context.learner_id,
                QuestionModel.business_usage == "user_ready",
                QuestionBankModel.status == "published",
            )
            .order_by(AttemptModel.created_at.desc())
            .limit(12)
        ).all())
    return [
        {
            "question_id": attempt.question_id,
            "bank_name": bank.name,
            "title": question.title,
            "topic": question.topic or question.subject,
            "correct": attempt.correct,
            "created_at": attempt.created_at.isoformat(),
        }
        for attempt, question, bank in rows
    ]


def _review_queue(context: AgentContext) -> dict[str, Any]:
    with SessionLocal() as session:
        repository = Stage1Repository(session)
        items = repository.review_items(learner_id=context.learner_id, tab="due", limit=6)
        summary = repository.review_summary(context.learner_id)
    return {
        "due_count": int(summary["due_count"]),
        # Review cards deliberately expose a learner-facing question_summary,
        # not a QuestionModel title. Keep Mentor on the same public DTO so
        # it can read the real queue without depending on a hidden field.
        "items": [{"question_id": item["question_id"], "bank_name": item["bank_name"], "title": item.get("question_summary", item.get("title", "")), "due_at": item.get("due_at")} for item in items],
    }


def _bank_progress(context: AgentContext) -> list[dict[str, Any]]:
    rows = stage1_service.list_banks(context.learner_id)
    return [
        {
            "bank_id": row["bank_id"], "name": row["name"], "question_count": row["question_count"],
            "completed_count": row.get("completed_count", 0), "incorrect_count": row.get("incorrect_count", 0),
            "marked_count": row.get("marked_count", 0),
        }
        for row in rows
    ]


def _learning_memories(context: AgentContext) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        recent_domains = list(session.scalars(
            select(QuestionModel.domain_id)
            .join(AttemptModel, AttemptModel.question_id == QuestionModel.question_id)
            .where(
                AttemptModel.learner_id == context.learner_id,
                QuestionModel.business_usage == "user_ready",
            )
            .order_by(AttemptModel.created_at.desc())
            .limit(12)
        ))
        domains: list[str] = []
        for domain_id in recent_domains:
            if str(domain_id) not in domains:
                domains.append(str(domain_id))
        memories: list[dict[str, Any]] = []
        for domain_id in domains:
            memories.extend(semantic_memory_service.retrieve(
                session,
                learner_id=context.learner_id,
                domain_id=domain_id,
                query=context.user_message,
                limit=5,
            ))
        memories.sort(key=lambda item: float(item.get("confidence", 0.0)), reverse=True)
        return memories[:5]


def _knowledge_domain_hint(message: str) -> str | None:
    """Constrain clearly endoscopy-focused material requests before ranking.

    Mentor is intentionally cross-domain for learning plans.  A request that
    explicitly names endoscopy anatomy or teaching images, however, should not
    let an unrelated general question-bank explanation outrank the governed
    endoscopy guide merely because its text embedding is closer.
    """

    lowered = message.lower()
    endoscopy_markers = (
        "内镜", "胃镜", "肠镜", "结肠", "直肠", "盲肠", "回盲瓣", "食管", "胃窦", "十二指肠",
        "消化道", "消化内镜", "endoscopy", "colonoscopy", "gastroscopy", "ileocecal", "cecum",
    )
    return "endoscopy" if any(marker in lowered for marker in endoscopy_markers) else None


def _search_knowledge(context: AgentContext) -> list[dict[str, Any]]:
    if os.getenv("TUTOR_RETRIEVAL_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return []
    try:
        from app.services.rag_service import rag_service

        endoscopy_query = _knowledge_domain_hint(context.user_message) == "endoscopy"
        result = rag_service.retrieve_multimodal(
            context.user_message,
            limit=4,
            domain_id=_knowledge_domain_hint(context.user_message),
            namespaces=["system", "user"] if endoscopy_query else ["system", "user", "qbank_explanations"],
        )
        citations = list(result.get("citations", []))
        image_results = list(result.get("image_results", []))
    except Exception:
        return []
    show_images_in_chat = _requests_reference_images(context.user_message)
    return [
        {
            "document_name": item.document_name, "page": str(item.page), "section": item.section,
            "snippet": item.snippet, "source_uri": item.source_uri or "", "namespace": item.namespace,
            "image_urls": list(item.image_urls), "media_asset_ids": list(item.media_asset_ids),
            # Text citations keep their figure links in the collapsed source
            # area. Only vetted Figure retrieval results below become direct
            # reply cards when the learner explicitly asked to see images.
            "show_in_chat": False,
        }
        for item in citations
    ] + [
        {
            "document_name": str(item.get("document_name") or "教学资料图片"),
            "page": str(item.get("page") or 1), "section": str(item.get("section") or "资料图片"),
            "snippet": str(item.get("caption") or "检索到相关资料图片。"), "source_uri": "", "namespace": "knowledge_media",
            "image_urls": [str(item.get("url"))], "media_asset_ids": [str(item.get("asset_id"))],
            "concepts": list(item.get("concepts") or []), "evidence_links": list(item.get("evidence_links") or []),
            "show_in_chat": show_images_in_chat,
        }
        for item in image_results
        if item.get("url")
    ]


def _runner() -> AgentRunner:
    registry = ToolRegistry()
    registry.register("get_learning_summary", {"mentor"}, _learning_summary)
    registry.register("get_recent_attempts", {"mentor"}, _recent_attempts)
    registry.register("get_review_queue", {"mentor"}, _review_queue)
    registry.register("get_bank_progress", {"mentor"}, _bank_progress)
    registry.register("get_learning_memories", {"mentor"}, _learning_memories)
    registry.register("search_knowledge", {"mentor"}, _search_knowledge)
    return AgentRunner(registry, gateway=MentorGateway(), max_steps=4, timeout_seconds=20.0, retries=1)


mentor_runner = _runner()


def refresh_mentor_runtime_gateway() -> None:
    """Apply the current instance LLM settings to the active Mentor runner."""

    mentor_runner.set_gateway(MentorGateway())


class MentorContextBuilder:
    """Small, explicit context projection for the persistent Mentor only."""

    def build(self, *, learner_id: str, message: str) -> dict[str, Any]:
        context = AgentContext(question_id="", learner_id=learner_id, user_message=message, phase="mentor", metadata={"agent_profile": "mentor"})
        return {
            "learning_summary": _learning_summary(context),
            "semantic_memories": _learning_memories(context)[:3],
        }


class MentorAgentService:
    def create_conversation(self, learner_id: str = "demo_learner") -> dict[str, Any]:
        row = AgentConversationModel(
            conversation_id=f"mentor_{uuid4().hex[:12]}", learner_id=learner_id, agent_profile="mentor", title="新的带教对话"
        )
        with SessionLocal() as session:
            session.add(row)
            session.commit()
            return self._conversation_payload(row, include_messages=True)

    def list_conversations(self, learner_id: str = "demo_learner") -> list[dict[str, Any]]:
        # Reflection is normally queued at startup and after Practice events;
        # this lightweight reconciliation also covers a browser that was
        # closed without sending a final lifecycle signal.
        from app.services.memory_reflection_service import memory_reflection_service
        memory_reflection_service.reconcile_inactive(limit=12)
        with SessionLocal() as session:
            rows = list(session.scalars(select(AgentConversationModel).where(
                AgentConversationModel.learner_id == learner_id, AgentConversationModel.agent_profile == "mentor"
            ).order_by(AgentConversationModel.updated_at.desc()).limit(40)))
            return [self._conversation_payload(row, include_messages=False) for row in rows]

    def detail(self, conversation_id: str, learner_id: str = "demo_learner") -> dict[str, Any]:
        with SessionLocal() as session:
            return self._conversation_payload(self._conversation(session, conversation_id, learner_id), include_messages=True, session=session)

    def delete_conversation(self, conversation_id: str, learner_id: str = "demo_learner") -> dict[str, Any]:
        """Delete one learner-owned Mentor conversation and its durable turns."""

        with SessionLocal() as session:
            conversation = self._conversation(session, conversation_id, learner_id)
            session.execute(delete(AgentMessageModel).where(AgentMessageModel.conversation_id == conversation.conversation_id))
            session.delete(conversation)
            session.commit()
        return {"conversation_id": conversation_id, "deleted": True}

    def stream_message(self, *, conversation_id: str, learner_id: str, message: str, image_asset_id: str | None = None) -> Iterator[AgentEvent]:
        image_path: str | None = None
        with SessionLocal() as session:
            conversation = self._conversation(session, conversation_id, learner_id)
            history = list(session.scalars(select(AgentMessageModel).where(
                AgentMessageModel.conversation_id == conversation_id
            ).order_by(AgentMessageModel.created_at.desc()).limit(12)))
            history.reverse()
            if image_asset_id:
                from app.services.image_asset_service import image_asset_service

                try:
                    # Resolve for authorization/expiry validation only.  The
                    # Agent receives an opaque asset URL, never a local path.
                    image_asset_service.resolve_path(session, image_asset_id, kind="chat")
                    image_path = f"/api/v3/assets/chat-images/{image_asset_id}"
                except (KeyError, FileNotFoundError, ValueError) as exc:
                    raise ValueError("聊天图片不存在或已过期，请重新附加图片。") from exc
            user = AgentMessageModel(
                message_id=f"mentormsg_{uuid4().hex[:12]}", conversation_id=conversation_id,
                role="user", content=message, image_attached=bool(image_asset_id),
                image_asset_id=image_asset_id,
            )
            session.add(user)
            if conversation.title == "新的带教对话":
                conversation.title = message.strip().replace("\n", " ")[:32] or conversation.title
            session.commit()
            prior = [{"role": item.role, "content": item.content} for item in history]

        context = AgentContext(
            question_id="", learner_id=learner_id, user_message=message, phase="mentor", mode="study",
            image_paths=[image_path] if image_path else [],
            metadata={"agent_profile": "mentor", "conversation": prior, "mentor_context": MentorContextBuilder().build(learner_id=learner_id, message=message)},
        )
        answer: list[str] = []
        activities: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        for event in mentor_runner.stream(context):
            if event.event == "token":
                answer.append(str(event.data.get("text", "")))
            elif event.event == "activity":
                activities.append(dict(event.data))
            elif event.event == "source":
                sources.append(dict(event.data))
            yield event
        content = "".join(answer).strip()
        if content:
            with SessionLocal() as session:
                conversation = self._conversation(session, conversation_id, learner_id)
                session.add(AgentMessageModel(
                    message_id=f"mentormsg_{uuid4().hex[:12]}", conversation_id=conversation_id, role="assistant", content=content,
                    activity=activities, sources=sources,
                ))
                conversation.updated_at = datetime.utcnow()
                session.commit()

    @staticmethod
    def _conversation(session: Any, conversation_id: str, learner_id: str) -> AgentConversationModel:
        row = session.get(AgentConversationModel, conversation_id)
        if row is None or row.learner_id != learner_id or row.agent_profile != "mentor":
            raise KeyError(conversation_id)
        return row

    @staticmethod
    def _conversation_payload(row: AgentConversationModel, *, include_messages: bool, session: Any | None = None) -> dict[str, Any]:
        payload = {
            "id": row.conversation_id, "title": row.title, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(),
        }
        if include_messages:
            own_session = session is None
            active = session or SessionLocal()
            try:
                messages = list(active.scalars(select(AgentMessageModel).where(
                    AgentMessageModel.conversation_id == row.conversation_id
                ).order_by(AgentMessageModel.created_at)))
                payload["messages"] = [{"id": item.message_id, "role": item.role, "content": item.content, "activity": item.activity, "sources": item.sources, "image_attached": bool(item.image_attached), "image_asset_id": item.image_asset_id, "created_at": item.created_at.isoformat()} for item in messages]
            finally:
                if own_session:
                    active.close()
        return payload


mentor_agent_service = MentorAgentService()
