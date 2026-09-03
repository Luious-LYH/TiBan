"""Persistence and bounded context for the session-scoped Tutor Agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import PracticeSessionItemModel, PracticeSessionModel, TutorMessageModel, TutorThreadModel
from app.services.learning_memory_service import extract_explicit_confusion
from app.services.memory_reflection_service import memory_reflection_service


class TutorSessionService:
    def start_turn(self, *, practice_session_id: str, tutor_thread_id: str, learner_id: str, question_id: str, content: str) -> list[dict[str, str]]:
        with SessionLocal() as session:
            practice = session.get(PracticeSessionModel, practice_session_id)
            thread = session.get(TutorThreadModel, tutor_thread_id)
            member = session.scalar(select(PracticeSessionItemModel).where(
                PracticeSessionItemModel.practice_session_id == practice_session_id,
                PracticeSessionItemModel.question_id == question_id,
            ))
            if (
                practice is None
                or thread is None
                or member is None
                or practice.learner_id != learner_id
                or thread.learner_id != learner_id
                or thread.practice_session_id != practice_session_id
                or thread.status != "active"
            ):
                raise KeyError("invalid Tutor session context")
            history = list(session.scalars(select(TutorMessageModel).where(
                TutorMessageModel.tutor_thread_id == tutor_thread_id
            ).order_by(TutorMessageModel.created_at.desc()).limit(12)))
            history.reverse()
            now = datetime.utcnow()
            session.add(TutorMessageModel(
                tutor_message_id=f"tutormsg_{uuid4().hex[:12]}", tutor_thread_id=tutor_thread_id,
                practice_session_id=practice_session_id, role="user", content=content,
            ))
            thread.last_active_at = now
            practice.last_active_at = now
            # A transcript turn is evidence. Reflection decides later whether it
            # supports a durable fact; it never writes raw chat into Memory.
            practice.reflection_dirty, practice.reflection_version, practice.reflection_status = True, practice.reflection_version + 1, "pending"
            session.commit()
            return [{"role": item.role, "content": item.content} for item in history]

    def finish_turn(
        self,
        *,
        practice_session_id: str,
        tutor_thread_id: str,
        learner_id: str,
        content: str,
        run_id: str | None,
        activity: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        user_message: str,
    ) -> None:
        if not content:
            return
        should_enqueue = extract_explicit_confusion(user_message) is not None
        with SessionLocal() as session:
            practice = session.get(PracticeSessionModel, practice_session_id)
            thread = session.get(TutorThreadModel, tutor_thread_id)
            if practice is None or thread is None or practice.learner_id != learner_id or thread.practice_session_id != practice_session_id:
                return
            session.add(TutorMessageModel(
                tutor_message_id=f"tutormsg_{uuid4().hex[:12]}", tutor_thread_id=tutor_thread_id,
                practice_session_id=practice_session_id, role="assistant", content=content,
                activity=activity, sources=sources, run_id=run_id,
            ))
            now = datetime.utcnow()
            thread.last_active_at, practice.last_active_at = now, now
            session.commit()
        if should_enqueue:
            memory_reflection_service.enqueue(practice_session_id, reason="meaningful_confusion")


tutor_session_service = TutorSessionService()
