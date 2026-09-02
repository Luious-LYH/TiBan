"""Small, evidence-backed cross-session learning memory for Stage 5.

Attempts, mastery rows, and FSRS cards remain the canonical learning state.
This module records only compact facts that are useful across sessions, and it
keeps their evidence and lifecycle inspectable.  It intentionally does not use
the medical RAG namespace, store raw conversation, or make model-driven writes.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AttemptModel, LearningMemoryItemModel, QuestionModel


REPEATED_MISTAKE_THRESHOLD = 3
RESOLUTION_CORRECT_THRESHOLD = 2
MAX_EVIDENCE_REFS = 12
MAX_RETRIEVED_MEMORIES = 3
MEMORY_NAMESPACE = "learner_memory_structured"
NON_MEMORY_TOPIC_KEYS = {"单选", "多选", "判断", "问答评分", "报告修改", "基础识别", "图像观察"}


def _clean_keys(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        normalized = clean.casefold()
        if clean and normalized not in seen:
            seen.add(normalized)
            result.append(clean)
    return result


def topic_keys_for_question(question: QuestionModel) -> list[str]:
    """Return a compact, deterministic topic projection for one question."""

    keys = _clean_keys([question.topic, *(question.teaching_tags or []), question.body_part])
    meaningful = [key for key in keys if key not in NON_MEMORY_TOPIC_KEYS]
    return (meaningful or keys)[:4]


def _dedupe_key(kind: str, learner_id: str, domain_id: str, keys: Iterable[str]) -> str:
    material = "|".join([kind, learner_id, domain_id, *sorted(item.casefold() for item in _clean_keys(keys))])
    return f"{kind}:{hashlib.sha256(material.encode('utf-8')).hexdigest()[:24]}"


def _attempt_ref(attempt: AttemptModel, *, topic_key: str) -> dict[str, str]:
    """Reference a graded event without retaining the submitted answer."""

    return {
        "source_type": "graded_attempt",
        "attempt_id": attempt.attempt_id,
        "session_id": attempt.practice_session_id,
        "question_id": attempt.question_id,
        "topic_key": topic_key,
        "outcome": "correct" if attempt.correct else "incorrect",
        "occurred_at": attempt.created_at.isoformat(),
    }


def _merge_evidence(existing: list[dict[str, Any]], additional: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_identity: dict[str, dict[str, Any]] = {}
    for item in [*existing, *additional]:
        if not isinstance(item, dict):
            continue
        identity = str(item.get("attempt_id") or item.get("tutor_run_id") or item.get("message_id") or "")
        if identity:
            by_identity[identity] = item
    return sorted(
        by_identity.values(),
        key=lambda item: str(item.get("occurred_at") or item.get("captured_at") or ""),
    )[-MAX_EVIDENCE_REFS:]


def _safe_concept(value: str) -> str | None:
    clean = re.sub(r"\s+", " ", value).strip(" ，,。；;：:")
    if not (2 <= len(clean) <= 40):
        return None
    if not re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9·()（）\- /]+", clean):
        return None
    forbidden = ("答案", "rubric", "prompt", "secret", "密码", "api key", "服务器")
    if any(item in clean.casefold() for item in forbidden):
        return None
    return clean


def extract_explicit_confusion(message: str) -> tuple[str, str] | None:
    """Extract only an explicit, bounded 'X vs Y' confusion statement.

    This is intentionally deterministic and conservative.  It does not infer
    a misconception from arbitrary chat, and it returns no raw message.
    """

    patterns = (
        r"(?:总是|一直|经常)?\s*分不清\s*(?P<left>[\u4e00-\u9fffA-Za-z0-9·()（）\- /]{2,40})\s*(?:和|与|、|vs\.?|/)+\s*(?P<right>[\u4e00-\u9fffA-Za-z0-9·()（）\- /]{2,40})",
        r"(?:把)?\s*(?P<left>[\u4e00-\u9fffA-Za-z0-9·()（）\- /]{2,40})\s*(?:和|与|、|vs\.?|/)+\s*(?P<right>[\u4e00-\u9fffA-Za-z0-9·()（）\- /]{2,40})\s*(?:分不清|容易混淆|总混淆)",
    )
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if not match:
            continue
        left = _safe_concept(match.group("left"))
        right = _safe_concept(match.group("right"))
        if left and right and left.casefold() != right.casefold():
            return tuple(sorted((left, right), key=str.casefold))
    return None


class LearningMemoryService:
    """Lifecycle operations for the single Stage 5 memory entity."""

    def consolidate_attempt(self, session: Session, *, attempt: AttemptModel, question: QuestionModel) -> list[LearningMemoryItemModel]:
        """Write or resolve strong repeated-mistake facts after grading.

        The caller has already recorded an immutable attempt, rebuilt mastery,
        and updated FSRS.  This preserves the deterministic submit ordering:
        grade -> Attempt -> mastery -> FSRS -> memory consolidation.
        """

        affected: list[LearningMemoryItemModel] = []
        # This remains in the deterministic submit transaction, but avoids one
        # full learner-history query per topic key.
        domain_history = list(
            session.execute(
                select(AttemptModel, QuestionModel)
                .join(QuestionModel, QuestionModel.question_id == AttemptModel.question_id)
                .where(AttemptModel.learner_id == attempt.learner_id, QuestionModel.domain_id == question.domain_id)
                .order_by(AttemptModel.created_at)
            ).all()
        )
        for topic_key in topic_keys_for_question(question):
            history = [
                (row_attempt, row_question)
                for row_attempt, row_question in domain_history
                if topic_key.casefold() in {item.casefold() for item in topic_keys_for_question(row_question)}
            ]
            incorrect = [(row_attempt, row_question) for row_attempt, row_question in history if not row_attempt.correct]
            if len(incorrect) < REPEATED_MISTAKE_THRESHOLD:
                continue
            record = self._memory_by_key(session, attempt.learner_id, question.domain_id, "repeated_mistake", [topic_key])
            latest_incorrect_at = max(row_attempt.created_at for row_attempt, _ in incorrect)
            correct_after_error = [
                row_attempt
                for row_attempt, _ in history
                if row_attempt.correct and row_attempt.created_at > latest_incorrect_at
            ]
            refs = [_attempt_ref(row_attempt, topic_key=topic_key) for row_attempt, _ in history]
            if record is None:
                record = LearningMemoryItemModel(
                    memory_id=f"memory_{uuid4().hex[:12]}",
                    learner_id=attempt.learner_id,
                    domain_id=question.domain_id,
                    kind="repeated_mistake",
                    topic_keys=[topic_key],
                    concept_keys=[],
                    summary=f"「{topic_key}」相关题目出现多次错误，下一轮建议先巩固基础观察与区分依据。",
                    status="active",
                    confidence=min(0.95, 0.55 + len(incorrect) * 0.1),
                    evidence_refs=_merge_evidence([], refs),
                    source_type="graded_attempt",
                    dedupe_key=_dedupe_key("repeated_mistake", attempt.learner_id, question.domain_id, [topic_key]),
                    version=1,
                    first_seen_at=incorrect[0][0].created_at,
                    last_seen_at=attempt.created_at,
                )
                session.add(record)
            else:
                record.evidence_refs = _merge_evidence(list(record.evidence_refs or []), refs)
                record.last_seen_at = attempt.created_at
                record.confidence = min(0.95, 0.55 + len(incorrect) * 0.1)
                record.version += 1
                if record.status == "resolved" and not attempt.correct:
                    record.status = "active"
                    record.summary = f"「{topic_key}」再次出现错误，下一轮建议回到基础观察与区分依据。"
            if record.status == "active" and len(correct_after_error) >= RESOLUTION_CORRECT_THRESHOLD:
                record.status = "resolved"
                record.summary = f"「{topic_key}」此前的反复错误已获得连续正确复习证据。"
                record.last_seen_at = correct_after_error[-1].created_at
                record.version += 1
            affected.append(record)
        return affected

    def record_explicit_confusion(
        self,
        session: Session,
        *,
        learner_id: str,
        question: QuestionModel,
        message: str,
        tutor_run_id: str,
        captured_at: datetime | None = None,
    ) -> LearningMemoryItemModel | None:
        """Persist an explicit, validated learner confusion fact, never raw chat."""

        concepts = extract_explicit_confusion(message)
        if concepts is None:
            return None
        now = captured_at or datetime.utcnow()
        record = self._memory_by_key(session, learner_id, question.domain_id, "confusing_concepts", concepts)
        evidence = {
            "source_type": "explicit_chat",
            "tutor_run_id": tutor_run_id,
            "question_id": question.question_id,
            "topic_keys": topic_keys_for_question(question),
            "captured_at": now.isoformat(),
        }
        if record is None:
            record = LearningMemoryItemModel(
                memory_id=f"memory_{uuid4().hex[:12]}",
                learner_id=learner_id,
                domain_id=question.domain_id,
                kind="confusing_concepts",
                topic_keys=topic_keys_for_question(question),
                concept_keys=list(concepts),
                summary=f"需要区分「{concepts[0]}」与「{concepts[1]}」的关键差异。",
                status="active",
                confidence=0.65,
                evidence_refs=[evidence],
                source_type="explicit_chat",
                dedupe_key=_dedupe_key("confusing_concepts", learner_id, question.domain_id, concepts),
                version=1,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(record)
        else:
            record.evidence_refs = _merge_evidence(list(record.evidence_refs or []), [evidence])
            record.status = "active"
            record.last_seen_at = now
            record.version += 1
        return record

    def retrieve_relevant(
        self,
        session: Session,
        *,
        learner_id: str,
        question_id: str,
        user_message: str = "",
        limit: int = MAX_RETRIEVED_MEMORIES,
    ) -> dict[str, Any]:
        """Return only relevant active facts from the requesting learner."""

        question = session.get(QuestionModel, question_id)
        if question is None:
            raise KeyError("question not found")
        question_topics = {item.casefold() for item in topic_keys_for_question(question)}
        query = user_message.casefold()
        candidates = list(
            session.scalars(
                select(LearningMemoryItemModel)
                .where(
                    LearningMemoryItemModel.learner_id == learner_id,
                    LearningMemoryItemModel.domain_id == question.domain_id,
                    LearningMemoryItemModel.status == "active",
                )
                .order_by(LearningMemoryItemModel.last_seen_at.desc())
                .limit(20)
            )
        )

        ranked: list[tuple[int, LearningMemoryItemModel, str]] = []
        for item in candidates:
            memory_topics = {str(value).casefold() for value in (item.topic_keys or [])}
            concept_match = any(str(value).casefold() in query for value in (item.concept_keys or []) if str(value).strip())
            if question_topics & memory_topics:
                ranked.append((2 + int(concept_match), item, "current_topic_match"))
            elif concept_match:
                ranked.append((1, item, "query_concept_match"))
        ranked.sort(key=lambda value: (value[0], value[1].last_seen_at), reverse=True)
        selected = ranked[: max(1, min(limit, MAX_RETRIEVED_MEMORIES))]
        items = [self.public_item(item) for _, item, _ in selected]
        return {
            "namespace": MEMORY_NAMESPACE,
            "items": items,
            "candidate_memory_ids": [item.memory_id for item in candidates],
            "selected_memory_ids": [item.memory_id for _, item, _ in selected],
            "profile_version": f"memory-v{max((item.version for item in candidates), default=0)}",
            "memory_token_count": sum(max(1, len(str(item["summary"])) // 4) for item in items),
            "personalization_reason": selected[0][2] if selected else "no_relevant_memory",
        }

    def list_for_learner(self, session: Session, *, learner_id: str, domain_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        filters = [LearningMemoryItemModel.learner_id == learner_id, LearningMemoryItemModel.status == "active"]
        if domain_id:
            filters.append(LearningMemoryItemModel.domain_id == domain_id)
        rows = list(
            session.scalars(
                select(LearningMemoryItemModel)
                .where(*filters)
                .order_by(LearningMemoryItemModel.last_seen_at.desc())
                .limit(max(1, min(limit, 10)))
            )
        )
        return [self.public_item(item) for item in rows]

    def clear_for_learner(self, session: Session, *, learner_id: str, domain_id: str | None = None) -> int:
        """Supersede active memory only; attempts and review history remain intact."""

        filters = [LearningMemoryItemModel.learner_id == learner_id, LearningMemoryItemModel.status == "active"]
        if domain_id:
            filters.append(LearningMemoryItemModel.domain_id == domain_id)
        rows = list(session.scalars(select(LearningMemoryItemModel).where(*filters)))
        for item in rows:
            item.status = "superseded"
            item.version += 1
        return len(rows)

    @staticmethod
    def public_item(item: LearningMemoryItemModel) -> dict[str, Any]:
        return {
            "memory_id": item.memory_id,
            "domain_id": item.domain_id,
            "kind": item.kind,
            "summary": item.summary,
            "status": item.status,
            "topic_keys": list(item.topic_keys or []),
            "concept_keys": list(item.concept_keys or []),
            "first_seen_at": item.first_seen_at.isoformat(),
            "last_seen_at": item.last_seen_at.isoformat(),
            "evidence_count": len(item.evidence_refs or []),
        }

    @staticmethod
    def _topic_attempt_history(session: Session, learner_id: str, domain_id: str, topic_key: str) -> list[tuple[AttemptModel, QuestionModel]]:
        rows = list(
            session.execute(
                select(AttemptModel, QuestionModel)
                .join(QuestionModel, QuestionModel.question_id == AttemptModel.question_id)
                .where(AttemptModel.learner_id == learner_id, QuestionModel.domain_id == domain_id)
                .order_by(AttemptModel.created_at)
            ).all()
        )
        return [
            (attempt, question)
            for attempt, question in rows
            if topic_key.casefold() in {item.casefold() for item in topic_keys_for_question(question)}
        ]

    @staticmethod
    def _memory_by_key(session: Session, learner_id: str, domain_id: str, kind: str, keys: Iterable[str]) -> LearningMemoryItemModel | None:
        return session.scalar(
            select(LearningMemoryItemModel).where(
                LearningMemoryItemModel.learner_id == learner_id,
                LearningMemoryItemModel.domain_id == domain_id,
                LearningMemoryItemModel.dedupe_key == _dedupe_key(kind, learner_id, domain_id, keys),
            )
        )


learning_memory_service = LearningMemoryService()
