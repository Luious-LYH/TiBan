from __future__ import annotations

from datetime import datetime
from collections import Counter
import random
from typing import Any
from uuid import uuid4

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import SAFETY_NOTICE

from .models import (
    AttemptModel,
    LearningMemoryItemModel,
    LearnerMasteryModel,
    PracticeSessionItemModel,
    PracticeSessionModel,
    QuestionBankModel,
    QuestionModel,
    ReviewCardModel,
)
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
        banks = list(self.session.scalars(select(QuestionBankModel)).all())
        type_rows = self.session.execute(
            select(QuestionModel.bank_id, QuestionModel.question_type, func.count(QuestionModel.question_id))
            .where(QuestionModel.business_usage == "user_ready")
            .group_by(QuestionModel.bank_id, QuestionModel.question_type)
        ).all()
        modality_rows = self.session.execute(
            select(QuestionModel.bank_id, QuestionModel.modality, func.count(QuestionModel.question_id))
            .where(QuestionModel.business_usage == "user_ready")
            .group_by(QuestionModel.bank_id, QuestionModel.modality)
        ).all()
        body_rows = self.session.execute(
            select(QuestionModel.bank_id, QuestionModel.body_part)
            .where(QuestionModel.business_usage == "user_ready")
            .distinct()
        ).all()
        types_by_bank: dict[str, dict[str, int]] = {}
        for bank_id, question_type, count in type_rows:
            types_by_bank.setdefault(str(bank_id), {})[str(question_type)] = int(count)
        modalities_by_bank: dict[str, dict[str, int]] = {}
        for bank_id, modality, count in modality_rows:
            modalities_by_bank.setdefault(str(bank_id), {})[str(modality)] = int(count)
        bodies_by_bank: dict[str, list[str]] = {}
        for bank_id, body_part in body_rows:
            bodies_by_bank.setdefault(str(bank_id), []).append(str(body_part))

        inventory_changed = False
        for bank in banks:
            type_counts = types_by_bank.get(bank.bank_id, {})
            modality_counts = modalities_by_bank.get(bank.bank_id, {})
            body_parts = sorted(bodies_by_bank.get(bank.bank_id, []))
            question_count = sum(type_counts.values())
            if (
                bank.question_count != question_count
                or dict(bank.question_type_counts or {}) != type_counts
                or dict(bank.modality_counts or {}) != modality_counts
                or list(bank.body_parts or []) != body_parts
            ):
                bank.question_count = question_count
                bank.question_type_counts = type_counts
                bank.modality_counts = modality_counts
                bank.body_parts = body_parts
                inventory_changed = True
        if benchmark_rows or inventory_changed:
            # Quarantine and inventory are data-policy projections, not
            # response-only filters. Persist them so a fresh process cannot
            # expose benchmark rows or stale zero-question counts.
            self.session.commit()

    def list_banks(self, learner_id: str = "demo_learner") -> list[QuestionBankModel]:
        self.ensure_seeded()
        banks = list(
            self.session.scalars(
                select(QuestionBankModel)
                .where(QuestionBankModel.question_count > 0)
                .order_by(QuestionBankModel.name)
            )
        )
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
        if not bank or bank.question_count <= 0:
            raise KeyError(f"Question bank not found: {bank_id}")
        return bank

    def list_questions(
        self,
        *,
        bank_id: str | None = None,
        question_type: str | None = None,
        body_part: str | None = None,
        subject: str | None = None,
        topic: str | None = None,
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
        if subject:
            statement = statement.where(QuestionModel.subject == subject)
        if topic:
            statement = statement.where(QuestionModel.topic == topic)
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

    def create_session(
        self,
        learner_id: str,
        bank_id: str,
        mode: str = "practice",
        question_count: int = 20,
        shuffle_seed: int | None = None,
    ) -> tuple[PracticeSessionModel, dict[str, Any]]:
        self.get_bank(bank_id)
        questions = list(
            self.session.scalars(
                select(QuestionModel)
                .where(QuestionModel.bank_id == bank_id, QuestionModel.business_usage == "user_ready")
                .order_by(QuestionModel.question_id)
            )
        )
        if not questions:
            raise KeyError(f"No learner-ready questions in bank: {bank_id}")
        selection_size = min(max(question_count, 1), len(questions))
        selected_ids, selection = self._select_adaptive_session_questions(
            learner_id=learner_id,
            bank_id=bank_id,
            questions=questions,
            selection_size=selection_size,
            shuffle_seed=shuffle_seed,
        )
        session = PracticeSessionModel(
            session_id=f"session_{uuid4().hex[:12]}",
            learner_id=learner_id,
            bank_id=bank_id,
            mode=mode,
            status="active",
        )
        self.session.add(session)
        self.session.flush()
        self.session.add_all(
            [
                PracticeSessionItemModel(
                    session_item_id=f"session_item_{uuid4().hex[:12]}",
                    practice_session_id=session.session_id,
                    question_id=question_id,
                    ordinal=ordinal,
                )
                for ordinal, question_id in enumerate(selected_ids)
            ]
        )
        self.session.commit()
        self.session.refresh(session)
        return session, selection

    def _select_adaptive_session_questions(
        self,
        *,
        learner_id: str,
        bank_id: str,
        questions: list[QuestionModel],
        selection_size: int,
        shuffle_seed: int | None,
    ) -> tuple[list[str], dict[str, Any]]:
        """Select a bounded session from existing deterministic learner state.

        No selection result is stored as a second LearningState record.  The
        immutable attempts, derived mastery rows and FSRS cards remain the
        sources of truth; the returned reason is a transparent projection of
        the choice made at this session boundary.
        """

        question_ids = [question.question_id for question in questions]
        now = datetime.utcnow()
        attempt_rows = list(
            self.session.execute(
                select(AttemptModel, QuestionModel)
                .join(QuestionModel, QuestionModel.question_id == AttemptModel.question_id)
                .where(
                    AttemptModel.learner_id == learner_id,
                    QuestionModel.bank_id == bank_id,
                    QuestionModel.business_usage == "user_ready",
                )
                .order_by(AttemptModel.created_at.desc())
            ).all()
        )
        attempted_ids = {attempt.question_id for attempt, _ in attempt_rows}
        error_count_by_point: Counter[str] = Counter()
        for attempt, question in attempt_rows:
            if not attempt.correct:
                error_count_by_point.update(self._question_points(question))

        mastery_by_point = {
            row.knowledge_point: row
            for row in self.session.scalars(
                select(LearnerMasteryModel).where(LearnerMasteryModel.learner_id == learner_id)
            )
            if row.attempt_count > 0
        }
        due_by_question = {
            row.question_id: row
            for row in self.session.scalars(
                select(ReviewCardModel).where(
                    ReviewCardModel.learner_id == learner_id,
                    ReviewCardModel.question_id.in_(question_ids),
                )
            )
            if row.due_at <= now
        }
        active_memory = list(
            self.session.scalars(
                select(LearningMemoryItemModel).where(
                    LearningMemoryItemModel.learner_id == learner_id,
                    LearningMemoryItemModel.status == "active",
                )
            )
        )

        # A supplied seed preserves reproducibility for scale/acceptance runs.
        # Normal sessions may rotate otherwise-equivalent coverage questions,
        # but never bypass due-review or weak-topic priority tiers.
        rng = random.Random(shuffle_seed) if shuffle_seed is not None else random.SystemRandom()
        tie_breakers = {question.question_id: rng.random() for question in questions}

        def weak_records(question: QuestionModel) -> list[LearnerMasteryModel]:
            return [
                mastery_by_point[point]
                for point in self._question_points(question)
                if point in mastery_by_point and mastery_by_point[point].mastery_score < 80
            ]

        def memory_records(question: QuestionModel) -> list[LearningMemoryItemModel]:
            question_keys = self._question_points(question)
            if question.topic:
                question_keys.add(question.topic)
            return [
                item
                for item in active_memory
                if question_keys & {str(key) for key in (item.topic_keys or [])}
            ]

        def rank(question: QuestionModel) -> tuple[int, float, int, float]:
            due = due_by_question.get(question.question_id)
            if due is not None:
                return (0, due.due_at.timestamp(), 0, tie_breakers[question.question_id])
            memories = memory_records(question)
            if memories:
                latest = max(memories, key=lambda row: row.last_seen_at)
                return (1, -latest.last_seen_at.timestamp(), -len(memories), tie_breakers[question.question_id])
            weak = weak_records(question)
            if weak:
                weakest = min(weak, key=lambda row: row.mastery_score)
                return (
                    2,
                    weakest.mastery_score,
                    -max(error_count_by_point.get(point, 0) for point in self._question_points(question)),
                    tie_breakers[question.question_id],
                )
            if question.question_id not in attempted_ids:
                return (3, 0, 0, tie_breakers[question.question_id])
            return (4, 0, 0, tie_breakers[question.question_id])

        selected = sorted(questions, key=rank)[:selection_size]
        selected_due = [question for question in selected if question.question_id in due_by_question]
        selected_memory = [question for question in selected if memory_records(question)]
        selected_weak = [question for question in selected if weak_records(question)]
        selected_unseen = [question for question in selected if question.question_id not in attempted_ids]

        if selected_due:
            strategy = "due_review"
            evidence = [f"优先放入 {len(selected_due)} 道已到复习时间的题目。"]
            if selected_unseen:
                evidence.append(f"其余题目中补入 {len(selected_unseen)} 道未练题，保持题库覆盖。")
            reason = "本次先安排到期复习，再补齐尚未覆盖的练习。"
        elif selected_memory:
            selected_item = memory_records(selected_memory[0])[0]
            strategy = "learning_memory"
            evidence = [f"结合已记录的学习事实：{selected_item.summary}"]
            if selected_unseen:
                evidence.append(f"同时保留 {len(selected_unseen)} 道未练题，避免只重复单一知识点。")
            reason = "本次优先巩固近期需要加强的概念，再维持题库覆盖。"
        elif selected_weak:
            strategy = "weak_topic"
            focus = min(
                (
                    row
                    for question in selected_weak
                    for row in weak_records(question)
                ),
                key=lambda row: row.mastery_score,
            )
            errors = error_count_by_point.get(focus.knowledge_point, 0)
            evidence = [
                f"「{focus.knowledge_point}」当前掌握度 {focus.mastery_score:.1f}%。",
                f"该知识点已有 {focus.attempt_count} 次练习，累计错误 {errors} 次。",
            ]
            if selected_unseen:
                evidence.append(f"同时保留 {len(selected_unseen)} 道未练题，避免只重复单一知识点。")
            reason = f"优先巩固「{focus.knowledge_point}」相关题目，再维持题库覆盖。"
        else:
            strategy = "coverage"
            evidence = [f"当前没有到期复习或显著薄弱项，优先安排 {len(selected_unseen)} 道未练题。"]
            reason = "本次按未练题与题库覆盖安排练习。"

        return [question.question_id for question in selected], {
            "selection_strategy": strategy,
            "selection_reason": reason,
            "selection_evidence": evidence,
        }

    @staticmethod
    def _question_points(question: QuestionModel) -> set[str]:
        return {str(item).strip() for item in (question.teaching_tags or [question.body_part]) if str(item).strip()}

    def get_or_create_session(self, learner_id: str, bank_id: str, session_id: str | None, mode: str = "practice") -> PracticeSessionModel:
        if session_id:
            current = self.session.get(PracticeSessionModel, session_id)
            if current and current.learner_id == learner_id and current.bank_id == bank_id:
                return current
        created, _ = self.create_session(learner_id, bank_id, mode)
        return created

    def session_questions(self, session_id: str) -> list[QuestionModel]:
        """Return persisted server membership in its authoritative order."""

        return list(
            self.session.scalars(
                select(QuestionModel)
                .join(PracticeSessionItemModel, PracticeSessionItemModel.question_id == QuestionModel.question_id)
                .where(PracticeSessionItemModel.practice_session_id == session_id)
                .order_by(PracticeSessionItemModel.ordinal)
            )
        )

    def session_items(self, session_id: str) -> list[dict[str, object]]:
        session = self.session.get(PracticeSessionModel, session_id)
        if session is None:
            raise KeyError(f"Practice session not found: {session_id}")
        items = list(
            self.session.scalars(
                select(PracticeSessionItemModel)
                .where(PracticeSessionItemModel.practice_session_id == session_id)
                .order_by(PracticeSessionItemModel.ordinal)
            )
        )
        attempts = list(
            self.session.scalars(
                select(AttemptModel)
                .where(AttemptModel.practice_session_id == session_id)
                .order_by(AttemptModel.created_at.desc())
            )
        )
        latest_by_question: dict[str, AttemptModel] = {}
        for attempt in attempts:
            latest_by_question.setdefault(attempt.question_id, attempt)
        return [
            {
                "question_id": item.question_id,
                "ordinal": item.ordinal,
                "state": "unanswered" if item.question_id not in latest_by_question else ("correct" if latest_by_question[item.question_id].correct else "incorrect"),
            }
            for item in items
        ]

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
