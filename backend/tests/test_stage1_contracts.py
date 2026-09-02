from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from app.db.database import SessionLocal
from app.db.bootstrap import initialize_database
from app.db.models import AttemptModel, LearnerMasteryModel, QuestionBankModel, QuestionModel, ReviewCardModel
from app.main import app
from app.schemas import QuestionPublic
from app.db.repositories import learner_visible_weak_topics
from app.services.stage1_service import stage1_service


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


def test_learner_visible_weak_topics_excludes_grading_labels_and_placeholder_metadata() -> None:
    bank = SimpleNamespace()
    attempts = [
        (SimpleNamespace(correct=False), SimpleNamespace(topic="酸碱", teaching_tags=["化学"], subject="化学"), bank),
        (SimpleNamespace(correct=False), SimpleNamespace(topic="不符合", teaching_tags=["补充章传统医学病证-模块1"], subject="中医科"), bank),
        (SimpleNamespace(correct=False), SimpleNamespace(topic=None, teaching_tags=[], subject="妇产科"), bank),
        (SimpleNamespace(correct=False), SimpleNamespace(topic=None, teaching_tags=[], subject="妇产科"), bank),
    ]

    assert learner_visible_weak_topics(attempts) == ["酸碱", "学科 · 妇产科"]


def test_learner_visible_weak_topics_does_not_promote_subject_copy_to_knowledge_point() -> None:
    bank = SimpleNamespace()
    attempts = [
        (SimpleNamespace(correct=False), SimpleNamespace(topic="不符合", teaching_tags=["中医科", "补充章传统医学病证-模块1"], subject="中医科"), bank),
        (SimpleNamespace(correct=False), SimpleNamespace(topic="不符合", teaching_tags=["中医科", "补充章传统医学病证-模块1"], subject="中医科"), bank),
    ]

    assert learner_visible_weak_topics(attempts) == ["学科 · 中医科"]


def test_missing_official_explanation_never_returns_grading_prose() -> None:
    missing = SimpleNamespace(official_explanation_available=False, explanation="评分规则不应显示")
    official = SimpleNamespace(official_explanation_available=True, explanation="题库提供的真实解析。")

    assert stage1_service._explanation(missing, correct=False, score=0, error_tags=["答案与当前评分规则不一致"]) == ""
    assert stage1_service._explanation(official, correct=True, score=100, error_tags=[]) == "题库提供的真实解析。"


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


def test_learner_catalog_exposes_only_formal_bank_and_its_pages_are_distinct() -> None:
    response = client.get("/api/v3/question-banks")
    assert response.status_code == 200
    banks = response.json()["items"]
    assert [bank["bank_id"] for bank in banks] == ["bank-cmexam-real"]

    first_items = client.get(
        "/api/v3/practice/questions", params={"bank_id": "bank-cmexam-real", "limit": 20, "offset": 0}
    ).json()["items"]
    second_items = client.get(
        "/api/v3/practice/questions", params={"bank_id": "bank-cmexam-real", "limit": 20, "offset": 20}
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


def test_zero_question_bank_is_not_learner_visible_or_startable() -> None:
    banks = client.get("/api/v3/question-banks").json()["items"]
    assert all(item["question_count"] > 0 for item in banks)
    assert client.get("/api/v3/question-banks/bank-colorectal-observation").status_code == 404

    response = client.post("/api/v3/practice/sessions", json={
        "learner_id": f"empty-bank-{uuid4().hex[:8]}",
        "bank_id": "bank-colorectal-observation",
        "mode": "study",
        "question_count": 20,
    })
    assert response.status_code == 404


def test_server_session_persists_random_membership_and_navigator_state() -> None:
    initialize_database()
    learner_id = f"session-membership-{uuid4().hex[:8]}"
    banks = client.get("/api/v3/question-banks").json()["items"]
    bank = next(item for item in banks if item["question_count"] >= 2)
    requested_count = 2
    created = client.post("/api/v3/practice/sessions", json={
        "learner_id": learner_id,
        "bank_id": bank["bank_id"],
        "mode": "study",
        "question_count": requested_count,
        "shuffle_seed": 20260828,
    })
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["question_count"] == requested_count
    assert len(payload["question_ids"]) == len(set(payload["question_ids"])) == requested_count

    detail = client.get(f"/api/v3/practice/sessions/{payload['session_id']}")
    assert detail.status_code == 200
    assert [item["ordinal"] for item in detail.json()["items"]] == list(range(requested_count))
    assert {item["state"] for item in detail.json()["items"]} == {"unanswered"}

    question = client.get(f"/api/v3/practice/questions/{payload['question_ids'][0]}").json()["item"]
    selected = question["options"][0]["id"] if question.get("options") else True
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


def test_v31_bank_progress_marks_and_review_are_unique_question_projections(monkeypatch) -> None:
    """A second attempt updates the same question state; it never inflates progress."""
    learner_id = f"v31-progress-{uuid4().hex[:8]}"
    banks = client.get("/api/v3/question-banks").json()["items"]
    bank = next(item for item in banks if item["bank_id"] == "bank-cmexam-real" or item["question_count"] >= 2)
    question = client.get("/api/v3/practice/questions", params={"bank_id": bank["bank_id"], "limit": 1}).json()["items"][0]
    answer = question["options"][0]["id"] if question.get("options") else True
    for _ in range(2):
        submitted = client.post("/api/v3/practice/submit", json={
            "learner_id": learner_id, "question_id": question["id"], "selected_answer": answer,
        })
        assert submitted.status_code == 200, submitted.text

    marked = client.put(f"/api/v3/questions/{question['id']}/mark", json={"learner_id": learner_id, "marked": True})
    assert marked.status_code == 200 and marked.json()["marked"] is True
    progress = client.get(f"/api/v3/question-banks/{bank['bank_id']}/questions", params={"learner_id": learner_id, "state": "completed"})
    assert progress.status_code == 200
    entry = next(item for item in progress.json()["items"] if item["question_id"] == question["id"])
    assert entry["attempt_count"] == 2
    assert entry["completed"] is True
    marked_items = client.get("/api/v3/review/items", params={"learner_id": learner_id, "tab": "marked"})
    assert marked_items.status_code == 200
    assert any(item["question_id"] == question["id"] for item in marked_items.json()["items"])

    # Review projections resolve learner-visible bank IDs once. If the old
    # per-question helper ever returns here, this regression test fails rather
    # than silently reintroducing an N+1 scan on large CMExam banks.
    def forbidden_test_only_bank(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("review must not call _test_only_bank per question")

    monkeypatch.setattr("app.db.repositories.Stage1Repository._test_only_bank", forbidden_test_only_bank)
    summary = client.get("/api/v3/review/summary", params={"learner_id": learner_id})
    assert summary.status_code == 200
    assert summary.json()["marked_count"] >= 1
    items = client.get("/api/v3/review/items", params={"learner_id": learner_id, "tab": "marked"})
    assert items.status_code == 200
    item = next(row for row in items.json()["items"] if row["question_id"] == question["id"])
    detail = client.get(f"/api/v3/review/items/{question['id']}", params={"learner_id": learner_id})
    assert detail.status_code == 200
    assert detail.json()["question_id"] == item["question_id"]
    session = client.post("/api/v3/review/sessions", json={"learner_id": learner_id, "tab": "marked", "question_count": 1})
    assert session.status_code == 200, session.text


def test_objective_submit_emits_timing_and_never_touches_llm_or_retrieval(monkeypatch) -> None:
    learner_id = f"v31-fast-submit-{uuid4().hex[:8]}"
    question = next(item for item in _all_questions() if item["question_type"] == "single_choice")

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("objective submit must not call an AI/RAG dependency")

    monkeypatch.setattr("app.services.llm_provider.LLMProvider.chat", forbidden)
    monkeypatch.setattr("app.services.rag_service.RagService.retrieve", forbidden)
    response = client.post("/api/v3/practice/submit", json={
        "learner_id": learner_id,
        "question_id": question["id"],
        "selected_answer": question["options"][0]["id"],
    })
    assert response.status_code == 200, response.text
    timing = response.headers.get("server-timing", "")
    for phase in ("question_load", "grade", "attempt_insert", "fsrs_update", "mastery_update", "memory_update", "serialize", "request_total"):
        assert f"{phase};dur=" in timing
