"""Persistent cross-session learning coach built on the existing Agent runtime."""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from typing import Any, Iterator
from uuid import uuid4

from sqlalchemy import select

from app.adapters.tutor_dependencies import configured_tutor_gateway
from app.db.database import SessionLocal
from app.db.models import AgentConversationModel, AgentMessageModel, AttemptModel, QuestionBankModel, QuestionModel, ReviewCardModel
from app.db.repositories import Stage1Repository
from app.services.agent_runtime import AgentContext, AgentEvent, AgentRunner, LocalPolicyModelGateway, ToolRegistry
from app.services.learning_memory_service import learning_memory_service
from app.services.stage1_service import stage1_service


COACH_PROMPT = (Path(__file__).resolve().parents[1] / "agents" / "prompts" / "coach_agent.md").read_text(encoding="utf-8")


class CoachGateway:
    """The coach shares the installed Provider but carries a separate prompt."""

    name = "local-learning-coach"

    def __init__(self) -> None:
        self._provider_enabled = False
        try:
            gateway = configured_tutor_gateway()
            self._provider_enabled = gateway.name != LocalPolicyModelGateway.name
        except Exception:
            self._provider_enabled = False
        if self._provider_enabled:
            self.name = "openai-compatible-learning-coach"

    def select_tools(self, context: AgentContext, available_tools: set[str]) -> list[str]:
        # AgentRunner has already applied the shared policy gate.  Returning
        # the small permitted set avoids another LLM request just to decide
        # whether a user said “my recent errors”.
        return sorted(available_tools)

    def compose(self, context: AgentContext, observations: dict[str, Any]) -> str:
        if not self._provider_enabled:
            return LocalPolicyModelGateway().compose(context, observations)
        from app.services.llm_provider import llm_provider

        result = llm_provider.chat(
            system_prompt=COACH_PROMPT + "\n\nUse only supplied learning observations. Do not invent a history or a source. Do not output tool names, JSON, internal IDs, hidden reasoning, diagnosis, or treatment advice.",
            user_prompt=(
                f"用户问题：{context.user_message}\n\n"
                f"允许的学习观察：{observations}\n\n"
                f"最近对话：{context.metadata.get('conversation', [])[-12:]}"
            ),
            temperature=0.2,
            max_tokens=440,
        )
        if not result.ok:
            raise RuntimeError(result.error)
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
            .where(AttemptModel.learner_id == context.learner_id)
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
        # not a QuestionModel title.  Keep the Coach on the same public DTO so
        # it can read the real queue without depending on a hidden field.
        "items": [{"question_id": item["question_id"], "bank_name": item["bank_name"], "title": item.get("question_summary", item.get("title", "")), "due_at": item.get("due_at")} for item in items],
    }


def _bank_progress(context: AgentContext) -> list[dict[str, Any]]:
    rows = stage1_service.list_banks(context.learner_id, "endoscopy")
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
        return learning_memory_service.list_for_learner(session, learner_id=context.learner_id, domain_id="endoscopy", limit=5)


def _search_knowledge(context: AgentContext) -> list[dict[str, str]]:
    if os.getenv("TUTOR_RETRIEVAL_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return []
    try:
        from app.services.rag_service import rag_service

        citations = rag_service.retrieve(
            context.user_message,
            mode="hybrid",
            limit=4,
            domain_id="endoscopy",
            namespaces=["system", "user", "qbank_explanations"],
        )
    except Exception:
        return []
    return [
        {
            "document_name": item.document_name, "page": str(item.page), "section": item.section,
            "snippet": item.snippet, "source_uri": item.source_uri or "", "namespace": item.namespace,
        }
        for item in citations
    ]


def _runner() -> AgentRunner:
    registry = ToolRegistry()
    registry.register("get_learning_summary", {"coach"}, _learning_summary)
    registry.register("get_recent_attempts", {"coach"}, _recent_attempts)
    registry.register("get_review_queue", {"coach"}, _review_queue)
    registry.register("get_bank_progress", {"coach"}, _bank_progress)
    registry.register("get_learning_memories", {"coach"}, _learning_memories)
    registry.register("search_knowledge", {"coach"}, _search_knowledge)
    return AgentRunner(registry, gateway=CoachGateway(), max_steps=4, timeout_seconds=20.0, retries=1)


coach_runner = _runner()


class CoachAgentService:
    def create_conversation(self, learner_id: str = "demo_learner") -> dict[str, Any]:
        row = AgentConversationModel(
            conversation_id=f"coach_{uuid4().hex[:12]}", learner_id=learner_id, agent_profile="coach", title="新的带教对话"
        )
        with SessionLocal() as session:
            session.add(row)
            session.commit()
            return self._conversation_payload(row, include_messages=True)

    def list_conversations(self, learner_id: str = "demo_learner") -> list[dict[str, Any]]:
        with SessionLocal() as session:
            rows = list(session.scalars(select(AgentConversationModel).where(
                AgentConversationModel.learner_id == learner_id, AgentConversationModel.agent_profile == "coach"
            ).order_by(AgentConversationModel.updated_at.desc()).limit(40)))
            return [self._conversation_payload(row, include_messages=False) for row in rows]

    def detail(self, conversation_id: str, learner_id: str = "demo_learner") -> dict[str, Any]:
        with SessionLocal() as session:
            return self._conversation_payload(self._conversation(session, conversation_id, learner_id), include_messages=True, session=session)

    def stream_message(self, *, conversation_id: str, learner_id: str, message: str) -> Iterator[AgentEvent]:
        with SessionLocal() as session:
            conversation = self._conversation(session, conversation_id, learner_id)
            history = list(session.scalars(select(AgentMessageModel).where(
                AgentMessageModel.conversation_id == conversation_id
            ).order_by(AgentMessageModel.created_at.desc()).limit(12)))
            history.reverse()
            user = AgentMessageModel(message_id=f"coachmsg_{uuid4().hex[:12]}", conversation_id=conversation_id, role="user", content=message)
            session.add(user)
            if conversation.title == "新的带教对话":
                conversation.title = message.strip().replace("\n", " ")[:32] or conversation.title
            session.commit()
            prior = [{"role": item.role, "content": item.content} for item in history]

        context = AgentContext(
            question_id="", learner_id=learner_id, user_message=message, phase="coach", mode="study",
            metadata={"agent_profile": "coach", "conversation": prior},
        )
        answer: list[str] = []
        activities: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        for event in coach_runner.stream(context):
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
                    message_id=f"coachmsg_{uuid4().hex[:12]}", conversation_id=conversation_id, role="assistant", content=content,
                    activity=activities, sources=sources,
                ))
                conversation.updated_at = datetime.utcnow()
                session.commit()

    @staticmethod
    def _conversation(session: Any, conversation_id: str, learner_id: str) -> AgentConversationModel:
        row = session.get(AgentConversationModel, conversation_id)
        if row is None or row.learner_id != learner_id or row.agent_profile != "coach":
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
                payload["messages"] = [{"id": item.message_id, "role": item.role, "content": item.content, "activity": item.activity, "sources": item.sources, "created_at": item.created_at.isoformat()} for item in messages]
            finally:
                if own_session:
                    active.close()
        return payload


coach_agent_service = CoachAgentService()
