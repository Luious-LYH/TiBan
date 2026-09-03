"""Concrete Tutor dependency adapters.

All SQLAlchemy, RAG and learning-memory access is intentionally contained in
this composition module; `agent_runtime` receives only its narrow callables.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select

from app.core import config
from app.domains import get_domain
from app.db.database import SessionLocal
from app.db.models import AttemptModel, PracticeSessionItemModel, PracticeSessionModel, QuestionModel, TutorThreadModel
from app.db.repositories import Stage1Repository
from app.db.serializers import grading_question_payload
from app.services.agent_runtime import (
    AgentContext,
    LocalPolicyModelGateway,
    ModelGateway,
    TutorDependencies,
)
from app.adapters.tutor_gateway import OpenAICompatibleTutorGateway
from app.services.stage1_service import stage1_service


def _question_context(context: AgentContext) -> dict[str, Any]:
    """Build only current-session Tutor context; never learner history."""

    if not context.practice_session_id:
        raise ValueError("practice_session_id required for Tutor")
    with SessionLocal() as session:
        practice = session.get(PracticeSessionModel, context.practice_session_id)
        if practice is None or practice.learner_id != context.learner_id:
            raise ValueError("practice session not found")
        member = session.scalar(select(PracticeSessionItemModel).where(
            PracticeSessionItemModel.practice_session_id == practice.session_id,
            PracticeSessionItemModel.question_id == context.question_id,
        ))
        if member is None:
            raise ValueError("question is not part of current practice session")
        if not context.tutor_thread_id:
            raise ValueError("tutor_thread_id required for Tutor")
        thread = session.get(TutorThreadModel, context.tutor_thread_id)
        if (
            thread is None
            or thread.practice_session_id != practice.session_id
            or thread.learner_id != context.learner_id
            or thread.status != "active"
        ):
            raise ValueError("Tutor thread is not an active thread for current practice session")
        payload = stage1_service.public_question(context.question_id)
        payload["practice_session"] = {
            "session_id": practice.session_id,
            "mode": practice.mode,
            "question_count": int(practice.requested_question_count),
            "current_position": int(practice.current_position),
        }
        return payload


def _retrieve_knowledge(context: AgentContext) -> list[dict[str, str]]:
    question = _question_context(context)
    # Retrieval is explicit-route only. Keep the user request first, with a
    # small question anchor for terms such as “这个选项”，rather than searching
    # the entire stem and manufacturing a superficially similar citation.
    query = f"{context.user_message}\n当前题目：{question.get('stem', '')[:180]}"
    citations: list[Any] = []
    if os.getenv("TUTOR_RETRIEVAL_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}:
        try:
            from app.services.rag_service import rag_service

            manifest = get_domain(str(question["domain_id"]))
            citations = rag_service.retrieve(
                query,
                mode="hybrid",
                limit=4,
                domain_id=manifest.domain_id,
                namespaces=["system", "user", "qbank_explanations"],
            )
        except Exception:
            # No local fake source is presented as RAG evidence. Public question
            # provenance below remains a truthful fallback when index is absent.
            citations = []
    if citations:
        return [
            {
                "chunk_id": citation.chunk_id,
                "document_name": citation.document_name,
                "page": str(citation.page),
                "section": citation.section,
                "snippet": citation.snippet,
                "source_uri": citation.source_uri or "",
                "namespace": citation.namespace,
            }
            for citation in citations
        ]
    # Zero is a valid retrieval result.  Question provenance is context, never
    # masqueraded as a knowledge-base citation.
    return []


def _grading_result(context: AgentContext) -> dict[str, Any]:
    if not context.attempt_id:
        raise ValueError("attempt_id required post submit")
    with SessionLocal() as session:
        attempt = session.get(AttemptModel, context.attempt_id)
        if not attempt or attempt.learner_id != context.learner_id or attempt.practice_session_id != context.practice_session_id:
            raise ValueError("attempt not found")
        return {"score": attempt.score, "correct": attempt.correct, "error_tags": attempt.error_tags}


def _answer_explanation(context: AgentContext) -> dict[str, Any]:
    if context.mode != "study" or context.phase != "pre_submit":
        raise PermissionError("answer explanation is only available in Study pre-submit mode")
    with SessionLocal() as session:
        question = Stage1Repository(session).get_question(context.question_id)
        grading = grading_question_payload(question)
        _, display = stage1_service._answer_displays(
            grading,
            grading.get("correct_option_id", grading.get("correct_option_ids", grading.get("correct_value", ""))),
        )
        if grading["question_type"] == "short_answer":
            display = "参考答案见题目解析与评分 rubric"
        return {
            "correct_answer_display": display,
            "explanation": question.explanation,
            "explanation_source": question.explanation_source,
        }


def build_tutor_dependencies() -> TutorDependencies:
    return TutorDependencies(
        question_context=_question_context,
        retrieve_knowledge=_retrieve_knowledge,
        grading_result=_grading_result,
        answer_explanation=_answer_explanation,
    )


def configured_tutor_gateway() -> ModelGateway:
    from app.services.runtime_settings_service import runtime_settings_service
    from app.services.llm_provider import llm_provider

    runtime_settings_service.sync()
    runtime_override = bool(runtime_settings_service.llm_public()["runtime_override"])
    provider_ready = bool(llm_provider.status().get("configured"))
    if (os.getenv("TUTOR_PROVIDER_ENABLED", "").strip().lower() == "true" or runtime_override) and provider_ready:
        return OpenAICompatibleTutorGateway()
    return LocalPolicyModelGateway()
