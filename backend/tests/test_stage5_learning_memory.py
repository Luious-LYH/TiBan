from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import AttemptModel, BackgroundJobModel, LearningMemoryItemModel, QuestionModel, ReviewCardModel, VectorIndexStateModel
from app.main import app
from app.services.memory_reflection_service import ReflectionCandidate, memory_reflection_service
from app.services.semantic_memory_service import semantic_memory_service


def _one_question_session(client: TestClient, learner_id: str) -> tuple[str, str]:
    """Create real session evidence; completion must queue Reflection."""

    response = client.post('/api/v3/practice/sessions', json={
        'learner_id': learner_id, 'bank_id': 'bank-cmexam-real', 'mode': 'study', 'question_count': 1,
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload['question_ids']) == 1
    return payload['session_id'], payload['question_ids'][0]


def _wrong_answer(question_id: str) -> object:
    with SessionLocal() as session:
        question = session.get(QuestionModel, question_id)
        assert question is not None
        grading = dict(question.grading_payload or {})
        if question.question_type == 'single_choice':
            expected = str(grading['correct_option_id'])
            return next(str(option['id']) for option in question.options if str(option['id']) != expected)
        if question.question_type == 'multiple_choice':
            expected = {str(value) for value in grading.get('correct_option_ids', [])}
            return [str(option['id']) for option in question.options if str(option['id']) not in expected][:1]
        if question.question_type == 'true_false':
            return not bool(grading.get('correct_value'))
        return '与题目评分要点无关的回答'


def _completed_session(client: TestClient, learner_id: str) -> tuple[str, str]:
    session_id, question_id = _one_question_session(client, learner_id)
    response = client.post('/api/v3/practice/submit', json={
        'learner_id': learner_id, 'session_id': session_id, 'question_id': question_id,
        'selected_answer': _wrong_answer(question_id), 'mode': 'study',
    })
    assert response.status_code == 200, response.text
    return session_id, question_id


def _queued_job(session_id: str) -> BackgroundJobModel:
    with SessionLocal() as session:
        row = session.scalar(select(BackgroundJobModel).where(
            BackgroundJobModel.target_id == session_id,
            BackgroundJobModel.job_type == 'memory_reflection',
        ))
        assert row is not None
        session.expunge(row)
        return row


def _valid_candidate(evidence: dict[str, object]) -> ReflectionCandidate:
    attempts = evidence['attempts']
    assert isinstance(attempts, list) and attempts
    first = attempts[0]
    assert isinstance(first, dict)
    topic_keys = first.get('topic_keys')
    assert isinstance(topic_keys, list) and topic_keys
    topic = str(topic_keys[0])
    return ReflectionCandidate(
        action='ADD', kind='repeated_mistake', summary=f'需要复盘「{topic}」涉及的基础概念区分。',
        topic_keys=[topic], concept_keys=[], confidence=.82,
        evidence_refs=[str(attempts[0]['evidence_ref'])],
    )


def test_completed_session_enqueues_validated_reflection_and_persists_canonical_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    learner_id = f'reflection-add-{uuid4().hex[:8]}'
    client = TestClient(app)
    session_id, question_id = _completed_session(client, learner_id)
    job = _queued_job(session_id)
    monkeypatch.setattr(memory_reflection_service, '_candidate', _valid_candidate)
    monkeypatch.setattr(semantic_memory_service, 'sync_memory', lambda _memory_id: None)

    outcome = memory_reflection_service.process(job.job_id)
    assert outcome['status'] == 'completed'
    with SessionLocal() as session:
        item = session.get(LearningMemoryItemModel, outcome['memory_id'])
        assert item is not None
        assert item.learner_id == learner_id and item.source_type == 'memory_reflection'
        assert item.evidence_refs and item.evidence_refs[0]['question_id'] == question_id
        assert session.get(BackgroundJobModel, job.job_id).status == 'completed'  # type: ignore[union-attr]


def test_invalid_reflection_evidence_never_writes_learning_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    learner_id = f'reflection-invalid-{uuid4().hex[:8]}'
    client = TestClient(app)
    session_id, _question_id = _completed_session(client, learner_id)
    job = _queued_job(session_id)
    monkeypatch.setattr(memory_reflection_service, '_candidate', lambda _evidence: ReflectionCandidate(
        action='ADD', kind='misconception', summary='这是一个有意义但引用无效的候选。',
        topic_keys=['测试'], confidence=.7, evidence_refs=['invented-reference'],
    ))
    with pytest.raises(ValueError, match='reflection_evidence_refs_invalid'):
        memory_reflection_service.process(job.job_id)
    with SessionLocal() as session:
        assert not list(session.scalars(select(LearningMemoryItemModel).where(LearningMemoryItemModel.learner_id == learner_id)))
        assert session.get(BackgroundJobModel, job.job_id).status == 'failed'  # type: ignore[union-attr]


def test_noop_and_failed_provider_do_not_fake_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    learner_id = f'reflection-noop-{uuid4().hex[:8]}'
    session_id, _question_id = _completed_session(client, learner_id)
    job = _queued_job(session_id)
    monkeypatch.setattr(memory_reflection_service, '_candidate', lambda _evidence: ReflectionCandidate(action='NOOP'))
    assert memory_reflection_service.process(job.job_id)['status'] == 'noop'

    session_id, _question_id = _completed_session(client, f'{learner_id}-failed')
    job = _queued_job(session_id)
    monkeypatch.setattr(memory_reflection_service, '_candidate', lambda _evidence: (_ for _ in ()).throw(RuntimeError('provider unavailable')))
    with pytest.raises(RuntimeError, match='provider unavailable'):
        memory_reflection_service.process(job.job_id)
    with SessionLocal() as session:
        assert session.get(BackgroundJobModel, job.job_id).status == 'failed'  # type: ignore[union-attr]


def test_semantic_memory_recall_is_learner_isolated_with_structured_fallback() -> None:
    first, second = f'reflection-a-{uuid4().hex[:8]}', f'reflection-b-{uuid4().hex[:8]}'
    with SessionLocal() as session:
        state = session.get(VectorIndexStateModel, 'learning_memory')
        if state is not None:
            state.status = 'stale'
        item = LearningMemoryItemModel(
            memory_id=f'memory_{uuid4().hex[:12]}', learner_id=first, domain_id='endoscopy', kind='misconception',
            summary='对反流相关概念的边界仍容易混淆。', status='active', topic_keys=['反流'], concept_keys=['边界'],
            confidence=.8, evidence_refs=[{'source_type': 'graded_attempt', 'attempt_id': 'attempt-test', 'session_id': 'session-test', 'question_id': 'cmexam_000001'}],
            source_type='memory_reflection', dedupe_key=f'test:{first}', version=1,
        )
        session.add(item)
        session.commit()
        first_items = semantic_memory_service.retrieve(session, learner_id=first, domain_id='endoscopy', query='反流概念怎么区分', limit=5)
        paraphrase_items = semantic_memory_service.retrieve(session, learner_id=first, domain_id='endoscopy', query='我对反流相关内容总是分不清', limit=5)
        second_items = semantic_memory_service.retrieve(session, learner_id=second, domain_id='endoscopy', query='反流概念怎么区分', limit=5)
        unrelated_items = semantic_memory_service.retrieve(session, learner_id=first, domain_id='endoscopy', query='量子纠缠的实验历史', limit=5)
    assert first_items and first_items[0]['memory_id'] == item.memory_id
    assert paraphrase_items and paraphrase_items[0]['memory_id'] == item.memory_id
    assert second_items == []
    assert unrelated_items == []


def test_clear_memory_preserves_attempt_and_review_history(monkeypatch: pytest.MonkeyPatch) -> None:
    learner_id = f'reflection-clear-{uuid4().hex[:8]}'
    client = TestClient(app)
    session_id, _question_id = _completed_session(client, learner_id)
    job = _queued_job(session_id)
    monkeypatch.setattr(memory_reflection_service, '_candidate', _valid_candidate)
    monkeypatch.setattr(semantic_memory_service, 'sync_memory', lambda _memory_id: None)
    memory_reflection_service.process(job.job_id)
    with SessionLocal() as session:
        attempts_before = len(list(session.scalars(select(AttemptModel).where(AttemptModel.learner_id == learner_id))))
        cards_before = len(list(session.scalars(select(ReviewCardModel).where(ReviewCardModel.learner_id == learner_id))))
    response = client.post('/api/v3/learning/memory/clear', json={'learner_id': learner_id})
    assert response.status_code == 200 and response.json()['superseded_count'] >= 1
    with SessionLocal() as session:
        assert len(list(session.scalars(select(AttemptModel).where(AttemptModel.learner_id == learner_id)))) == attempts_before
        assert len(list(session.scalars(select(ReviewCardModel).where(ReviewCardModel.learner_id == learner_id)))) == cards_before
