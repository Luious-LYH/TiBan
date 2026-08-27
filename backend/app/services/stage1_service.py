from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.core.config import SAFETY_NOTICE
from app.db.database import SessionLocal
from app.db.repositories import Stage1Repository
from app.db.serializers import grading_question_payload, public_bank_payload, public_question_payload
from app.schemas import FactFeedbackPublic, PracticeSubmitRequest, PracticeSubmitResponse


class Stage1Service:
    def _repository(self) -> tuple[Any, Stage1Repository]:
        session = SessionLocal()
        repository = Stage1Repository(session)
        repository.ensure_seeded()
        return session, repository

    def list_banks(self, learner_id: str = "demo_learner") -> list[dict[str, Any]]:
        session, repository = self._repository()
        try:
            return [
                public_bank_payload(bank, getattr(bank, "_stage1_completed_count", 0))
                for bank in repository.list_banks(learner_id)
            ]
        finally:
            session.close()

    def list_public_questions(
        self,
        *,
        bank_id: str | None = None,
        question_type: str | None = None,
        body_part: str | None = None,
        search: str | None = None,
        limit: int = 18,
        offset: int = 0,
        legacy: bool = False,
    ) -> list[dict[str, Any]]:
        session, repository = self._repository()
        try:
            questions = repository.list_questions(
                bank_id=bank_id,
                question_type=question_type,
                body_part=body_part,
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

    def create_session(self, learner_id: str, bank_id: str, mode: str = "practice") -> dict[str, Any]:
        session, repository = self._repository()
        try:
            created = repository.create_session(learner_id, bank_id, mode)
            return {
                "session_id": created.session_id,
                "learner_id": created.learner_id,
                "bank_id": created.bank_id,
                "mode": created.mode,
                "status": created.status,
                "started_at": created.started_at,
            }
        finally:
            session.close()

    def submit(self, request: PracticeSubmitRequest) -> PracticeSubmitResponse:
        session, repository = self._repository()
        try:
            question = repository.get_question(request.question_id)
            bank_id = question.bank_id
            practice_session = repository.get_or_create_session(
                request.learner_id,
                bank_id,
                request.session_id,
            )
            grading = grading_question_payload(question)
            normalized = self._normalize_submission(request.selected_answer, grading)
            score, correct, error_tags = self._grade(question, grading, normalized)
            attempt = repository.record_attempt(
                session=practice_session,
                question=question,
                selected_answer=normalized,
                score=score,
                correct=correct,
                error_tags=error_tags,
                hint_count=request.hint_count,
                duration_ms=request.duration_ms,
            )
            facts = list(question.expected_keywords or question.teaching_tags or [])[:4]
            feedback = [
                FactFeedbackPublic(
                    fact=fact,
                    supported=correct or index == 0,
                    note="已按当前题型评分规则记录；提交后的学习状态由服务端 workflow 更新。",
                )
                for index, fact in enumerate(facts)
            ]
            explanation = self._explanation(question.question_type, correct, score, error_tags)
            return PracticeSubmitResponse(
                attempt_id=attempt.attempt_id,
                question_id=question.question_id,
                session_id=practice_session.session_id,
                learner_id=request.learner_id,
                is_correct=correct,
                score=score,
                error_tags=error_tags,
                fact_feedback=feedback,
                explanation=explanation,
                next_recommendation="可继续下一题；错题已进入复盘队列。" if not correct else "可以继续下一题，系统已记录本次练习。",
                profile_updated=True,
                doctor_review_required=True,
                safety_notice=SAFETY_NOTICE,
                created_at=attempt.created_at,
            )
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

    def _explanation(self, question_type: str, correct: bool, score: int, error_tags: list[str]) -> str:
        if correct:
            return f"本次 {question_type} 提交已通过当前确定性评分规则（{score} 分）。结果仅用于教学训练和复盘。"
        return f"本次提交得分 {score}。请回到题干与图像证据，检查选项判断和观察边界；记录的复盘标签：{'、'.join(error_tags)}。"

    def _split(self, value: str) -> list[str]:
        return [item.strip() for item in re.split(r"[；;,]", value) if item.strip()]


stage1_service = Stage1Service()
