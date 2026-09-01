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
from app.db.models import AttemptModel, QuestionModel
from app.db.repositories import Stage1Repository
from app.db.serializers import grading_question_payload
from app.services.agent_runtime import (
    AgentContext,
    LocalPolicyModelGateway,
    ModelGateway,
    TutorDependencies,
)
from app.adapters.tutor_gateway import OpenAICompatibleTutorGateway
from app.services.learning_memory_service import learning_memory_service
from app.services.stage1_service import stage1_service


def _question_context(context: AgentContext) -> dict[str, Any]:
    # Public projection is deliberate: no grading payload reaches pre-submit tools.
    return stage1_service.public_question(context.question_id)


def _public_source(context: AgentContext) -> dict[str, str] | None:
    try:
        question = _question_context(context)
    except Exception:
        return None
    return {
        "document_name": str(question.get("source_dataset", "题目来源")),
        "page": "题目来源",
        "section": str(question.get("body_part", "观察要点")),
        "snippet": str(question.get("citation_note", "当前题目的公开来源信息。")),
        "source_uri": "",
        "namespace": "question_source",
    }


def _retrieve_knowledge(context: AgentContext) -> list[dict[str, str]]:
    question = _question_context(context)
    query = f"{question.get('body_part', '')} {question.get('stem', '')} {context.user_message}"
    citations: list[Any] = []
    if os.getenv("TUTOR_RETRIEVAL_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}:
        try:
            from app.services.rag_service import rag_service

            manifest = get_domain(str(question["domain_id"]))
            citations = rag_service.retrieve(query, mode="dense", limit=3, domain_id=manifest.domain_id, namespaces=list(manifest.knowledge_namespaces))
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
    source = _public_source(context)
    return [source] if source else []


def _learning_profile(context: AgentContext) -> dict[str, Any]:
    overview = stage1_service.overview(context.learner_id)
    return {
        "attempt_count": overview["completed_today"],
        "due_review_count": overview["due_review_count"],
        "weak_areas": overview["weak_areas"],
    }


def _learning_memory(context: AgentContext) -> dict[str, Any]:
    with SessionLocal() as session:
        return learning_memory_service.retrieve_relevant(
            session,
            learner_id=context.learner_id,
            question_id=context.question_id,
            user_message=context.user_message,
        )


def _recent_mistakes(context: AgentContext) -> list[dict[str, Any]]:
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
            "question_id": attempt.question_id,
            "title": question.title,
            "tags": list(question.teaching_tags or [question.body_part]),
            "error_tags": list(attempt.error_tags or []),
            "created_at": attempt.created_at.isoformat(),
        }
        for attempt, question in rows
    ]


def _grading_result(context: AgentContext) -> dict[str, Any]:
    if not context.attempt_id:
        raise ValueError("attempt_id required post submit")
    with SessionLocal() as session:
        attempt = session.get(AttemptModel, context.attempt_id)
        if not attempt or attempt.learner_id != context.learner_id:
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


def _record_explicit_confusion(context: AgentContext, run_id: str) -> str | None:
    with SessionLocal() as session:
        question = session.get(QuestionModel, context.question_id)
        if question is None:
            return None
        item = learning_memory_service.record_explicit_confusion(
            session,
            learner_id=context.learner_id,
            question=question,
            message=context.user_message,
            tutor_run_id=run_id,
        )
        if item is None:
            return None
        session.commit()
        return item.memory_id


def build_tutor_dependencies() -> TutorDependencies:
    return TutorDependencies(
        question_context=_question_context,
        retrieve_knowledge=_retrieve_knowledge,
        learning_profile=_learning_profile,
        learning_memory=_learning_memory,
        recent_mistakes=_recent_mistakes,
        grading_result=_grading_result,
        answer_explanation=_answer_explanation,
        public_source=_public_source,
        record_explicit_confusion=_record_explicit_confusion,
    )


def configured_tutor_gateway() -> ModelGateway:
    from app.services.runtime_settings_service import runtime_settings_service

    runtime_settings_service.sync()
    runtime_override = bool(runtime_settings_service.llm_public()["runtime_override"])
    if (os.getenv("TUTOR_PROVIDER_ENABLED", "").strip().lower() == "true" or runtime_override) and config.LLM_BASE_URL and config.LLM_API_KEY:
        return OpenAICompatibleTutorGateway()
    return LocalPolicyModelGateway()
