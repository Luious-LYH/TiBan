"""Validated asynchronous Reflection from session evidence to Learning Memory."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core import config
from app.db.database import SessionLocal
from app.db.models import (
    AttemptModel,
    BackgroundJobModel,
    LearningMemoryItemModel,
    PracticeSessionModel,
    QuestionModel,
    TutorMessageModel,
)
from app.services.learning_memory_service import _dedupe_key, _merge_evidence, topic_keys_for_question
from app.services.rag_service import _terms
from app.services.semantic_memory_service import semantic_memory_service


REFLECTION_INACTIVITY_MINUTES = 20
MAX_SESSION_ATTEMPTS = 40
MAX_SESSION_MESSAGES = 12


class ReflectionCandidate(BaseModel):
    action: Literal["ADD", "UPDATE", "RESOLVE", "NOOP"]
    kind: Literal["repeated_mistake", "confusing_concepts", "misconception", "study_habit"] | None = None
    summary: str = Field(default="", max_length=240)
    topic_keys: list[str] = Field(default_factory=list, max_length=4)
    concept_keys: list[str] = Field(default_factory=list, max_length=6)
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list, max_length=12)


class MemoryReflectionService:
    def mark_dirty(self, session_id: str, *, reason: str) -> int:
        with SessionLocal() as session:
            practice = session.get(PracticeSessionModel, session_id)
            if practice is None:
                raise KeyError(session_id)
            practice.reflection_dirty = True
            practice.reflection_version += 1
            practice.reflection_status = "pending"
            practice.last_active_at = datetime.utcnow()
            session.commit()
            return int(practice.reflection_version)

    def enqueue(self, session_id: str, *, reason: str) -> str | None:
        """Create one durable job per session evidence version; queue best effort."""

        with SessionLocal() as session:
            practice = session.get(PracticeSessionModel, session_id)
            if practice is None or not practice.reflection_dirty:
                return None
            version = int(practice.reflection_version)
            key = f"reflection:{session_id}:{version}"
            existing = session.scalar(select(BackgroundJobModel).where(BackgroundJobModel.idempotency_key == key))
            if existing:
                # A failed worker attempt is retryable work for the same
                # evidence version. Reusing the durable row preserves
                # idempotency and avoids creating duplicate memory jobs,
                # while putting it back on the queue lets inactivity/startup
                # reconciliation make progress after a transient provider or
                # Redis failure.
                if existing.status == "failed":
                    existing.status = "queued"
                    existing.stage = "queued"
                    existing.progress = 0
                    existing.error_message = None
                    existing.started_at = None
                    existing.completed_at = None
                    existing.detail = {**dict(existing.detail or {}), "reason": reason, "retry": True}
                    practice.reflection_status = "queued"
                    session.commit()
                else:
                    return existing.job_id
                job_id = existing.job_id
            else:
                job = BackgroundJobModel(
                    job_id=f"reflection_{uuid4().hex[:12]}",
                    job_type="memory_reflection",
                    target_id=session_id,
                    status="queued",
                    stage="queued",
                    progress=0,
                    idempotency_key=key,
                    detail={"reason": reason, "reflection_version": version},
                )
                session.add(job)
                practice.reflection_status = "queued"
                session.commit()
                job_id = job.job_id
        try:
            from app.workers.background_worker import process_memory_reflection_actor

            process_memory_reflection_actor.send(job_id)
        except Exception:
            # Redis/worker availability never invalidates the already-committed
            # Attempt/session data. Startup/inactivity reconciliation retries it.
            pass
        return job_id

    def process(self, job_id: str) -> dict[str, Any]:
        with SessionLocal() as session:
            job = session.get(BackgroundJobModel, job_id)
            if job is None or job.job_type != "memory_reflection":
                raise KeyError(job_id)
            if job.status in {"completed", "noop"}:
                return {"status": job.status, "job_id": job_id}
            practice = session.get(PracticeSessionModel, job.target_id)
            if practice is None:
                job.status, job.stage, job.error_message = "failed", "failed", "practice session not found"
                session.commit()
                return {"status": "failed", "job_id": job_id}
            version = int(job.detail.get("reflection_version", -1))
            if not practice.reflection_dirty or version != practice.reflection_version:
                job.status, job.stage, job.progress = "noop", "superseded", 100
                session.commit()
                return {"status": "noop", "job_id": job_id}
            job.status, job.stage, job.progress, job.started_at = "running", "collecting_evidence", 10, datetime.utcnow()
            practice.reflection_status = "running"
            session.commit()

        try:
            evidence = self._session_evidence(practice.session_id, practice.learner_id)
            candidate = self._candidate(evidence)
            outcome = self._apply_candidate(job_id, candidate, evidence)
            return outcome
        except Exception as exc:
            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                practice = session.get(PracticeSessionModel, job.target_id) if job else None
                if job:
                    job.status, job.stage, job.error_message = "failed", "failed", type(exc).__name__
                    job.completed_at = datetime.utcnow()
                if practice:
                    practice.reflection_status = "failed"
                session.commit()
            raise

    def reconcile_inactive(self, *, now: datetime | None = None) -> list[str]:
        cutoff = (now or datetime.utcnow()) - timedelta(minutes=REFLECTION_INACTIVITY_MINUTES)
        with SessionLocal() as session:
            ids = list(session.scalars(select(PracticeSessionModel.session_id).where(
                PracticeSessionModel.reflection_dirty.is_(True),
                PracticeSessionModel.last_active_at <= cutoff,
                PracticeSessionModel.status.in_(["active", "abandoned", "completed"]),
            )))
        return [job_id for session_id in ids if (job_id := self.enqueue(session_id, reason="inactivity"))]

    def _session_evidence(self, session_id: str, learner_id: str) -> dict[str, Any]:
        with SessionLocal() as session:
            practice = session.get(PracticeSessionModel, session_id)
            if practice is None or practice.learner_id != learner_id:
                raise KeyError(session_id)
            attempts = list(session.execute(
                select(AttemptModel, QuestionModel)
                .join(QuestionModel, QuestionModel.question_id == AttemptModel.question_id)
                .where(AttemptModel.practice_session_id == session_id, AttemptModel.learner_id == learner_id)
                .order_by(AttemptModel.created_at.desc())
                .limit(MAX_SESSION_ATTEMPTS)
            ).all())
            attempts.reverse()
            messages = list(session.scalars(select(TutorMessageModel).where(
                TutorMessageModel.practice_session_id == session_id
            ).order_by(TutorMessageModel.created_at.desc()).limit(MAX_SESSION_MESSAGES)))
            messages.reverse()
        refs: dict[str, dict[str, Any]] = {}
        attempt_payload: list[dict[str, Any]] = []
        for attempt, question in attempts:
            reference = {
                "source_type": "graded_attempt",
                "attempt_id": attempt.attempt_id,
                "session_id": session_id,
                "question_id": attempt.question_id,
                "topic_keys": topic_keys_for_question(question),
                "outcome": "correct" if attempt.correct else "incorrect",
                "occurred_at": attempt.created_at.isoformat(),
            }
            refs[attempt.attempt_id] = reference
            attempt_payload.append({
                "evidence_ref": attempt.attempt_id,
                "topic_keys": reference["topic_keys"],
                "correct": attempt.correct,
                "error_tags": list(attempt.error_tags or []),
            })
        transcript: list[dict[str, str]] = []
        for message in messages:
            refs[message.tutor_message_id] = {
                "source_type": "tutor_message",
                "message_id": message.tutor_message_id,
                "session_id": session_id,
                "role": message.role,
                "occurred_at": message.created_at.isoformat(),
            }
            transcript.append({"evidence_ref": message.tutor_message_id, "role": message.role, "content": message.content[:500]})
        return {"session_id": session_id, "learner_id": learner_id, "domain_id": practice.domain_id, "attempts": attempt_payload, "transcript": transcript, "refs": refs}

    def _candidate(self, evidence: dict[str, Any]) -> ReflectionCandidate:
        if not evidence["attempts"] and not evidence["transcript"]:
            return ReflectionCandidate(action="NOOP")
        if not (config.LLM_BASE_URL and config.LLM_API_KEY):
            raise RuntimeError("reflection_provider_not_configured")
        from app.services.llm_provider import llm_provider

        prompt = {
            "attempts": evidence["attempts"],
            "tutor_transcript": evidence["transcript"],
            "allowed_evidence_refs": list(evidence["refs"]),
        }
        result = llm_provider.chat(
            system_prompt=(
                "You are TiBan Memory Reflection. Return JSON only with action ADD, UPDATE, RESOLVE, or NOOP; kind, summary, topic_keys, concept_keys, confidence, evidence_refs. "
                "Use only provided evidence refs. Never diagnose, prescribe, expose answers, invent learner history, or store raw transcript. Prefer NOOP when the evidence is weak."
            ),
            user_prompt=json.dumps(prompt, ensure_ascii=False),
            temperature=0,
            max_tokens=350,
            allow_fallback=False,
        )
        if not result.ok:
            raise RuntimeError("reflection_provider_failed")
        try:
            return ReflectionCandidate.model_validate(json.loads(result.text))
        except Exception as exc:
            raise RuntimeError("reflection_candidate_invalid") from exc

    def _apply_candidate(self, job_id: str, candidate: ReflectionCandidate, evidence: dict[str, Any]) -> dict[str, Any]:
        invalid = set(candidate.evidence_refs) - set(evidence["refs"])
        if invalid:
            raise ValueError("reflection_evidence_refs_invalid")
        if candidate.action != "NOOP" and not candidate.evidence_refs:
            raise ValueError("reflection_evidence_required")
        if candidate.action != "NOOP":
            if candidate.kind is None:
                raise ValueError("reflection_kind_required")
            if len(candidate.summary.strip()) < 8:
                raise ValueError("reflection_summary_required")
        if candidate.summary and (len(candidate.summary.strip()) < 8 or re.search(r"(?:诊断|治疗方案|处方|prompt|api key)", candidate.summary, re.I)):
            raise ValueError("reflection_summary_unsafe")
        if candidate.action != "NOOP":
            self._validate_candidate_support(candidate, evidence)
        with SessionLocal() as session:
            job = session.get(BackgroundJobModel, job_id)
            assert job is not None
            practice = session.get(PracticeSessionModel, job.target_id)
            assert practice is not None
            version = int(job.detail.get("reflection_version", -1))
            if version != practice.reflection_version or not practice.reflection_dirty:
                job.status, job.stage, job.progress = "noop", "superseded", 100
                session.commit()
                return {"status": "noop", "job_id": job_id}
            if candidate.action == "NOOP":
                self._finish(session, job, practice, status="noop", memory_id=None)
                return {"status": "noop", "job_id": job_id}
            keys = [*candidate.topic_keys, *candidate.concept_keys]
            if not keys:
                raise ValueError("reflection_keys_required")
            dedupe = _dedupe_key(candidate.kind or "misconception", practice.learner_id, practice.domain_id, keys)
            item = session.scalar(select(LearningMemoryItemModel).where(
                LearningMemoryItemModel.learner_id == practice.learner_id,
                LearningMemoryItemModel.domain_id == practice.domain_id,
                LearningMemoryItemModel.dedupe_key == dedupe,
            ))
            refs = [evidence["refs"][ref] for ref in candidate.evidence_refs]
            now = datetime.utcnow()
            if item is None and candidate.action == "RESOLVE":
                self._finish(session, job, practice, status="noop", memory_id=None)
                return {"status": "noop", "job_id": job_id}
            if item is None and candidate.action == "UPDATE":
                # UPDATE is a lifecycle operation on an existing canonical
                # memory.  Treating it as ADD would let a stale or hallucinated
                # update candidate create a brand-new learner fact.
                self._finish(session, job, practice, status="noop", memory_id=None)
                return {"status": "noop", "job_id": job_id}
            if item is None:
                item = LearningMemoryItemModel(
                    memory_id=f"memory_{uuid4().hex[:12]}", learner_id=practice.learner_id, domain_id=practice.domain_id,
                    kind=candidate.kind or "misconception", summary=candidate.summary.strip(), status="active",
                    topic_keys=[value.strip() for value in candidate.topic_keys if value.strip()][:4],
                    concept_keys=[value.strip() for value in candidate.concept_keys if value.strip()][:6], confidence=candidate.confidence,
                    evidence_refs=_merge_evidence([], refs), source_type="memory_reflection", dedupe_key=dedupe,
                    version=1, first_seen_at=now, last_seen_at=now,
                )
                session.add(item)
            else:
                item.evidence_refs = _merge_evidence(list(item.evidence_refs or []), refs)
                item.last_seen_at = now
                item.confidence = candidate.confidence
                item.version += 1
                if candidate.action == "RESOLVE":
                    item.status = "resolved"
                else:
                    item.status = "active"
                    item.summary = candidate.summary.strip()
            self._finish(session, job, practice, status="completed", memory_id=item.memory_id)
            memory_id = item.memory_id
        try:
            semantic_memory_service.sync_memory(memory_id)
        except Exception:
            # Canonical memory is already committed. The vector state records
            # failure and can be rebuilt without losing the learning fact.
            pass
        return {"status": "completed", "job_id": job_id, "memory_id": memory_id}

    @staticmethod
    def _validate_candidate_support(candidate: ReflectionCandidate, evidence: dict[str, Any]) -> None:
        """Require candidate labels to be grounded in the referenced evidence.

        The model may summarize an event, but it may not introduce an unrelated
        topic or concept merely because the key is plausible in this domain.
        Evidence is limited to the attempt/transcript payload already collected
        for this session, never to the model's unseen context.
        """

        referenced = set(candidate.evidence_refs)
        attempt_rows = [
            row for row in evidence.get("attempts", [])
            if str(row.get("evidence_ref")) in referenced
        ]
        transcript_rows = [
            row for row in evidence.get("transcript", [])
            if str(row.get("evidence_ref")) in referenced
        ]
        if not attempt_rows and not transcript_rows:
            raise ValueError("reflection_evidence_refs_empty")

        evidence_text = json.dumps([attempt_rows, transcript_rows], ensure_ascii=False)
        evidence_terms = _terms(evidence_text)
        keys = [*candidate.topic_keys, *candidate.concept_keys]
        if not keys:
            raise ValueError("reflection_keys_required")
        unsupported = []
        for key in keys:
            clean = str(key).strip()
            compact_key = re.sub(r"\s+", "", clean).casefold()
            compact_evidence = re.sub(r"\s+", "", evidence_text).casefold()
            key_terms = _terms(clean)
            overlap = sum(min(count, evidence_terms.get(term, 0)) for term, count in key_terms.items())
            if not compact_key or (compact_key not in compact_evidence and overlap == 0):
                unsupported.append(clean)
        if unsupported:
            raise ValueError("reflection_keys_unsupported")

        if candidate.kind in {"repeated_mistake", "misconception", "confusing_concepts"}:
            has_incorrect_attempt = any(not bool(row.get("correct")) for row in attempt_rows)
            has_confusion_signal = any(
                extract_explicit_confusion(str(row.get("content") or "")) is not None
                for row in transcript_rows
            )
            if not has_incorrect_attempt and not has_confusion_signal:
                raise ValueError("reflection_signal_unsupported")

    @staticmethod
    def _finish(session: Any, job: BackgroundJobModel, practice: PracticeSessionModel, *, status: str, memory_id: str | None) -> None:
        job.status, job.stage, job.progress, job.completed_at = status, "completed" if status == "completed" else "noop", 100, datetime.utcnow()
        job.detail = {**dict(job.detail or {}), "memory_id": memory_id, "outcome": status}
        practice.reflection_dirty = False
        practice.reflection_status = status
        practice.last_reflected_at = datetime.utcnow()
        practice.last_reflection_event_id = job.idempotency_key
        session.commit()


memory_reflection_service = MemoryReflectionService()
