from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from app.db.database import SessionLocal
from app.db.models import AttemptModel, ReviewCardModel
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
