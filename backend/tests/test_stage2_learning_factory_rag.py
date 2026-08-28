from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fsrs import Card, Rating, Scheduler

from app.db.database import SessionLocal
from app.db.models import LearnerMasteryModel, ReviewCardModel
from app.main import app
from app.services.factory_service import (
    GeneratedDraft,
    GeneratorInput,
    ProviderFactoryError,
    _deterministic_gate,
    _generator,
    _judge,
    _provider_generator,
    _provider_judge,
    _normalize_provider_judge,
    import_allowed_document,
)
from app.services.llm_provider import LLMResult
from app.services.rag_service import Citation, _chunk_markdown


def test_fsrs_fixed_rating_sequence_is_deterministic() -> None:
    scheduler = Scheduler(enable_fuzzing=False)
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    snapshots = []
    for rating in (Rating.Again, Rating.Hard, Rating.Good, Rating.Easy):
        card, _ = scheduler.review_card(Card(), rating, review_datetime=now)
        snapshots.append((rating.name, card.difficulty, card.stability, card.due.isoformat()))
    assert [item[0] for item in snapshots] == ["Again", "Hard", "Good", "Easy"]
    assert all(item[2] is not None and item[3] for item in snapshots)
    assert snapshots == [
        (rating.name, Scheduler(enable_fuzzing=False).review_card(Card(), rating, review_datetime=now)[0].difficulty,
         Scheduler(enable_fuzzing=False).review_card(Card(), rating, review_datetime=now)[0].stability,
         Scheduler(enable_fuzzing=False).review_card(Card(), rating, review_datetime=now)[0].due.isoformat())
        for rating in (Rating.Again, Rating.Hard, Rating.Good, Rating.Easy)
    ]


def test_submit_rebuilds_mastery_and_real_fsrs_card() -> None:
    client = TestClient(app)
    learner = f"learning-{uuid4().hex[:8]}"
    question = client.get("/api/v3/practice/questions", params={"limit": 1}).json()["items"][0]
    response = client.post("/api/v3/practice/submit", json={"learner_id": learner, "question_id": question["id"], "selected_answer": question["options"][0]["id"]})
    assert response.status_code == 200
    with SessionLocal() as session:
        card = session.query(ReviewCardModel).filter_by(learner_id=learner, question_id=question["id"]).one()
        mastery = session.query(LearnerMasteryModel).filter_by(learner_id=learner).all()
        assert card.fsrs_card and card.difficulty is not None and card.stability is not None
        assert card.retrievability is not None and card.fsrs_logs[-1]["rating_name"] in {"Again", "Good"}
        assert mastery and mastery[0].attempt_count >= 1


def test_mentor_plan_changes_with_actual_learner_history() -> None:
    client = TestClient(app)
    first, second = f"mentor-a-{uuid4().hex[:6]}", f"mentor-b-{uuid4().hex[:6]}"
    questions = client.get("/api/v3/practice/questions", params={"limit": 3}).json()["items"]
    for question in questions[:2]:
        client.post("/api/v3/practice/submit", json={"learner_id": first, "question_id": question["id"], "selected_answer": question.get("options", [{"id": ""}])[0]["id"]})
    client.post("/api/v3/practice/submit", json={"learner_id": second, "question_id": questions[-1]["id"], "selected_answer": "错误且缺少观察依据"})
    plan_a = client.get("/api/v3/learning/mentor", params={"learner_id": first}).json()["plan"]
    plan_b = client.get("/api/v3/learning/mentor", params={"learner_id": second}).json()["plan"]
    assert plan_a["learner_id"] != plan_b["learner_id"]
    assert (plan_a["focus"], plan_a["recent_errors"], plan_a["due_review_count"]) != (plan_b["focus"], plan_b["recent_errors"], plan_b["due_review_count"])


def test_factory_schemas_keep_generator_judge_and_revision_inputs_separate(tmp_path: Path) -> None:
    uploaded = import_allowed_document("fixture.md", b"# Fixture\n\n## Evidence\n\nObservation-only training evidence must retain clinician review boundaries.", "text/markdown")
    assert uploaded["document_id"].startswith("doc_")
    evidence = "Observation-only training evidence must retain clinician review boundaries."
    draft = _generator(GeneratorInput(evidence=evidence, source_chunk_id="chunk-proof", source_document_id=uploaded["document_id"]))
    assert isinstance(draft, GeneratedDraft)
    assert _deterministic_gate(draft, evidence)[0]
    decision = _judge(draft, evidence)
    assert not decision.passed and decision.rewrite_instruction


def test_factory_provider_roles_are_schema_separated_and_never_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_chat(**kwargs: object) -> LLMResult:
        calls.append(kwargs)
        if "Generator" in str(kwargs["system_prompt"]):
            return LLMResult(
                True,
                json.dumps({
                    "title": "Provider draft", "stem": "哪项符合资料？",
                    "options": [{"id": "a", "text": "可见事实"}, {"id": "b", "text": "独立诊断"}],
                    "correct_option_id": "a", "explanation": "仅供教学训练或医生审核前辅助，不作为独立诊断依据。",
                    "teaching_tags": ["证据"],
                }),
                "provider", "local", "test-model", latency_ms=12,
            )
        return LLMResult(
            True,
            json.dumps({
                "passed": True, "groundedness": "pass", "answer_consistency": "pass",
                "citation_validity": "pass", "distractor_quality": "pass", "teaching_value": "pass",
                "rewrite_instruction": None,
            }),
            "provider", "local", "test-model", latency_ms=10,
        )

    monkeypatch.setattr("app.services.factory_service.llm_provider.chat", fake_chat)
    payload = GeneratorInput(evidence="可见事实必须保留医生复核边界，不能独立诊断。", source_chunk_id="chunk-provider", source_document_id="doc-provider")
    draft = _provider_generator(payload)
    decision = _provider_judge(draft, payload.evidence)

    assert draft.provider_mode == "provider" and draft.citation["chunk_id"] == "chunk-provider"
    assert decision.judge_mode == "provider" and decision.passed
    assert len(calls) == 2 and all(call["allow_fallback"] is False for call in calls)
    assert "Generator" in str(calls[0]["system_prompt"])
    assert "Judge" in str(calls[1]["system_prompt"])


def test_factory_provider_failure_is_not_converted_to_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.factory_service.llm_provider.chat",
        lambda **_: LLMResult(False, "", "provider", "local", "test", "http_502: gateway"),
    )
    with pytest.raises(ProviderFactoryError, match="generator_provider_failed"):
        _provider_generator(GeneratorInput(evidence="可见事实必须保留医生复核边界，不能独立诊断。", source_chunk_id="chunk-provider", source_document_id="doc-provider"))


def test_provider_judge_normalizes_explicit_chinese_wire_labels() -> None:
    normalized = _normalize_provider_judge({
        "overall": "通过", "groundedness": "通过", "answer_consistency": "通过",
        "citation_validity": "通过", "distractor_quality": "通过", "teaching_value": "通过",
    })
    assert normalized["passed"] is True
    assert all(normalized[key] == "pass" for key in ["groundedness", "answer_consistency", "citation_validity", "distractor_quality", "teaching_value"])


def test_rag_heading_chunks_and_frozen_benchmark_are_traceable() -> None:
    chunks = list(_chunk_markdown("# A\n甲乙丙丁\n# B\n戊己庚辛", 2))
    assert chunks == [("A", "甲乙"), ("A", "丙丁"), ("B", "戊己"), ("B", "庚辛")]
    fixture = json.loads((Path(__file__).resolve().parents[2] / "docs" / "fixtures" / "retrieval-eval-v1.json").read_text(encoding="utf-8"))
    assert len(fixture["queries"]) == 50
    assert {item["split"] for item in fixture["queries"]} == {"development", "test"}
    citation = Citation(chunk_id="chunk-1", document_name="source.md", page=1, section="观察记录的基本顺序", snippet="证据", score=.9)
    assert citation.document_name and citation.page == 1 and citation.section


@pytest.mark.parametrize("filename", ["bad.exe", "path/../bad.txt"])
def test_factory_rejects_disallowed_document_types(filename: str) -> None:
    with pytest.raises(ValueError):
        import_allowed_document(filename, b"not a document")
