from __future__ import annotations

from datetime import datetime
from collections import Counter
import random
import re
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
    QuestionMarkModel,
    QuestionModel,
    ReviewCardModel,
)
from .seed import TYPE_CODE, TYPE_LABEL, seed_database


_WEAK_TOPIC_PLACEHOLDER = re.compile(r"(?:^不符合$|模块\s*\d+|^未知$|^其他$|^n/?a$|import|csv|jsonl)", re.IGNORECASE)

# These imported datasets remain available to evaluation and historical records,
# but they are not part of the focused V3.1 learner catalog.  New sessions may
# only start from a published formal bank; existing persisted sessions can still
# be read so that removing a catalog entry never corrupts learning history.
_HIDDEN_LEARNER_BANK_IDS = {
    "bank-cmb-exam-real",
    "bank-general-science-foundations",
    "bank-arc-easy-local",
    "factory-generated-endoscopy-v1",
}


def learner_visible_weak_topics(recent_attempts: list[tuple[Any, QuestionModel, QuestionBankModel]]) -> list[str]:
    """Return only learner-meaningful weak-topic labels from incorrect attempts.

    Grading tags and import placeholders are deliberately excluded.  A subject is
    a last-resort classification, so it is labelled rather than presented as a
    knowledge concept.
    """
    counts: Counter[str] = Counter()
    for attempt, question, _ in recent_attempts:
        if attempt.correct:
            continue
        subject = str(question.subject or "").strip()

        def is_meaningful(value: Any) -> bool:
            candidate = str(value or "").strip()
            # Imported banks commonly repeat the broad subject in teaching_tags.
            # It is useful as a labelled fallback, but it is not a knowledge point.
            return bool(candidate) and candidate != subject and not _WEAK_TOPIC_PLACEHOLDER.search(candidate)

        candidates = [question.topic, *(question.teaching_tags or [])]
        label = next((str(value).strip() for value in candidates if is_meaningful(value)), None)
        if label is None and subject and not _WEAK_TOPIC_PLACEHOLDER.search(subject):
            label = f"学科 · {subject}"
        if label:
            counts[label] += 1

    # A generic subject becomes useful only after repeated evidence; a specific
    # topic remains meaningful after one incorrect attempt.
    ordered = [
        label
        for label, _ in sorted(
            counts.items(),
            key=lambda item: (item[0].startswith("学科 · "), -item[1], item[0]),
        )
        if not label.startswith("学科 · ") or counts[label] >= 2
    ]
    return ordered[:5]


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
        catalog_changed = False
        for bank in banks:
            # V3.1 intentionally retires the old seed/ARC catalog from the
            # learner surface.  Rows remain for compatibility, audit and test
            # history; a formal learning bank is a real CMExam/Kvasir/imported
            # bank rather than a bootstrap fixture.
            if (
                bank.bank_id in _HIDDEN_LEARNER_BANK_IDS
                or bank.version == "seed-v1"
                or "fixture" in bank.name.lower()
            ):
                if bank.status != "draft":
                    bank.status = "draft"
                    catalog_changed = True
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
        if benchmark_rows or inventory_changed or catalog_changed:
            # Quarantine and inventory are data-policy projections, not
            # response-only filters. Persist them so a fresh process cannot
            # expose benchmark rows or stale zero-question counts.
            self.session.commit()

    def list_banks(self, learner_id: str = "demo_learner", domain_id: str | None = None) -> list[QuestionBankModel]:
        self.ensure_seeded()
        statement = select(QuestionBankModel).where(
            QuestionBankModel.question_count > 0,
            QuestionBankModel.status == "published",
            QuestionBankModel.bank_id.not_in(_HIDDEN_LEARNER_BANK_IDS),
        )
        if domain_id:
            statement = statement.where(QuestionBankModel.domain_id == domain_id)
        banks = [
            bank
            for bank in self.session.scalars(statement.order_by(QuestionBankModel.name))
            if not bank.bank_id.startswith("adaptive-bank-")
            and not self._test_only_bank(bank.bank_id)
        ]
        for bank in banks:
            bank._stage1_progress = self.bank_progress(bank.bank_id, learner_id)
            bank._stage1_completed_count = bank._stage1_progress["completed_count"]
        return banks

    def _test_only_bank(self, bank_id: str) -> bool:
        source_types = set(self.session.scalars(
            select(QuestionModel.source_type).where(QuestionModel.bank_id == bank_id).distinct()
        ))
        return bool(source_types) and source_types == {"test"}

    def _is_learner_visible_bank(self, bank: QuestionBankModel) -> bool:
        """Apply the single learner-catalog policy to every learner projection."""
        return (
            bank.question_count > 0
            and bank.status == "published"
            and bank.bank_id not in _HIDDEN_LEARNER_BANK_IDS
            and not bank.bank_id.startswith("adaptive-bank-")
            and not self._test_only_bank(bank.bank_id)
        )

    def _learner_visible_bank_ids(self, bank_id: str | None = None) -> list[str]:
        """Resolve learner-visible banks once for read-heavy review projections.

        Review previously called ``_test_only_bank`` for every question in a
        bank. Build the same policy from one bank query plus one distinct
        source-type query, so a 1,500-question bank does not create 1,500
        repeated SQL reads.
        """
        statement = select(QuestionBankModel.bank_id).where(
            QuestionBankModel.question_count > 0,
            QuestionBankModel.status == "published",
            QuestionBankModel.bank_id.not_in(_HIDDEN_LEARNER_BANK_IDS),
        )
        if bank_id:
            statement = statement.where(QuestionBankModel.bank_id == bank_id)
        candidates = [
            value
            for value in self.session.scalars(statement.order_by(QuestionBankModel.name))
            if not value.startswith("adaptive-bank-")
        ]
        if not candidates:
            return []
        source_types: dict[str, set[str]] = {}
        for candidate_id, source_type in self.session.execute(
            select(QuestionModel.bank_id, QuestionModel.source_type)
            .where(QuestionModel.bank_id.in_(candidates))
            .distinct()
        ):
            source_types.setdefault(str(candidate_id), set()).add(str(source_type))
        return [candidate_id for candidate_id in candidates if source_types.get(candidate_id, set()) != {"test"}]

    def _review_question_ids(self, bank_id: str | None = None) -> list[str]:
        visible_bank_ids = self._learner_visible_bank_ids(bank_id)
        if not visible_bank_ids:
            return []
        return list(self.session.scalars(
            select(QuestionModel.question_id)
            .where(
                QuestionModel.business_usage == "user_ready",
                QuestionModel.bank_id.in_(visible_bank_ids),
            )
            .order_by(QuestionModel.question_id)
        ))

    def get_bank(self, bank_id: str) -> QuestionBankModel:
        self.ensure_seeded()
        bank = self.session.get(QuestionBankModel, bank_id)
        if not bank or bank.question_count <= 0:
            raise KeyError(f"Question bank not found: {bank_id}")
        return bank

    def learner_bank(self, bank_id: str) -> QuestionBankModel:
        bank = self.get_bank(bank_id)
        if bank.status != "published" or bank.bank_id in _HIDDEN_LEARNER_BANK_IDS:
            raise KeyError(f"Question bank is not learner-facing: {bank_id}")
        return bank

    def bank_progress(self, bank_id: str, learner_id: str) -> dict[str, int]:
        question_ids = list(self.session.scalars(
            select(QuestionModel.question_id).where(
                QuestionModel.bank_id == bank_id,
                QuestionModel.business_usage == "user_ready",
            )
        ))
        if not question_ids:
            return {"completed_count": 0, "uncompleted_count": 0, "incorrect_count": 0, "marked_count": 0}
        latest = self._latest_attempts(learner_id, question_ids)
        marked = set(self.session.scalars(
            select(QuestionMarkModel.question_id).where(
                QuestionMarkModel.learner_id == learner_id,
                QuestionMarkModel.question_id.in_(question_ids),
            )
        ))
        completed = len(latest)
        return {
            "completed_count": completed,
            "uncompleted_count": len(question_ids) - completed,
            "incorrect_count": sum(1 for attempt in latest.values() if not attempt.correct),
            "marked_count": len(marked),
        }

    def bank_question_progress(
        self,
        *,
        bank_id: str,
        learner_id: str,
        state: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        self.learner_bank(bank_id)
        questions = list(self.session.scalars(
            select(QuestionModel)
            .where(QuestionModel.bank_id == bank_id, QuestionModel.business_usage == "user_ready")
            .order_by(QuestionModel.question_id)
        ))
        question_ids = [item.question_id for item in questions]
        latest = self._latest_attempts(learner_id, question_ids)
        counts = Counter(self.session.scalars(
            select(AttemptModel.question_id).where(
                AttemptModel.learner_id == learner_id,
                AttemptModel.question_id.in_(question_ids),
            )
        )) if question_ids else Counter()
        marked = set(self.session.scalars(
            select(QuestionMarkModel.question_id).where(
                QuestionMarkModel.learner_id == learner_id,
                QuestionMarkModel.question_id.in_(question_ids),
            )
        ))
        rows = [self._question_progress_payload(item, latest.get(item.question_id), int(counts[item.question_id]), item.question_id in marked) for item in questions]
        if state == "uncompleted":
            rows = [item for item in rows if not item["completed"]]
        elif state == "completed":
            rows = [item for item in rows if item["completed"]]
        elif state == "incorrect":
            rows = [item for item in rows if item["incorrect"]]
        elif state == "marked":
            rows = [item for item in rows if item["marked"]]
        return rows[offset: offset + limit], len(rows)

    def set_question_mark(self, *, learner_id: str, question_id: str, marked: bool) -> bool:
        question = self.get_question(question_id)
        if question.business_usage != "user_ready":
            raise KeyError(question_id)
        existing = self.session.scalar(select(QuestionMarkModel).where(
            QuestionMarkModel.learner_id == learner_id,
            QuestionMarkModel.question_id == question_id,
        ))
        if marked and existing is None:
            self.session.add(QuestionMarkModel(mark_id=f"mark_{uuid4().hex[:12]}", learner_id=learner_id, question_id=question_id))
            self.session.commit()
        elif not marked and existing is not None:
            self.session.delete(existing)
            self.session.commit()
        return marked

    def review_summary(self, learner_id: str) -> dict[str, int]:
        ids = self._review_question_ids()
        latest = self._latest_attempts(learner_id, ids)
        return {
            "due_count": int(self.session.scalar(select(func.count(ReviewCardModel.review_card_id)).where(
                ReviewCardModel.learner_id == learner_id,
                ReviewCardModel.question_id.in_(ids),
                ReviewCardModel.due_at <= datetime.utcnow(),
            )) or 0) if ids else 0,
            "incorrect_count": sum(1 for attempt in latest.values() if not attempt.correct),
            "marked_count": int(self.session.scalar(select(func.count(QuestionMarkModel.mark_id)).where(
                QuestionMarkModel.learner_id == learner_id,
                QuestionMarkModel.question_id.in_(ids),
            )) or 0) if ids else 0,
        }

    def review_items(self, *, learner_id: str, tab: str, bank_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        ids = self._review_question_ids(bank_id)
        if not ids:
            return []
        latest = self._latest_attempts(learner_id, ids)
        marked = set(self.session.scalars(select(QuestionMarkModel.question_id).where(
            QuestionMarkModel.learner_id == learner_id,
            QuestionMarkModel.question_id.in_(ids),
        )))
        cards = {card.question_id: card for card in self.session.scalars(select(ReviewCardModel).where(
            ReviewCardModel.learner_id == learner_id,
            ReviewCardModel.question_id.in_(ids),
        ))}
        now = datetime.utcnow()
        if tab == "due":
            selected_ids = {question_id for question_id, card in cards.items() if card.due_at <= now}
        elif tab == "wrong":
            selected_ids = {question_id for question_id, attempt in latest.items() if not attempt.correct}
        elif tab == "marked":
            selected_ids = marked
        else:
            raise ValueError(f"unsupported review tab: {tab}")
        if not selected_ids:
            return []
        rows = list(self.session.execute(
            select(QuestionModel, QuestionBankModel)
            .join(QuestionBankModel, QuestionBankModel.bank_id == QuestionModel.bank_id)
            .where(QuestionModel.question_id.in_(selected_ids))
            .order_by(QuestionBankModel.name, QuestionModel.question_id)
            .limit(limit)
        ).all())
        selected_question_ids = [question.question_id for question, _ in rows]
        all_attempts = list(self.session.scalars(select(AttemptModel).where(
            AttemptModel.learner_id == learner_id,
            AttemptModel.question_id.in_(selected_question_ids),
        ).order_by(AttemptModel.created_at.desc())))
        attempts_by_question: dict[str, list[AttemptModel]] = {}
        for attempt in all_attempts:
            attempts_by_question.setdefault(attempt.question_id, []).append(attempt)
        result: list[dict[str, Any]] = []
        for question, bank in rows:
            latest_attempt = latest.get(question.question_id)
            payload = self._question_progress_payload(
                question, latest_attempt, len(attempts_by_question.get(question.question_id, [])), question.question_id in marked
            )
            payload.update({
                "bank_id": bank.bank_id,
                "bank_name": bank.name,
                "due_at": cards[question.question_id].due_at if question.question_id in cards else None,
                "wrong_count": sum(1 for attempt in attempts_by_question.get(question.question_id, []) if not attempt.correct),
                "last_selected_answer": latest_attempt.selected_answer if latest_attempt else None,
                "official_explanation_available": bool(question.official_explanation_available and (question.explanation or "").strip()),
            })
            result.append(payload)
        return result

    def review_item_detail(self, *, learner_id: str, question_id: str) -> dict[str, Any]:
        visible_bank_ids = self._learner_visible_bank_ids()
        if not visible_bank_ids:
            raise KeyError(question_id)
        pair = self.session.execute(
            select(QuestionModel, QuestionBankModel)
            .join(QuestionBankModel, QuestionBankModel.bank_id == QuestionModel.bank_id)
            .where(
                QuestionModel.question_id == question_id,
                QuestionModel.business_usage == "user_ready",
                QuestionModel.bank_id.in_(visible_bank_ids),
            )
        ).first()
        if pair is None:
            raise KeyError(question_id)
        question, bank = pair
        attempts = list(self.session.scalars(select(AttemptModel).where(
            AttemptModel.learner_id == learner_id,
            AttemptModel.question_id == question_id,
        ).order_by(AttemptModel.created_at.desc())))
        latest_attempt = attempts[0] if attempts else None
        marked = self.session.scalar(select(QuestionMarkModel.mark_id).where(
            QuestionMarkModel.learner_id == learner_id,
            QuestionMarkModel.question_id == question_id,
        )) is not None
        card = self.session.scalar(select(ReviewCardModel).where(
            ReviewCardModel.learner_id == learner_id,
            ReviewCardModel.question_id == question_id,
        ))
        if not (
            (card is not None and card.due_at <= datetime.utcnow())
            or (latest_attempt is not None and not latest_attempt.correct)
            or marked
        ):
            raise KeyError(question_id)
        row = self._question_progress_payload(question, latest_attempt, len(attempts), marked)
        row.update({
            "bank_id": bank.bank_id,
            "bank_name": bank.name,
            "due_at": card.due_at if card is not None else None,
            "wrong_count": sum(1 for attempt in attempts if not attempt.correct),
            "last_selected_answer": latest_attempt.selected_answer if latest_attempt else None,
            "official_explanation_available": bool(question.official_explanation_available and (question.explanation or "").strip()),
        })
        grading = question.grading_payload or {}
        options = {str(item.get("id")): str(item.get("text")) for item in (question.options or [])}
        def display(selected: Any) -> str:
            if isinstance(selected, list):
                return "、".join(options.get(str(item), str(item)) for item in selected)
            if question.question_type == "true_false":
                return "正确" if bool(selected) else "错误"
            return options.get(str(selected), str(selected))
        if question.question_type == "single_choice":
            answer = options.get(str(grading.get("correct_option_id")), "")
        elif question.question_type == "multiple_choice":
            answer = "、".join(options.get(str(item), str(item)) for item in grading.get("correct_option_ids", []))
        elif question.question_type == "true_false":
            answer = "正确" if grading.get("correct_value") else "错误"
        else:
            answer = "参考答案见评分标准"
        row.update({
            "stem": question.stem,
            "options": list(question.options or []),
            "correct_answer_display": answer,
            "explanation": question.explanation if question.official_explanation_available else "",
            "recent_attempts": [{"selected_answer_display": display(item.selected_answer), "correct": item.correct, "created_at": item.created_at} for item in attempts[:5]],
        })
        return row

    def list_questions(
        self,
        *,
        bank_id: str | None = None,
        domain_id: str | None = None,
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
                # Persistent local regression runs may leave their explicitly
                # marked test rows in the developer SQLite database.  They
                # remain addressable by their test bank, but must not crowd
                # the canonical learner catalog or hide the four typed seed
                # variants on the first page.
                (QuestionModel.source_dataset == "test", 3),
                (QuestionModel.source_dataset.not_in(["CMExam", "CMB-Exam", "Kvasir-VQA"]), 0),
                (QuestionModel.modality == "image", 1),
                else_=2,
            ),
            QuestionModel.question_id,
        )
        if bank_id:
            statement = statement.where(QuestionModel.bank_id == bank_id)
        if domain_id:
            statement = statement.where(QuestionModel.domain_id == domain_id)
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
        question_scope: str = "all",
        allow_non_catalog: bool = False,
    ) -> tuple[PracticeSessionModel, dict[str, Any]]:
        bank = self.get_bank(bank_id) if allow_non_catalog else self.learner_bank(bank_id)
        questions = list(
            self.session.scalars(
                select(QuestionModel)
                .where(QuestionModel.bank_id == bank_id, QuestionModel.business_usage == "user_ready")
                .order_by(QuestionModel.question_id)
            )
        )
        questions = self._filter_questions_for_scope(questions, learner_id=learner_id, scope=question_scope)
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
            domain_id=bank.domain_id,
            mode=mode,
            status="active",
            requested_question_count=selection_size,
            current_position=0,
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

    def _filter_questions_for_scope(self, questions: list[QuestionModel], *, learner_id: str, scope: str) -> list[QuestionModel]:
        if scope == "all":
            return questions
        question_ids = [item.question_id for item in questions]
        latest = self._latest_attempts(learner_id, question_ids)
        if scope == "uncompleted":
            return [item for item in questions if item.question_id not in latest]
        if scope == "incorrect":
            return [item for item in questions if item.question_id in latest and not latest[item.question_id].correct]
        if scope == "marked":
            marked = set(self.session.scalars(select(QuestionMarkModel.question_id).where(
                QuestionMarkModel.learner_id == learner_id,
                QuestionMarkModel.question_id.in_(question_ids),
            )))
            return [item for item in questions if item.question_id in marked]
        if scope == "due":
            now = datetime.utcnow()
            due = set(self.session.scalars(select(ReviewCardModel.question_id).where(
                ReviewCardModel.learner_id == learner_id,
                ReviewCardModel.question_id.in_(question_ids),
                ReviewCardModel.due_at <= now,
            )))
            return [item for item in questions if item.question_id in due]
        raise ValueError(f"unsupported question scope: {scope}")

    def _latest_attempts(self, learner_id: str, question_ids: list[str]) -> dict[str, AttemptModel]:
        if not question_ids:
            return {}
        attempts = list(self.session.scalars(
            select(AttemptModel)
            .where(AttemptModel.learner_id == learner_id, AttemptModel.question_id.in_(question_ids))
            .order_by(AttemptModel.created_at.desc())
        ))
        latest: dict[str, AttemptModel] = {}
        for attempt in attempts:
            latest.setdefault(attempt.question_id, attempt)
        return latest

    @staticmethod
    def _question_progress_payload(question: QuestionModel, latest: AttemptModel | None, attempt_count: int, marked: bool) -> dict[str, Any]:
        return {
            "question_id": question.question_id,
            "question_type": question.question_type,
            "question_summary": (question.stem or question.title).strip()[:120],
            "subject": question.subject,
            "topic": question.topic,
            "completed": latest is not None,
            "incorrect": bool(latest is not None and not latest.correct),
            "marked": marked,
            "attempt_count": attempt_count,
            "last_result": None if latest is None else ("correct" if latest.correct else "incorrect"),
            "last_attempt_at": None if latest is None else latest.created_at,
        }

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
                select(LearnerMasteryModel).where(
                    LearnerMasteryModel.learner_id == learner_id,
                    LearnerMasteryModel.domain_id == questions[0].domain_id,
                )
            )
            if row.attempt_count > 0
        }
        due_by_question = {
            row.question_id: row
            for row in self.session.scalars(
                select(ReviewCardModel).where(
                    ReviewCardModel.learner_id == learner_id,
                    ReviewCardModel.domain_id == questions[0].domain_id,
                    ReviewCardModel.question_id.in_(question_ids),
                )
            )
            if row.due_at <= now
        }
        active_memory = list(
            self.session.scalars(
                select(LearningMemoryItemModel).where(
                    LearningMemoryItemModel.learner_id == learner_id,
                    LearningMemoryItemModel.domain_id == questions[0].domain_id,
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

    def get_or_create_session(
        self,
        learner_id: str,
        bank_id: str,
        session_id: str | None,
        mode: str = "practice",
        question_id: str | None = None,
    ) -> PracticeSessionModel:
        if session_id:
            current = self.session.get(PracticeSessionModel, session_id)
            if current and current.learner_id == learner_id and current.bank_id == bank_id:
                if question_id is not None:
                    member = self.session.scalar(select(PracticeSessionItemModel).where(
                        PracticeSessionItemModel.practice_session_id == session_id,
                        PracticeSessionItemModel.question_id == question_id,
                    ))
                    if member is None:
                        # A valid session ID is not permission to submit an
                        # arbitrary question from the same bank. Session
                        # membership is the authoritative Practice boundary.
                        raise KeyError(f"Question is not part of practice session: {question_id}")
                return current
        # Historical/compatibility submissions may target an archived seed
        # question.  Preserve their immutable Attempt history without letting
        # that bank reappear as a new learner-facing catalog choice.
        created, _ = self.create_session(learner_id, bank_id, mode, allow_non_catalog=True)
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
        timings: dict[str, float] | None = None,
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
        timing = timings if timings is not None else {}
        started = datetime.utcnow()
        self.session.add(attempt)
        session.last_active_at = now
        # The submit workflow owns the only side effects: once the immutable
        # attempt is staged, derive mastery and FSRS scheduling deterministically.
        self.session.flush()
        timing["attempt_insert_ms"] = round((datetime.utcnow() - started).total_seconds() * 1000, 3)
        from app.services.learning_service import apply_learning_outcome
        apply_learning_outcome(self.session, attempt=attempt, question=question, now=now, timings=timing)
        commit_started = datetime.utcnow()
        self.session.commit()
        timing["commit_ms"] = round((datetime.utcnow() - commit_started).total_seconds() * 1000, 3)
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
            self.session.execute(
                select(AttemptModel, QuestionModel, QuestionBankModel)
                .join(QuestionModel, QuestionModel.question_id == AttemptModel.question_id)
                .join(QuestionBankModel, QuestionBankModel.bank_id == QuestionModel.bank_id)
                .where(AttemptModel.learner_id == learner_id)
                .order_by(AttemptModel.created_at.desc())
                .limit(10)
            ).all()
        )
        due_count = self.session.scalar(
            select(func.count(ReviewCardModel.review_card_id)).where(
                ReviewCardModel.learner_id == learner_id,
                ReviewCardModel.due_at <= datetime.utcnow(),
            )
        ) or 0
        recent_accuracy = (
            sum(1 for item, _, _ in recent_attempts if item.correct) / len(recent_attempts)
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
                    "attempt_id": attempt.attempt_id,
                    "question_id": attempt.question_id,
                    "bank_id": question.bank_id,
                    "bank_name": bank.name,
                    "question_summary": (question.stem or question.title).strip()[:88],
                    "question_type": question.question_type,
                    "score": attempt.score,
                    "correct": attempt.correct,
                    "created_at": attempt.created_at.isoformat(),
                }
                for attempt, question, bank in recent_attempts
            ],
            "banks": banks,
            "weak_areas": learner_visible_weak_topics(recent_attempts),
            "safety_notice": SAFETY_NOTICE,
            "api_source": "backend",
        }
