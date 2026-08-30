from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import AttemptModel, LearningMemoryItemModel, QuestionModel, ReviewCardModel
from app.main import app
from app.services.agent_runtime import AgentContext, tutor_runner
from app.services.learning_memory_service import learning_memory_service
from app.services.stage1_service import stage1_service


QUESTION_ID = "endo_text_esophagus_reflux_single"


def _answers() -> tuple[str, str]:
    with SessionLocal() as session:
        question = session.get(QuestionModel, QUESTION_ID)
        assert question is not None
        correct = str(question.grading_payload["correct_option_id"])
        wrong = next(str(option["id"]) for option in question.options if str(option["id"]) != correct)
        return correct, wrong


def _submit(client: TestClient, learner_id: str, answer: str) -> None:
    response = client.post(
        "/api/v3/practice/submit",
        json={"learner_id": learner_id, "question_id": QUESTION_ID, "selected_answer": answer, "mode": "study"},
    )
    assert response.status_code == 200, response.text


def test_repeated_mistake_is_evidence_backed_deduplicated_then_resolved() -> None:
    learner_id = f"memory-lifecycle-{uuid4().hex[:8]}"
    correct, wrong = _answers()
    client = TestClient(app)
    for _ in range(3):
        _submit(client, learner_id, wrong)

    listed = client.get("/api/v3/learning/memory", params={"learner_id": learner_id}).json()
    assert listed["api_source"] == "backend"
    assert len(listed["items"]) >= 1
    memory = next(item for item in listed["items"] if item["kind"] == "repeated_mistake")
    assert memory["status"] == "active"
    assert memory["evidence_count"] >= 3

    # The same topic updates one fact instead of creating a second label.
    _submit(client, learner_id, wrong)
    with SessionLocal() as session:
        rows = list(session.scalars(select(LearningMemoryItemModel).where(
            LearningMemoryItemModel.learner_id == learner_id,
            LearningMemoryItemModel.kind == "repeated_mistake",
        )))
        assert len(rows) >= 1
        assert all(len(row.evidence_refs) >= 3 for row in rows)

    _submit(client, learner_id, correct)
    _submit(client, learner_id, correct)
    with SessionLocal() as session:
        resolved = list(session.scalars(select(LearningMemoryItemModel).where(
            LearningMemoryItemModel.learner_id == learner_id,
            LearningMemoryItemModel.kind == "repeated_mistake",
        )))
        assert resolved and any(item.status == "resolved" for item in resolved)


def test_memory_readback_is_relevant_and_isolated_per_learner() -> None:
    first, second = f"memory-a-{uuid4().hex[:8]}", f"memory-b-{uuid4().hex[:8]}"
    _, wrong = _answers()
    client = TestClient(app)
    for _ in range(3):
        _submit(client, first, wrong)

    with SessionLocal() as session:
        first_memory = learning_memory_service.retrieve_relevant(
            session, learner_id=first, question_id=QUESTION_ID, user_message="请解释这个知识点",
        )
        second_memory = learning_memory_service.retrieve_relevant(
            session, learner_id=second, question_id=QUESTION_ID, user_message="请解释这个知识点",
        )
    assert first_memory["namespace"] == "learner_memory_structured"
    assert first_memory["items"] and first_memory["selected_memory_ids"]
    assert not second_memory["items"]
    assert not ({item["memory_id"] for item in first_memory["items"]} & set(second_memory["selected_memory_ids"]))


def test_explicit_confusion_candidate_has_run_evidence_but_not_raw_chat() -> None:
    learner_id = f"memory-chat-{uuid4().hex[:8]}"
    message = "我总是分不清 Barrett 食管和反流性食管炎。"
    events = list(tutor_runner.stream(AgentContext(
        question_id=QUESTION_ID,
        learner_id=learner_id,
        user_message=message,
        phase="pre_submit",
    )))
    end = next(event for event in events if event.event == "message_end")
    assert end.data["trace"].get("candidate_memory_id")
    with SessionLocal() as session:
        item = session.scalar(select(LearningMemoryItemModel).where(
            LearningMemoryItemModel.learner_id == learner_id,
            LearningMemoryItemModel.kind == "confusing_concepts",
        ))
        assert item is not None
        assert item.evidence_refs[0]["tutor_run_id"].startswith("run_")
        assert message not in str(item.evidence_refs)
        assert message not in item.summary


def test_tutor_trace_uses_relevant_memory_without_answer_leakage() -> None:
    learner_id = f"memory-tutor-{uuid4().hex[:8]}"
    _, wrong = _answers()
    client = TestClient(app)
    for _ in range(3):
        _submit(client, learner_id, wrong)

    events = list(tutor_runner.stream(AgentContext(
        question_id=QUESTION_ID,
        learner_id=learner_id,
        user_message="请解释我为什么容易错，并给一个复习提示。",
        phase="pre_submit",
    )))
    tool_names = [event.data["tool_name"] for event in events if event.event == "tool_start"]
    end = next(event for event in events if event.event == "message_end")
    text = "".join(str(event.data.get("text", "")) for event in events if event.event == "token")
    assert "get_learning_memory" in tool_names
    assert end.data["trace"]["selected_memory_ids"]
    assert "correct_option_id" not in text
    assert "hidden rubric" not in text.lower()


def test_post_submit_tool_plan_keeps_grading_within_step_budget() -> None:
    context = AgentContext(
        question_id=QUESTION_ID,
        learner_id="memory-post-submit",
        user_message="请解释本次错误并结合历史安排复习。",
        phase="post_submit",
        attempt_id="attempt-placeholder",
    )
    selected = tutor_runner.gateway.select_tools(context, tutor_runner.registry.allowed("post_submit"))[: tutor_runner.max_steps]
    assert "get_grading_result" in selected


def test_memory_changes_selection_after_due_cards_are_not_due() -> None:
    learner_id = f"memory-selection-{uuid4().hex[:8]}"
    _, wrong = _answers()
    client = TestClient(app)
    for _ in range(3):
        _submit(client, learner_id, wrong)
    with SessionLocal() as session:
        question = session.get(QuestionModel, QUESTION_ID)
        assert question is not None
        for card in session.scalars(select(ReviewCardModel).where(ReviewCardModel.learner_id == learner_id)):
            card.due_at = datetime.utcnow() + timedelta(days=7)
        session.commit()
        bank_id = question.bank_id
    created = stage1_service.create_session(learner_id, bank_id, question_count=2, shuffle_seed=17)
    assert created["selection_strategy"] == "learning_memory"
    assert any("学习事实" in item for item in created["selection_evidence"])


def test_clear_memory_preserves_attempt_and_review_history() -> None:
    learner_id = f"memory-clear-{uuid4().hex[:8]}"
    _, wrong = _answers()
    client = TestClient(app)
    for _ in range(3):
        _submit(client, learner_id, wrong)
    with SessionLocal() as session:
        before_attempts = len(list(session.scalars(select(AttemptModel).where(AttemptModel.learner_id == learner_id))))
        before_cards = len(list(session.scalars(select(ReviewCardModel).where(ReviewCardModel.learner_id == learner_id))))
    response = client.post("/api/v3/learning/memory/clear", json={"learner_id": learner_id})
    assert response.status_code == 200 and response.json()["superseded_count"] >= 1
    with SessionLocal() as session:
        after_attempts = len(list(session.scalars(select(AttemptModel).where(AttemptModel.learner_id == learner_id))))
        after_cards = len(list(session.scalars(select(ReviewCardModel).where(ReviewCardModel.learner_id == learner_id))))
        assert after_attempts == before_attempts
        assert after_cards == before_cards
