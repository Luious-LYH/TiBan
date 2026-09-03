"""Explicit Practice lifecycle without moving deterministic grading into Agent code."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import AttemptModel, PracticeSessionItemModel, PracticeSessionModel, TutorThreadModel
from app.services.memory_reflection_service import memory_reflection_service


class PracticeSessionService:
    def abandon_other_active(self, *, learner_id: str, except_session_id: str | None = None) -> list[str]:
        """End old active sessions before a newly selected batch starts."""

        with SessionLocal() as session:
            rows = list(session.scalars(select(PracticeSessionModel).where(
                PracticeSessionModel.learner_id == learner_id,
                PracticeSessionModel.status == "active",
            )))
            affected: list[str] = []
            for row in rows:
                if row.session_id == except_session_id:
                    continue
                row.status = "abandoned"
                row.last_active_at = datetime.utcnow()
                row.reflection_dirty = True
                row.reflection_version += 1
                row.reflection_status = "pending"
                # A new batch must never inherit an old Tutor context. Keep
                # the old transcript for audit/Reflection, but close every
                # active thread belonging to the abandoned session.
                now = datetime.utcnow()
                for thread in session.scalars(select(TutorThreadModel).where(
                    TutorThreadModel.practice_session_id == row.session_id,
                    TutorThreadModel.status == "active",
                )):
                    thread.status, thread.ended_at, thread.last_active_at = "closed", now, now
                affected.append(row.session_id)
            session.commit()
        for session_id in affected:
            memory_reflection_service.enqueue(session_id, reason="new_practice_session")
        return affected

    def after_submission(self, *, session_id: str, question_id: str) -> dict[str, Any]:
        """Persist lightweight progress and enqueue Reflection only if eligible."""

        enqueue_reason: str | None = None
        with SessionLocal() as session:
            practice = session.get(PracticeSessionModel, session_id)
            if practice is None:
                raise KeyError(session_id)
            items = list(session.scalars(select(PracticeSessionItemModel).where(
                PracticeSessionItemModel.practice_session_id == session_id
            ).order_by(PracticeSessionItemModel.ordinal)))
            ordinal = next((item.ordinal for item in items if item.question_id == question_id), practice.current_position)
            submitted = set(session.scalars(select(AttemptModel.question_id).where(AttemptModel.practice_session_id == session_id)))
            practice.current_position = min(max(ordinal + 1, practice.current_position), max(len(items) - 1, 0))
            practice.last_active_at = datetime.utcnow()
            practice.reflection_dirty = True
            practice.reflection_version += 1
            practice.reflection_status = "pending"
            if items and all(item.question_id in submitted for item in items):
                practice.status = "completed"
                practice.completed_at = datetime.utcnow()
                enqueue_reason = "session_completed"
            session.commit()
            payload = {
                "status": practice.status,
                "current_position": practice.current_position,
                "reflection_status": practice.reflection_status,
            }
        if enqueue_reason:
            memory_reflection_service.enqueue(session_id, reason=enqueue_reason)
            payload["reflection_status"] = "queued"
        return payload

    def create_tutor_thread(self, *, session_id: str, learner_id: str) -> dict[str, str]:
        """Always create a fresh active Tutor context for start/resume."""

        with SessionLocal() as session:
            practice = session.get(PracticeSessionModel, session_id)
            if practice is None or practice.learner_id != learner_id:
                raise KeyError(session_id)
            # Old transcripts remain evidence. Ending an old active thread
            # prevents it from being accidentally reused as prompt context.
            now = datetime.utcnow()
            for current in session.scalars(select(TutorThreadModel).where(
                TutorThreadModel.practice_session_id == session_id,
                TutorThreadModel.status == "active",
            )):
                current.status, current.ended_at = "closed", now
            row = TutorThreadModel(
                tutor_thread_id=f"tutor_thread_{uuid4().hex[:12]}",
                practice_session_id=session_id,
                learner_id=learner_id,
                status="active",
                started_at=now,
                last_active_at=now,
            )
            session.add(row)
            practice.last_active_at = now
            session.commit()
            return {"tutor_thread_id": row.tutor_thread_id, "practice_session_id": row.practice_session_id, "status": row.status}

    def resumable(self, *, learner_id: str) -> dict[str, Any] | None:
        with SessionLocal() as session:
            row = session.scalar(select(PracticeSessionModel).where(
                PracticeSessionModel.learner_id == learner_id,
                PracticeSessionModel.status == "active",
            ).order_by(PracticeSessionModel.last_active_at.desc()))
            if row is None:
                return None
            return {
                "session_id": row.session_id,
                "bank_id": row.bank_id,
                "mode": row.mode,
                "current_position": row.current_position,
                "last_active_at": row.last_active_at,
            }

    def resume(self, *, session_id: str, learner_id: str) -> dict[str, str]:
        with SessionLocal() as session:
            row = session.get(PracticeSessionModel, session_id)
            if row is None or row.learner_id != learner_id or row.status != "active":
                raise KeyError(session_id)
            row.last_active_at = datetime.utcnow()
            session.commit()
        return self.create_tutor_thread(session_id=session_id, learner_id=learner_id)

    def leave(self, *, session_id: str, learner_id: str, abandon: bool = False) -> None:
        with SessionLocal() as session:
            row = session.get(PracticeSessionModel, session_id)
            if row is None or row.learner_id != learner_id:
                raise KeyError(session_id)
            row.last_active_at = datetime.utcnow()
            if abandon and row.status == "active":
                row.status = "abandoned"
                row.reflection_dirty = True
                row.reflection_version += 1
                row.reflection_status = "pending"
                now = datetime.utcnow()
                for thread in session.scalars(select(TutorThreadModel).where(
                    TutorThreadModel.practice_session_id == session_id,
                    TutorThreadModel.status == "active",
                )):
                    thread.status, thread.ended_at, thread.last_active_at = "closed", now, now
            session.commit()
        if abandon:
            memory_reflection_service.enqueue(session_id, reason="practice_left")


practice_session_service = PracticeSessionService()
