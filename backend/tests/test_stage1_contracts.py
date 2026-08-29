from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from app.db.database import SessionLocal
from app.db.bootstrap import initialize_database
from app.db.models import AttemptModel, LearnerMasteryModel, QuestionBankModel, QuestionModel, ReviewCardModel
from app.main import app
from app.schemas import QuestionPublic


client = TestClient(app)
PUBLIC_ADAPTER = TypeAdapter(QuestionPublic)
SENSITIVE_KEYS = {
    "answer",
    "correct_option_id",
    "correct_option_ids",
    "hidden_rubric",
    "reference_answer",
    "benchmark_target",
    "expected_facts",
}


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _walk_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _walk_keys(item)}
    return set()


def _all_questions() -> list[dict[str, Any]]:
    response = client.get("/api/v3/practice/questions", params={"limit": 100})
    assert response.status_code == 200
    return response.json()["items"]


def test_public_question_contract_is_discriminated_and_answer_isolated() -> None:
    response = client.get("/api/v3/practice/questions", params={"limit": 100})
    assert response.status_code == 200
    payload = response.json()
    assert not (_walk_keys(payload) & SENSITIVE_KEYS)

    first = payload["items"][0]
    validated = PUBLIC_ADAPTER.validate_python(first)
    assert validated.question_type in {"single_choice", "multiple_choice", "true_false", "short_answer"}

    detail = client.get(f"/api/v3/practice/questions/{first['id']}")
    assert detail.status_code == 200
    assert not (_walk_keys(detail.json()) & SENSITIVE_KEYS)

    try:
        PUBLIC_ADAPTER.validate_python({**first, "answer": "should be rejected"})
    except ValidationError:
        pass
    else:
        raise AssertionError("QuestionPublic accepted a private answer field")


def test_openapi_exposes_four_question_variants() -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    for name in (
        "SingleChoiceQuestionPublic",
        "MultipleChoiceQuestionPublic",
        "TrueFalseQuestionPublic",
        "ShortAnswerQuestionPublic",
    ):
        assert name in schemas
        assert schemas[name]["properties"]["question_type"]["const"] in {
            "single_choice",
            "multiple_choice",
            "true_false",
            "short_answer",
        }

    question_union = schemas.get("QuestionPublic")
    if question_union:
        assert question_union.get("discriminator", {}).get("propertyName") == "question_type"


def test_banks_return_distinct_question_sets() -> None:
    response = client.get("/api/v3/question-banks")
    assert response.status_code == 200
    banks = response.json()["items"]
    assert len(banks) >= 2

    first_items = client.get(
        "/api/v3/practice/questions", params={"bank_id": banks[0]["bank_id"], "limit": 100}
    ).json()["items"]
    second_items = client.get(
        "/api/v3/practice/questions", params={"bank_id": banks[1]["bank_id"], "limit": 100}
    ).json()["items"]
    assert first_items and second_items
    assert {item["id"] for item in first_items}.isdisjoint({item["id"] for item in second_items})


def test_four_question_types_accept_typed_submission_and_persist_side_effects() -> None:
    by_type: dict[str, dict[str, Any]] = {}
    for item in _all_questions():
        by_type.setdefault(item["question_type"], item)
    assert set(by_type) == {"single_choice", "multiple_choice", "true_false", "short_answer"}

    learner_id = f"stage1-contract-{uuid4().hex[:8]}"
    for question_type, item in by_type.items():
        if question_type == "single_choice":
            selected: Any = item["options"][0]["id"]
        elif question_type == "multiple_choice":
            selected = [item["options"][0]["id"]]
        elif question_type == "true_false":
            selected = False
        else:
            selected = "观察黏膜形态并保留医生复核边界"

        response = client.post(
            "/api/v3/practice/submit",
            json={
                "question_id": item["id"],
                "selected_answer": selected,
                "learner_id": learner_id,
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["question_id"] == item["id"]
        assert not (_walk_keys(result) & SENSITIVE_KEYS)

    with SessionLocal() as session:
        attempts = session.query(AttemptModel).filter_by(learner_id=learner_id).all()
        review_cards = session.query(ReviewCardModel).filter_by(learner_id=learner_id).all()
        assert len(attempts) == 4
        assert len(review_cards) == 4


def test_overview_banks_are_serializable_public_contract() -> None:
    response = client.get("/api/v3/overview")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["api_source"] == "backend"
    assert payload["banks"]
    assert all("bank_id" in bank and "question_count" in bank for bank in payload["banks"])
    assert not (_walk_keys(payload) & SENSITIVE_KEYS)


def test_server_session_persists_random_membership_and_navigator_state() -> None:
    initialize_database()
    learner_id = f"session-membership-{uuid4().hex[:8]}"
    created = client.post("/api/v3/practice/sessions", json={
        "learner_id": learner_id,
        "bank_id": "bank-cmexam-real",
        "mode": "study",
        "question_count": 50,
        "shuffle_seed": 20260828,
    })
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["question_count"] == 50
    assert len(payload["question_ids"]) == len(set(payload["question_ids"])) == 50

    detail = client.get(f"/api/v3/practice/sessions/{payload['session_id']}")
    assert detail.status_code == 200
    assert [item["ordinal"] for item in detail.json()["items"]] == list(range(50))
    assert {item["state"] for item in detail.json()["items"]} == {"unanswered"}

    question = client.get(f"/api/v3/practice/questions/{payload['question_ids'][0]}").json()["item"]
    selected = question["options"][0]["id"] if question["options"] else True
    submitted = client.post("/api/v3/practice/submit", json={
        "learner_id": learner_id,
        "session_id": payload["session_id"],
        "question_id": question["id"],
        "selected_answer": selected,
        "mode": "study",
    })
    assert submitted.status_code == 200, submitted.text
    refreshed = client.get(f"/api/v3/practice/sessions/{payload['session_id']}").json()
    assert refreshed["items"][0]["state"] in {"correct", "incorrect"}


def test_adaptive_session_reuses_attempt_mastery_and_review_state_without_new_schema() -> None:
    """A wrong Topic A answer must change the next canonical session selection."""

    suffix = uuid4().hex[:8]
    bank_id = f"adaptive-bank-{suffix}"
    focus_id = f"adaptive-focus-{suffix}"
    sibling_id = f"adaptive-sibling-{suffix}"
    coverage_id = f"adaptive-coverage-{suffix}"
    learner_id = f"adaptive-learner-{suffix}"

    def question(question_id: str, title: str, tags: list[str]) -> QuestionModel:
        return QuestionModel(
            question_id=question_id,
            bank_id=bank_id,
            domain_id="endoscopy",
            question_type="single_choice",
            modality="text",
            title=title,
            stem=f"{title} 的观察练习",
            case_summary="测试用教学摘要。",
            image_url=None,
            image_alt=None,
            difficulty="easy",
            complexity=1,
            question_class="基础识别",
            task="观察训练",
            body_part="胃",
            source_type="test",
            source_dataset="test",
            citation_note="测试来源。",
            options=[{"id": "a", "text": "错误选项"}, {"id": "b", "text": "正确选项"}],
            grading_payload={"correct_option_id": "b"},
            explanation="测试解析。",
            teaching_tags=tags,
            expected_keywords=[],
            false_premise=False,
            doctor_review_required=True,
            safety_notice="仅供教学研修或医生复核前辅助，不作为独立诊断依据。",
            business_usage="user_ready",
            answer_source="dataset_gold",
            explanation_source="none",
            official_explanation_available=False,
        )

    with SessionLocal() as session:
        session.add(QuestionBankModel(
            bank_id=bank_id,
            domain_id="endoscopy",
            name="自适应闭环测试题库",
            description="用于证明下一次选题读取已有学习状态。",
            version="test-v1",
            status="published",
            question_count=3,
            question_type_counts={"single_choice": 3},
            modality_counts={"text": 3},
            body_parts=["胃"],
        ))
        session.add_all([
            question(focus_id, "Topic A 初始题", ["Topic A"]),
            question(sibling_id, "Topic A 巩固题", ["Topic A"]),
            question(coverage_id, "Topic B 覆盖题", ["Topic B"]),
        ])
        session.commit()

    submitted = client.post("/api/v3/practice/submit", json={
        "learner_id": learner_id,
        "question_id": focus_id,
        "selected_answer": "a",
        "mode": "study",
    })
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["is_correct"] is False

    # Isolate weak-topic selection from the separately-tested due-review tier.
    with SessionLocal() as session:
        mastery = session.query(LearnerMasteryModel).filter_by(learner_id=learner_id, knowledge_point="Topic A").one()
        assert mastery.mastery_score == 0
        card = session.query(ReviewCardModel).filter_by(learner_id=learner_id, question_id=focus_id).one()
        card.due_at = datetime.utcnow() + timedelta(days=7)
        session.commit()

    created = client.post("/api/v3/practice/sessions", json={
        "learner_id": learner_id,
        "bank_id": bank_id,
        "mode": "study",
        "question_count": 2,
        "shuffle_seed": 20260829,
    })
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["selection_strategy"] == "weak_topic"
    assert payload["question_ids"][0] in {focus_id, sibling_id}
    assert "Topic A" in payload["selection_reason"]
    assert any("Topic A" in item for item in payload["selection_evidence"])

    # The learner-facing list endpoint must return the authoritative persisted
    # membership/order, not a client-side slice of the bank catalog.
    session_questions = client.get("/api/v3/practice/questions", params={
        "bank_id": bank_id,
        "session_id": payload["session_id"],
        "limit": 100,
    })
    assert session_questions.status_code == 200, session_questions.text
    assert [item["id"] for item in session_questions.json()["items"]] == payload["question_ids"]
