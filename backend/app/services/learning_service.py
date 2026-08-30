"""Deterministic learner state: immutable attempts, mastery and official FSRS.

This module deliberately has no model/tool dependency.  A successful submit
always follows grade -> attempt -> mastery -> review schedule on the server.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fsrs import Card, Rating, Scheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AttemptModel, LearnerMasteryModel, QuestionModel, ReviewCardModel


RATING_BY_RESULT = {True: Rating.Good, False: Rating.Again}
SCHEDULER = Scheduler(enable_fuzzing=False)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _rating_name(rating: Rating) -> str:
    return {Rating.Again: "Again", Rating.Hard: "Hard", Rating.Good: "Good", Rating.Easy: "Easy"}[rating]


def apply_learning_outcome(session: Session, *, attempt: AttemptModel, question: QuestionModel, now: datetime | None = None) -> ReviewCardModel:
    """Apply deterministic state transitions after an immutable attempt exists."""
    review_at = _aware(now or attempt.created_at)
    card_model = session.scalar(select(ReviewCardModel).where(
        ReviewCardModel.learner_id == attempt.learner_id,
        ReviewCardModel.question_id == attempt.question_id,
    ))
    if card_model and card_model.fsrs_card:
        card = Card.from_dict(card_model.fsrs_card)
    else:
        card = Card()
    rating = RATING_BY_RESULT[attempt.correct]
    scheduled, log = SCHEDULER.review_card(card, rating, review_datetime=review_at)
    due_at = scheduled.due.replace(tzinfo=None) if scheduled.due.tzinfo else scheduled.due
    retrievability = SCHEDULER.get_card_retrievability(scheduled, current_datetime=review_at)
    payload = scheduled.to_dict()
    logs = list(card_model.fsrs_logs) if card_model else []
    logs.append({**log.to_dict(), "rating_name": _rating_name(rating)})
    interval_days = max(0, (due_at - review_at.replace(tzinfo=None)).days)
    if card_model is None:
        card_model = ReviewCardModel(
            review_card_id=f"review_{uuid4().hex[:12]}", learner_id=attempt.learner_id,
            question_id=attempt.question_id, due_at=due_at, interval_days=interval_days,
            review_count=1, last_reviewed_at=review_at.replace(tzinfo=None), fsrs_card=payload,
            fsrs_logs=logs, difficulty=scheduled.difficulty, stability=scheduled.stability,
            retrievability=retrievability, fsrs_state=scheduled.state.name,
        )
        session.add(card_model)
    else:
        card_model.due_at = due_at
        card_model.interval_days = interval_days
        card_model.review_count += 1
        card_model.last_reviewed_at = review_at.replace(tzinfo=None)
        card_model.fsrs_card = payload
        card_model.fsrs_logs = logs
        card_model.difficulty = scheduled.difficulty
        card_model.stability = scheduled.stability
        card_model.retrievability = retrievability
        card_model.fsrs_state = scheduled.state.name
    _rebuild_mastery(session, attempt.learner_id, question)
    # Memory is a compact derived fact built only after the immutable attempt,
    # mastery and FSRS state are already staged in this same transaction.
    from app.services.learning_memory_service import learning_memory_service

    learning_memory_service.consolidate_attempt(session, attempt=attempt, question=question)
    return card_model


def _rebuild_mastery(session: Session, learner_id: str, question: QuestionModel) -> None:
    """Rebuild the affected knowledge points from immutable attempts."""
    points = sorted(set(question.teaching_tags or [question.body_part]))
    for point in points:
        # JSON containment compiles differently on SQLite and PostgreSQL.  The
        # immutable attempt set is small in this training workflow, so use a
        # portable query and apply the tag projection in Python.
        learner_attempts = list(session.scalars(
            select(AttemptModel).where(AttemptModel.learner_id == learner_id).order_by(AttemptModel.created_at)
        ))
        attempts = [item for item in learner_attempts if (linked := session.get(QuestionModel, item.question_id)) and (point in (linked.teaching_tags or []) or linked.body_part == point)]
        if not attempts:
            continue
        errors = Counter(tag for item in attempts for tag in (item.error_tags or []))
        accuracy = sum(item.correct for item in attempts) / len(attempts)
        recent = attempts[-5:]
        recent_accuracy = sum(item.correct for item in recent) / len(recent)
        score = round((0.6 * accuracy + 0.4 * recent_accuracy) * 100, 1)
        record = session.scalar(select(LearnerMasteryModel).where(
            LearnerMasteryModel.learner_id == learner_id, LearnerMasteryModel.knowledge_point == point,
        ))
        if record is None:
            record = LearnerMasteryModel(mastery_id=f"mastery_{uuid4().hex[:12]}", learner_id=learner_id, knowledge_point=point)
            session.add(record)
        record.attempt_count = len(attempts)
        record.accuracy = accuracy
        record.recent_accuracy = recent_accuracy
        record.common_errors = [name for name, _ in errors.most_common(3)]
        record.last_seen_at = attempts[-1].created_at
        record.mastery_score = score


def review_with_rating(session: Session, *, learner_id: str, question_id: str, rating_name: str, now: datetime | None = None) -> dict[str, Any]:
    rating = {"Again": Rating.Again, "Hard": Rating.Hard, "Good": Rating.Good, "Easy": Rating.Easy}.get(rating_name)
    if rating is None:
        raise ValueError("unsupported FSRS rating")
    card_model = session.scalar(select(ReviewCardModel).where(ReviewCardModel.learner_id == learner_id, ReviewCardModel.question_id == question_id))
    if card_model is None:
        raise KeyError("review card not found")
    review_at = _aware(now or datetime.utcnow())
    card = Card.from_dict(card_model.fsrs_card) if card_model.fsrs_card else Card()
    scheduled, log = SCHEDULER.review_card(card, rating, review_datetime=review_at)
    card_model.fsrs_card = scheduled.to_dict()
    card_model.fsrs_logs = [*card_model.fsrs_logs, {**log.to_dict(), "rating_name": rating_name}]
    card_model.difficulty = scheduled.difficulty
    card_model.stability = scheduled.stability
    card_model.retrievability = SCHEDULER.get_card_retrievability(scheduled, current_datetime=review_at)
    card_model.fsrs_state = scheduled.state.name
    card_model.due_at = scheduled.due.replace(tzinfo=None)
    card_model.interval_days = max(0, (card_model.due_at - review_at.replace(tzinfo=None)).days)
    card_model.review_count += 1
    card_model.last_reviewed_at = review_at.replace(tzinfo=None)
    return review_card_payload(card_model)


def review_card_payload(card: ReviewCardModel) -> dict[str, Any]:
    return {
        "review_card_id": card.review_card_id, "question_id": card.question_id,
        "due_at": card.due_at.isoformat(), "interval_days": card.interval_days,
        "difficulty": card.difficulty, "stability": card.stability,
        "retrievability": card.retrievability, "state": card.fsrs_state,
        "review_count": card.review_count,
    }


def mentor_plan(session: Session, *, learner_id: str, study_goal: str = "巩固观察证据与复盘边界") -> dict[str, Any]:
    due = list(session.scalars(select(ReviewCardModel).where(ReviewCardModel.learner_id == learner_id).order_by(ReviewCardModel.due_at).limit(8)))
    mastery = list(session.scalars(select(LearnerMasteryModel).where(LearnerMasteryModel.learner_id == learner_id).order_by(LearnerMasteryModel.mastery_score).limit(3)))
    recent = list(session.scalars(select(AttemptModel).where(AttemptModel.learner_id == learner_id).order_by(AttemptModel.created_at.desc()).limit(8)))
    error_tags = [tag for item in recent for tag in (item.error_tags or [])]
    focus = mastery[0].knowledge_point if mastery else "基础观察"
    return {
        "learner_id": learner_id, "study_goal": study_goal, "due_review_count": len(due),
        "focus": focus, "weak_areas": [item.knowledge_point for item in mastery],
        "recent_errors": [name for name, _ in Counter(error_tags).most_common(3)],
        "steps": [
            {"kind": "review", "title": f"先完成 {len(due)} 张到期复习卡", "question_ids": [item.question_id for item in due[:3]]},
            {"kind": "focus", "title": f"围绕「{focus}」完成 3 题并逐项写出观察证据", "question_ids": []},
            {"kind": "safety", "title": "复盘时区分可见事实与需要完整检查、医生复核的信息", "question_ids": []},
        ],
    }
