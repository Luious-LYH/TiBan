from __future__ import annotations

from datetime import datetime
from collections import Counter
from typing import Any
from uuid import uuid4

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import SAFETY_NOTICE

from .models import AttemptModel, PracticeSessionModel, QuestionBankModel, QuestionModel, ReviewCardModel
from .seed import TYPE_CODE, TYPE_LABEL, seed_database


class Stage1Repository:
    def __init__(self, session: Session):
        self.session = session

    def ensure_seeded(self) -> None:
        seed_database(self.session)
        # Legacy seed rows included benchmark and research samples before
        # Stage 2.5. Keep them for evaluation/audit history, but remove all
        # non-user-ready rows from product catalog counts and learner queries.
        benchmark_rows = list(self.session.scalars(select(QuestionModel).where(QuestionModel.source_dataset == "EndoBench")))
        for question in benchmark_rows:
            question.business_usage = "benchmark_only"
            question.derived_from_dataset = "EndoBench"
            question.license_gate_status = "allow_noncommercial"
            question.source_uri = "https://github.com/medAI-NEU/EndoBench"
        if benchmark_rows:
            for bank in self.session.scalars(select(QuestionBankModel)).all():
                visible = list(self.session.scalars(select(QuestionModel).where(QuestionModel.bank_id == bank.bank_id, QuestionModel.business_usage == "user_ready")))
                bank.question_count = len(visible)
                bank.question_type_counts = dict(Counter(item.question_type for item in visible))
                bank.modality_counts = dict(Counter(item.modality for item in visible))
                bank.body_parts = sorted({item.body_part for item in visible})
            # Quarantine is a data-policy migration, not a response-only
            # projection. Persist it so a fresh process cannot expose legacy
            # benchmark/research rows before the next repository read.
            self.session.commit()

    def list_banks(self, learner_id: str = "demo_learner") -> list[QuestionBankModel]:
        self.ensure_seeded()
        banks = list(self.session.scalars(select(QuestionBankModel).order_by(QuestionBankModel.name)))
        for bank in banks:
            completed = self.session.scalar(
                select(func.count(func.distinct(AttemptModel.question_id)))
                .join(QuestionModel, QuestionModel.question_id == AttemptModel.question_id)
                .where(
                    AttemptModel.learner_id == learner_id,
                    QuestionModel.bank_id == bank.bank_id,
                    QuestionModel.business_usage == "user_ready",
                )
            ) or 0
            bank._stage1_completed_count = int(completed)
        return banks

    def get_bank(self, bank_id: str) -> QuestionBankModel:
        self.ensure_seeded()
        bank = self.session.get(QuestionBankModel, bank_id)
        if not bank:
            raise KeyError(f"Question bank not found: {bank_id}")
        return bank

    def list_questions(
        self,
        *,
        bank_id: str | None = None,
        question_type: str | None = None,
        body_part: str | None = None,
        search: str | None = None,
        limit: int = 18,
        offset: int = 0,
    ) -> list[QuestionModel]:
        self.ensure_seeded()
        statement = select(QuestionModel).where(QuestionModel.business_usage == "user_ready").order_by(
            # Keep the legacy compatibility endpoint representative while
            # bank-scoped Stage 2.5 sessions still filter deterministically.
            case(
                (QuestionModel.source_dataset.not_in(["CMExam", "CMB-Exam", "Kvasir-VQA"]), 0),
                (QuestionModel.modality == "image", 1),
                else_=2,
            ),
            QuestionModel.question_id,
        )
        if bank_id:
            statement = statement.where(QuestionModel.bank_id == bank_id)
        if question_type:
            code = TYPE_CODE.get(question_type, question_type if question_type in TYPE_LABEL else None)
            if code:
                statement = statement.where(QuestionModel.question_type == code)
        if body_part:
            statement = statement.where(QuestionModel.body_part == body_part)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                QuestionModel.title.ilike(pattern) | QuestionModel.stem.ilike(pattern) | QuestionModel.body_part.ilike(pattern)
            )
        return list(self.session.scalars(statement.offset(max(offset, 0)).limit(max(min(limit, 100), 1))))

    def get_question(self, question_id: str) -> QuestionModel:
        self.ensure_seeded()
        question = self.session.get(QuestionModel, question_id)
        if not question:
            raise KeyError(f"Question not found: {question_id}")
        return question

    def create_session(self, learner_id: str, bank_id: str, mode: str = "practice") -> PracticeSessionModel:
        self.get_bank(bank_id)
        session = PracticeSessionModel(
            session_id=f"session_{uuid4().hex[:12]}",
            learner_id=learner_id,
            bank_id=bank_id,
            mode=mode,
            status="active",
        )
        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)
        return session

    def get_or_create_session(self, learner_id: str, bank_id: str, session_id: str | None, mode: str = "practice") -> PracticeSessionModel:
        if session_id:
            current = self.session.get(PracticeSessionModel, session_id)
            if current and current.learner_id == learner_id and current.bank_id == bank_id:
                return current
        return self.create_session(learner_id, bank_id, mode)

    def record_attempt(
        self,
        *,
        session: PracticeSessionModel,
        question: QuestionModel,
        selected_answer: Any,
        score: int,
        correct: bool,
        error_tags: list[str],
        hint_count: int = 0,
        duration_ms: int | None = None,
    ) -> AttemptModel:
        now = datetime.utcnow()
        attempt = AttemptModel(
            attempt_id=f"attempt_{uuid4().hex[:12]}",
            practice_session_id=session.session_id,
            question_id=question.question_id,
            learner_id=session.learner_id,
            selected_answer=selected_answer,
            score=score,
            correct=correct,
            error_tags=error_tags,
            hint_count=hint_count,
            duration_ms=duration_ms,
            created_at=now,
        )
        self.session.add(attempt)
        session.last_active_at = now
        # The submit workflow owns the only side effects: once the immutable
        # attempt is staged, derive mastery and FSRS scheduling deterministically.
        self.session.flush()
        from app.services.learning_service import apply_learning_outcome
        apply_learning_outcome(self.session, attempt=attempt, question=question, now=now)
        self.session.commit()
        self.session.refresh(attempt)
        return attempt

    def overview(self, learner_id: str = "demo_learner") -> dict[str, Any]:
        banks = self.list_banks(learner_id)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        completed_today = self.session.scalar(
            select(func.count(AttemptModel.attempt_id)).where(
                AttemptModel.learner_id == learner_id,
                AttemptModel.created_at >= today_start,
            )
        ) or 0
        recent_attempts = list(
            self.session.scalars(
                select(AttemptModel)
                .where(AttemptModel.learner_id == learner_id)
                .order_by(AttemptModel.created_at.desc())
                .limit(10)
            )
        )
        due_count = self.session.scalar(
            select(func.count(ReviewCardModel.review_card_id)).where(
                ReviewCardModel.learner_id == learner_id,
                ReviewCardModel.due_at <= datetime.utcnow(),
            )
        ) or 0
        recent_accuracy = (
            sum(1 for item in recent_attempts if item.correct) / len(recent_attempts)
            if recent_attempts
            else 0.0
        )
        return {
            "learner_id": learner_id,
            "completed_today": int(completed_today),
            "daily_target": 10,
            "due_review_count": int(due_count),
            "recent_accuracy": round(recent_accuracy, 3),
            "recent_sessions": [
                {
                    "attempt_id": item.attempt_id,
                    "question_id": item.question_id,
                    "score": item.score,
                    "correct": item.correct,
                    "created_at": item.created_at.isoformat(),
                }
                for item in recent_attempts
            ],
            "banks": banks,
            "weak_areas": sorted({tag for item in recent_attempts for tag in (item.error_tags or [])}),
            "safety_notice": SAFETY_NOTICE,
            "api_source": "backend",
        }
