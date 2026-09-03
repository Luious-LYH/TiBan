from __future__ import annotations

import re
from datetime import datetime
from time import perf_counter
from contextvars import ContextVar
from typing import Any

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import PracticeSessionModel, TutorThreadModel
from app.db.repositories import Stage1Repository
from app.db.serializers import grading_question_payload, public_bank_payload, public_question_payload
from app.domains import get_domain
from app.schemas import FactFeedbackPublic, PracticeSubmitRequest, PracticeSubmitResponse


submit_timing_context: ContextVar[dict[str, float]] = ContextVar("submit_timing_context", default={})


class Stage1Service:
    def _repository(self) -> tuple[Any, Stage1Repository]:
        session = SessionLocal()
        repository = Stage1Repository(session)
        repository.ensure_seeded()
        return session, repository

    def list_banks(self, learner_id: str = "demo_learner", domain_id: str | None = None) -> list[dict[str, Any]]:
        session, repository = self._repository()
        try:
            return [
                public_bank_payload(bank, getattr(bank, "_stage1_completed_count", 0))
                for bank in repository.list_banks(learner_id, domain_id)
            ]
        finally:
            session.close()

    def list_public_questions(
        self,
        *,
        bank_id: str | None = None,
        domain_id: str | None = None,
        question_type: str | None = None,
        body_part: str | None = None,
        subject: str | None = None,
        topic: str | None = None,
        search: str | None = None,
        session_id: str | None = None,
        limit: int = 18,
        offset: int = 0,
        legacy: bool = False,
    ) -> list[dict[str, Any]]:
        session, repository = self._repository()
        try:
            if session_id:
                practice_session = session.get(PracticeSessionModel, session_id)
                if practice_session is None:
                    raise KeyError(session_id)
                if bank_id and practice_session.bank_id != bank_id:
                    raise KeyError(session_id)
                questions = [
                    question
                    for question in repository.session_questions(session_id)
                    if self._matches_question_filters(
                        question,
                        domain_id=domain_id,
                        question_type=question_type,
                        body_part=body_part,
                        subject=subject,
                        topic=topic,
                        search=search,
                    )
                ]
                questions = questions[max(offset, 0): max(offset, 0) + max(min(limit, 100), 1)]
            else:
                questions = repository.list_questions(
                    bank_id=bank_id,
                    domain_id=domain_id,
                    question_type=question_type,
                    body_part=body_part,
                    subject=subject,
                    topic=topic,
                    search=search,
                    limit=limit,
                    offset=offset,
                )
            if legacy:
                from app.db.serializers import legacy_question_payload

                return [legacy_question_payload(question) for question in questions]
            return [public_question_payload(question) for question in questions]
        finally:
            session.close()

    def public_question(self, question_id: str, *, legacy: bool = False) -> dict[str, Any]:
        session, repository = self._repository()
        try:
            question = repository.get_question(question_id)
            if legacy:
                from app.db.serializers import legacy_question_payload

                return legacy_question_payload(question)
            return public_question_payload(question)
        finally:
            session.close()

    def create_session(
        self,
        learner_id: str,
        bank_id: str,
        mode: str = "practice",
        question_count: int = 20,
        shuffle_seed: int | None = None,
        question_scope: str = "all",
    ) -> dict[str, Any]:
        session, repository = self._repository()
        try:
            created, selection = repository.create_session(learner_id, bank_id, mode, question_count, shuffle_seed, question_scope)
            items = repository.session_items(created.session_id)
            from app.services.practice_session_service import practice_session_service
            practice_session_service.abandon_other_active(learner_id=learner_id, except_session_id=created.session_id)
            tutor_thread = practice_session_service.create_tutor_thread(session_id=created.session_id, learner_id=learner_id)
            return {
                "session_id": created.session_id,
                "learner_id": created.learner_id,
                "bank_id": created.bank_id,
                "domain_id": created.domain_id,
                "mode": created.mode,
                "status": created.status,
                "started_at": created.started_at,
                "current_position": created.current_position,
                "reflection_status": created.reflection_status,
                "tutor_thread_id": tutor_thread["tutor_thread_id"],
                "question_count": len(items),
                "question_ids": [str(item["question_id"]) for item in items],
                **selection,
            }
        finally:
            session.close()

    def session_detail(self, session_id: str, state: str | None = None) -> dict[str, Any]:
        session, repository = self._repository()
        try:
            created = session.get(PracticeSessionModel, session_id)
            if created is None:
                raise KeyError(session_id)
            items = repository.session_items(session_id)
            if state is not None:
                items = [item for item in items if item["state"] == state]
            active_thread = session.scalar(select(TutorThreadModel).where(
                TutorThreadModel.practice_session_id == created.session_id,
                TutorThreadModel.learner_id == created.learner_id,
                TutorThreadModel.status == "active",
            ).order_by(TutorThreadModel.last_active_at.desc()))
            return {
                "session_id": created.session_id,
                "learner_id": created.learner_id,
                "bank_id": created.bank_id,
                "domain_id": created.domain_id,
                "mode": created.mode,
                "status": created.status,
                "started_at": created.started_at,
                "current_position": created.current_position,
                "reflection_status": created.reflection_status,
                "tutor_thread_id": active_thread.tutor_thread_id if active_thread else None,
                "question_count": len(items),
                "question_ids": [str(item["question_id"]) for item in items],
                "items": items,
            }
        finally:
            session.close()

    def submit(self, request: PracticeSubmitRequest) -> PracticeSubmitResponse:
        started = perf_counter()
        timings: dict[str, float] = {"request_receive_ms": 0.0}
        session, repository = self._repository()
        try:
            mark = perf_counter()
            question = repository.get_question(request.question_id)
            timings["question_load_ms"] = round((perf_counter() - mark) * 1000, 3)
            bank_id = question.bank_id
            mark = perf_counter()
            practice_session = repository.get_or_create_session(
                request.learner_id,
                bank_id,
                request.session_id,
                request.mode,
                question_id=request.question_id,
            )
            timings["session_load_ms"] = round((perf_counter() - mark) * 1000, 3)
            mark = perf_counter()
            grading = grading_question_payload(question)
            normalized = self._normalize_submission(request.selected_answer, grading)
            score, correct, error_tags = self._grade(question, grading, normalized)
            timings["grade_ms"] = round((perf_counter() - mark) * 1000, 3)
            mark = perf_counter()
            attempt = repository.record_attempt(
                session=practice_session,
                question=question,
                selected_answer=normalized,
                score=score,
                correct=correct,
                error_tags=error_tags,
                hint_count=request.hint_count,
                duration_ms=request.duration_ms,
                timings=timings,
            )
            timings["attempt_workflow_ms"] = round((perf_counter() - mark) * 1000, 3)
            # Reflection only observes already committed deterministic state.
            # This tiny lifecycle write/queue handoff never invokes LLM, RAG or
            # embeddings on the submit path.
            from app.services.practice_session_service import practice_session_service
            practice_session_service.after_submission(session_id=practice_session.session_id, question_id=question.question_id)
            # Long-term memory is deliberately not written on the objective
            # submit path. Keep the timing contract explicit with a zero-cost
            # phase so callers can distinguish "not run" from a missing
            # measurement; Reflection observes the committed state later.
            timings["memory_update_ms"] = 0.0
            mark = perf_counter()
            facts = list(question.expected_keywords or question.teaching_tags or [])[:4]
            feedback = [
                FactFeedbackPublic(
                    fact=fact,
                    supported=correct or index == 0,
                    note="已按当前题型评分规则记录；提交后的学习状态由服务端 workflow 更新。",
                )
                for index, fact in enumerate(facts)
            ]
            exam_locked = request.mode == "exam"
            explanation = "考试进行中；提交本题后暂不显示正确答案和解析，结束后统一复盘。" if exam_locked else self._explanation(question, correct, score, error_tags)
            selected_display, correct_display = self._answer_displays(grading, normalized)
            response = PracticeSubmitResponse(
                attempt_id=attempt.attempt_id,
                question_id=question.question_id,
                session_id=practice_session.session_id,
                learner_id=request.learner_id,
                is_correct=correct,
                score=score,
                error_tags=error_tags,
                fact_feedback=feedback,
                explanation=explanation,
                next_recommendation=(
                    "可继续下一题；错题已进入复盘队列。"
                    if not correct
                    else "可以继续下一题，系统已记录本次练习。"
                ),
                profile_updated=True,
                doctor_review_required=question.doctor_review_required,
                safety_notice=question.safety_notice or get_domain(question.domain_id).learner_notice,
                created_at=attempt.created_at,
                selected_answer=normalized,
                selected_answer_display=selected_display,
                correct_answer_display="考试结束后显示" if exam_locked else correct_display,
                answer_source=question.answer_source if question.answer_source in {"dataset_gold", "human_verified", "generated"} else "dataset_gold",
                explanation_source=question.explanation_source if question.explanation_source in {"dataset_gold", "rag_generated", "human_curated", "none"} else "none",
                official_explanation_available=False if exam_locked else bool(question.official_explanation_available and (question.explanation or "").strip()),
            )
            timings["serialize_ms"] = round((perf_counter() - mark) * 1000, 3)
            timings["request_total_ms"] = round((perf_counter() - started) * 1000, 3)
            submit_timing_context.set(timings)
            return response
        finally:
            session.close()

    def overview(self, learner_id: str = "demo_learner") -> dict[str, Any]:
        session, repository = self._repository()
        try:
            payload = repository.overview(learner_id)
            # Keep ORM instances behind the repository boundary.  The canonical
            # overview contract is also consumed by the frontend and must be
            # serializable without SQLAlchemy internals leaking into it.
            payload["banks"] = [
                public_bank_payload(bank, getattr(bank, "_stage1_completed_count", 0))
                for bank in payload.get("banks", [])
            ]
            return payload
        finally:
            session.close()

    def _normalize_submission(self, value: Any, grading: dict[str, Any]) -> Any:
        question_type = grading["question_type"]
        if question_type == "multiple_choice":
            raw = value if isinstance(value, list) else self._split(str(value))
            options = {item["id"]: item["text"] for item in grading.get("options", [])}
            by_text = {text: option_id for option_id, text in options.items()}
            return sorted({by_text.get(str(item), str(item)) for item in raw if str(item).strip()})
        if question_type == "true_false":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"true", "1", "正确", "是", "yes"}
        return str(value).strip()

    @staticmethod
    def _matches_question_filters(
        question: Any,
        *,
        domain_id: str | None,
        question_type: str | None,
        body_part: str | None,
        subject: str | None,
        topic: str | None,
        search: str | None,
    ) -> bool:
        if domain_id and question.domain_id != domain_id:
            return False
        if question_type and question.question_type != question_type:
            return False
        if body_part and question.body_part != body_part:
            return False
        if subject and question.subject != subject:
            return False
        if topic and question.topic != topic:
            return False
        if search:
            query = search.strip().lower()
            if query and query not in " ".join(
                str(value or "") for value in (question.title, question.stem, question.body_part)
            ).lower():
                return False
        return True

    def _grade(self, question: Any, grading: dict[str, Any], selected: Any) -> tuple[int, bool, list[str]]:
        question_type = grading["question_type"]
        correct = False
        if question_type == "single_choice":
            selected_id = selected
            if selected_id not in {item["id"] for item in grading.get("options", [])}:
                selected_id = next((item["id"] for item in grading.get("options", []) if item["text"] == selected), selected)
            correct = selected_id == grading["correct_option_id"]
        elif question_type == "multiple_choice":
            correct = set(selected) == set(grading["correct_option_ids"])
        elif question_type == "true_false":
            correct = selected is grading["correct_value"]
        else:
            text = str(selected)
            expected = [str(item) for item in grading.get("expected_facts", []) if str(item).strip()]
            matched = sum(1 for item in expected if item in text)
            score = round(matched / max(len(expected), 1) * 88)
            if any(token in text for token in ["复核", "结合", "完整检查", "病理"]):
                score += 12
            if any(token in text for token in ["确诊", "治疗方案", "必须手术", "开药"]):
                score -= 35
            score = max(0, min(100, score))
            correct = score >= 80
            return score, correct, [] if correct else ["观察依据不足"]
        return (100 if correct else 0), correct, [] if correct else ["答案与当前评分规则不一致"]

    def _explanation(self, question: Any, correct: bool, score: int, error_tags: list[str]) -> str:
        # Objective-question feedback must never turn grading internals into a
        # learner-facing "explanation".  Only stored, governed explanations are
        # surfaced here; the UI offers the existing Tutor for a guided walkthrough
        # when a source bank did not provide one.
        if question.official_explanation_available:
            return (question.explanation or "").strip()
        return ""

    def _answer_displays(self, grading: dict[str, Any], selected: Any) -> tuple[str, str]:
        question_type = grading["question_type"]
        options = {item["id"]: item["text"] for item in grading.get("options", [])}
        if question_type == "single_choice":
            return options.get(str(selected), str(selected)), options.get(grading["correct_option_id"], grading["correct_option_id"])
        if question_type == "multiple_choice":
            selected_ids = selected if isinstance(selected, list) else [selected]
            correct_ids = grading.get("correct_option_ids", [])
            selected_text = "、".join(options.get(str(item), str(item)) for item in selected_ids)
            correct_text = "、".join(options.get(str(item), str(item)) for item in correct_ids)
            return selected_text, correct_text
        if question_type == "true_false":
            display = lambda value: "正确" if bool(value) else "错误"
            return display(selected), display(grading["correct_value"])
        return str(selected), "参考答案见题目解析与评分 rubric"

    def _split(self, value: str) -> list[str]:
        return [item.strip() for item in re.split(r"[；;,]", value) if item.strip()]


stage1_service = Stage1Service()
