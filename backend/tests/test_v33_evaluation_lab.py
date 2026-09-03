from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from uuid import uuid4

from app.db.database import SessionLocal
from app.main import app
from app.db.models import BackgroundJobModel, DocumentVersionModel, EvalExperimentModel, EvalLabCaseModel, EvalLabRunModel, EvalRagProfileModel, EvalSuiteModel, KnowledgeChunkModel, QuestionBankModel, QuestionModel, SourceDocumentModel
from app.services.evaluation_lab_service import evaluation_lab_service
from app.services.model_discovery_service import model_discovery_service
from app.services.llm_provider import LLMResult
from app.services.rag_service import Citation, RetrievalProfile


_TEST_BANK_ID = "test-v33-evaluation-bank"


def _eligible_bank() -> QuestionBankModel:
    with SessionLocal() as session:
        bank = session.get(QuestionBankModel, _TEST_BANK_ID)
        if bank is None:
            bank = QuestionBankModel(
                bank_id=_TEST_BANK_ID, domain_id="general_science", name="V3.3 evaluation test bank",
                description="isolated test inventory", version="test-v1", status="published", question_count=2,
                question_type_counts={"single_choice": 2}, modality_counts={"text": 2}, body_parts=[],
            )
            session.add(bank)
            for index, answer in enumerate(("opt_a", "opt_b"), start=1):
                session.add(QuestionModel(
                    question_id=f"test-v33-eval-question-{index}", bank_id=_TEST_BANK_ID,
                    domain_id="general_science", question_type="single_choice", modality="text",
                    title=f"Evaluation test {index}", stem=f"Choose the expected option for {index}.",
                    case_summary="Test-only evaluation question", difficulty="easy", body_part="general",
                    source_type="integration", source_dataset="test", citation_note="test",
                    options=[{"id": "opt_a", "text": "A"}, {"id": "opt_b", "text": "B"}],
                    grading_payload={"correct_option_id": answer}, explanation="Test", teaching_tags=[],
                    expected_keywords=[], doctor_review_required=False, safety_notice="test",
                    business_usage="user_ready",
                ))
            session.commit()
        return bank


def _indexed_knowledge_snapshot() -> None:
    """Give the RAG-run regression one real frozen version to pass through."""
    with SessionLocal() as session:
        if session.get(SourceDocumentModel, "test-v33-knowledge") is not None:
            return
        session.add(SourceDocumentModel(
            document_id="test-v33-knowledge", domain_id="general_science", bank_id=None,
            name="V3.3 retrieval fixture", media_type="text/markdown", content_hash="test-doc-hash",
            status="ready", business_usage="knowledge_base", license_gate_status="allow",
            ai_ingestion_allowed=True, namespace="general_learning", enabled=True,
        ))
        session.add(DocumentVersionModel(
            version_id="test-v33-knowledge-version", document_id="test-v33-knowledge",
            version_label="v1", source_path="test://v33-knowledge", content_hash="test-version-hash",
            parser="test", status="indexed",
        ))
        session.add(KnowledgeChunkModel(
            chunk_id="test-v33-knowledge-chunk", document_id="test-v33-knowledge",
            version_id="test-v33-knowledge-version", parent_section="Fixture", page=1, ordinal=0,
            content="Test retrieval context.", content_hash="test-chunk-hash", token_count=5,
            namespace="general_learning",
        ))
        session.commit()


def test_suite_is_deterministic_but_resampling_keeps_immutable_history() -> None:
    bank = _eligible_bank()
    first = evaluation_lab_service.create_suite(bank_id=bank.bank_id, sample_size=3, seed=713)
    second = evaluation_lab_service.create_suite(bank_id=bank.bank_id, sample_size=3, seed=713)
    fresh = evaluation_lab_service.create_suite(bank_id=bank.bank_id, sample_size=3, seed=714)
    assert first["suite_id"] != second["suite_id"]
    assert first["suite_hash"] == second["suite_hash"]
    assert first["suite_hash"] != fresh["suite_hash"]


def test_model_run_uses_runtime_no_fallback_and_separates_invalid_from_provider_failure(monkeypatch) -> None:
    bank = _eligible_bank()
    suite = evaluation_lab_service.create_suite(bank_id=bank.bank_id, sample_size=2, seed=714)
    monkeypatch.setattr(evaluation_lab_service, "_dispatch", lambda _run_id: None)
    experiment = evaluation_lab_service.create_model_experiment(suite_id=suite["suite_id"], models=["candidate-model"])
    calls: list[dict[str, object]] = []
    outcomes = iter([
        LLMResult(True, "not typed", "configured", "runtime", "candidate-model", latency_ms=17, usage={"total_tokens": 7}),
        LLMResult(False, "", "configured", "runtime", "candidate-model", "http_502", latency_ms=19),
    ])

    def fake_chat(**kwargs):
        calls.append(kwargs)
        return next(outcomes)

    monkeypatch.setattr("app.services.evaluation_lab_service.llm_provider.chat", fake_chat)
    run_id = experiment["runs"][0]["run_id"]
    evaluation_lab_service.process_run(run_id)
    result = evaluation_lab_service.experiment(experiment["experiment_id"])["runs"][0]
    assert calls and all(call["temperature"] == 0 and call["allow_fallback"] is False for call in calls)
    assert result["aggregate"]["valid_response_rate"] == 0.0
    assert result["aggregate"]["provider_success_rate"] == 0.5
    with SessionLocal() as session:
        run = session.get(EvalLabRunModel, run_id)
        assert run is not None and run.status == "completed"
        job = session.get(BackgroundJobModel, run.job_id)
        assert job is not None and "key" not in str(job.detail).lower()
        assert "key" not in str(run.aggregate).lower()


def test_custom_model_connection_reaches_runtime_without_persisting_key(monkeypatch) -> None:
    bank = _eligible_bank()
    suite = evaluation_lab_service.create_suite(bank_id=bank.bank_id, sample_size=1, seed=716)
    monkeypatch.setattr(evaluation_lab_service, "_dispatch", lambda _run_id: None)
    monkeypatch.setattr(
        "app.services.evaluation_lab_service.llm_provider.preflight",
        lambda _base_url: {"ok": True},
    )
    experiment = evaluation_lab_service.create_model_experiment(
        suite_id=suite["suite_id"], models=["custom-model"],
        base_url="https://provider.example/v1/", api_key="secret-for-one-run", provider="custom",
    )
    run_id = experiment["runs"][0]["run_id"]
    calls: list[dict[str, object]] = []

    def fake_chat(**kwargs):
        calls.append(kwargs)
        return LLMResult(True, '{"answer":"A"}', "provider", "custom", "custom-model", latency_ms=9, usage={"total_tokens": 4})

    monkeypatch.setattr("app.services.evaluation_lab_service.llm_provider.chat", fake_chat)
    evaluation_lab_service.process_run(run_id)
    assert calls and calls[0]["base_url"] == "https://provider.example/v1"
    assert calls[0]["api_key"] == "secret-for-one-run"
    assert calls[0]["model"] == "custom-model"
    assert calls[0]["allow_fallback"] is False
    with SessionLocal() as session:
        run = session.get(EvalLabRunModel, run_id)
        assert run is not None
        assert run.provider_base_url == "https://provider.example/v1"
        assert "secret-for-one-run" not in str(run.__dict__)
        job = session.get(BackgroundJobModel, run.job_id)
        assert job is not None and "secret-for-one-run" not in str(job.__dict__)


def test_rag_profile_is_forwarded_to_the_shared_rag_service_and_absent_gold_is_null(monkeypatch) -> None:
    bank = _eligible_bank()
    _indexed_knowledge_snapshot()
    suite = evaluation_lab_service.create_suite(bank_id=bank.bank_id, sample_size=1, seed=715)
    monkeypatch.setattr(evaluation_lab_service, "_dispatch", lambda _run_id: None)
    profile = {"name": "Dense six", "mode": "dense", "top_k": 6, "candidate_pool": 40, "rerank_enabled": True, "rrf_k": 60, "section_dedupe": False}
    experiment = evaluation_lab_service.create_rag_experiment(suite_id=suite["suite_id"], variants=[profile], model="candidate-model")
    assert experiment["fixed_snapshot"]["answer_model"] == "candidate-model"
    seen: list[RetrievalProfile] = []

    def fake_retrieve(_query: str, **kwargs):
        seen.append(kwargs["profile"])
        assert isinstance(kwargs["version_ids"], list)
        return [Citation(chunk_id="chunk-a", document_name="source", page=1, section="s", snippet="evidence", score=1.0)]

    monkeypatch.setattr("app.services.evaluation_lab_service.rag_service.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.evaluation_lab_service.llm_provider.chat", lambda **_kwargs: LLMResult(True, '{"answer":"A"}', "configured", "runtime", "candidate-model", latency_ms=11, usage={"total_tokens": 6}))
    for run in experiment["runs"]:
        evaluation_lab_service.process_run(run["run_id"])
    result = evaluation_lab_service.experiment(experiment["experiment_id"])
    assert any(item.mode == "dense" and item.top_k == 6 and item.candidate_pool == 40 and not item.section_dedupe for item in seen)
    assert all(run["aggregate"]["recall_at_k"] is None for run in result["runs"])


def test_rag_variant_cap_and_default_profile_contract() -> None:
    assert RetrievalProfile.from_value({"mode": "hybrid", "top_k": 4}, fallback_mode="hybrid", fallback_limit=5).public()["top_k"] == 4


def test_rag_profiles_are_persisted_per_bank_and_capped_at_two() -> None:
    bank = _eligible_bank()
    first = evaluation_lab_service.save_rag_profile(
        bank_id=bank.bank_id,
        profile={"name": "低候选池", "mode": "dense", "top_k": 4, "candidate_pool": 12, "rerank_enabled": True, "rrf_k": 60, "section_dedupe": False},
    )
    second = evaluation_lab_service.save_rag_profile(
        bank_id=bank.bank_id,
        profile={"name": "稀疏方案", "mode": "sparse", "top_k": 3, "candidate_pool": 10, "rerank_enabled": False, "rrf_k": 60, "section_dedupe": True},
    )
    try:
        rows = evaluation_lab_service.list_rag_profiles(bank_id=bank.bank_id)
        assert [item["profile_id"] for item in rows] == [first["profile_id"], second["profile_id"]]
        updated = evaluation_lab_service.save_rag_profile(
            bank_id=bank.bank_id,
            profile={**first, "name": "更新后的方案", "top_k": 6},
            profile_id=first["profile_id"],
        )
        assert updated["profile_id"] == first["profile_id"]
        assert updated["name"] == "更新后的方案"
        assert updated["top_k"] == 6
        with pytest.raises(ValueError, match="最多保存两个"):
            evaluation_lab_service.save_rag_profile(
                bank_id=bank.bank_id,
                profile={"name": "第三个方案", "mode": "hybrid", "top_k": 5, "candidate_pool": 20, "rerank_enabled": False, "rrf_k": 60, "section_dedupe": True},
            )
        with pytest.raises(KeyError):
            evaluation_lab_service.save_rag_profile(
                bank_id="another-bank",
                profile={**first},
                profile_id=first["profile_id"],
            )
        evaluation_lab_service.delete_rag_profile(bank_id=bank.bank_id, profile_id=first["profile_id"])
        assert [item["profile_id"] for item in evaluation_lab_service.list_rag_profiles(bank_id=bank.bank_id)] == [second["profile_id"]]
    finally:
        with SessionLocal() as session:
            session.query(EvalRagProfileModel).filter(EvalRagProfileModel.profile_id.in_([first["profile_id"], second["profile_id"]])).delete(synchronize_session=False)
            session.commit()


def test_rag_run_rejects_embedding_or_index_drift_after_snapshot(monkeypatch) -> None:
    monkeypatch.setattr("app.services.evaluation_lab_service.rag_service.index_state", lambda: {"provider": "other", "model": "other", "index_version": 9})
    with pytest.raises(RuntimeError, match="RAG index changed"):
        evaluation_lab_service._assert_rag_snapshot_is_current({"embedding_provider": "configured", "embedding_model": "configured", "index_version": 1})


def test_latest_and_delete_results_are_isolated_by_bank_and_lab_type(monkeypatch) -> None:
    # Use a unique throwaway bank so a regression test never deletes a
    # developer's or learner's existing experiment history.
    bank_id = f"test-eval-isolation-{uuid4().hex[:10]}"
    question_id = f"test-eval-question-{uuid4().hex[:10]}"
    with SessionLocal() as session:
        bank = QuestionBankModel(
            bank_id=bank_id, domain_id="general_science", name="Evaluation isolation test",
            description="test", version="test-v1", status="published", question_count=1,
            question_type_counts={"single_choice": 1}, modality_counts={"text": 1}, body_parts=[],
        )
        session.add(bank)
        session.add(QuestionModel(
            question_id=question_id, bank_id=bank_id, domain_id="general_science", question_type="single_choice",
            modality="text", title="Test question", stem="Choose A", case_summary="Test", difficulty="easy",
            body_part="general", source_type="seed", source_dataset="test", citation_note="test",
            options=[{"id": "opt_a", "text": "A"}, {"id": "opt_b", "text": "B"}],
            grading_payload={"correct_option_id": "opt_a"}, explanation="Test", teaching_tags=[], expected_keywords=[],
            doctor_review_required=False, safety_notice="test", business_usage="user_ready",
        ))
        session.commit()

    try:
        suite = evaluation_lab_service.create_suite(bank_id=bank_id, sample_size=1, seed=717)
        monkeypatch.setattr(evaluation_lab_service, "_dispatch", lambda _run_id: None)
        model_experiment = evaluation_lab_service.create_model_experiment(suite_id=suite["suite_id"], models=["model-for-delete"])
        rag_experiment = evaluation_lab_service.create_rag_experiment(suite_id=suite["suite_id"], variants=[], model="rag-for-keep")

        latest_model = evaluation_lab_service.latest_experiment(bank_id=bank_id, experiment_type="model")
        latest_rag = evaluation_lab_service.latest_experiment(bank_id=bank_id, experiment_type="rag")
        assert latest_model and latest_model["experiment_id"] == model_experiment["experiment_id"]
        assert latest_rag and latest_rag["experiment_id"] == rag_experiment["experiment_id"]

        deleted = evaluation_lab_service.delete_experiments(bank_id=bank_id, experiment_type="model")
        assert deleted == {"deleted_experiment_count": 1, "deleted_run_count": 1}
        assert evaluation_lab_service.latest_experiment(bank_id=bank_id, experiment_type="model") is None
        kept_rag = evaluation_lab_service.latest_experiment(bank_id=bank_id, experiment_type="rag")
        assert kept_rag and kept_rag["experiment_id"] == rag_experiment["experiment_id"]

        with SessionLocal() as session:
            assert session.get(EvalSuiteModel, suite["suite_id"]) is not None
            assert session.get(EvalExperimentModel, model_experiment["experiment_id"]) is None
            assert session.get(EvalLabRunModel, model_experiment["runs"][0]["run_id"]) is None
            assert session.scalar(select(EvalLabCaseModel).where(EvalLabCaseModel.run_id == model_experiment["runs"][0]["run_id"])) is None
    finally:
        evaluation_lab_service.delete_experiments(bank_id=bank_id, experiment_type="rag")
        with SessionLocal() as session:
            session.execute(delete(EvalSuiteModel).where(EvalSuiteModel.bank_id == bank_id))
            session.execute(delete(QuestionModel).where(QuestionModel.question_id == question_id))
            session.execute(delete(QuestionBankModel).where(QuestionBankModel.bank_id == bank_id))
            session.commit()


def test_model_discovery_uses_normalized_endpoints_and_deduplicates_without_exposing_key(monkeypatch) -> None:
    monkeypatch.setattr("app.services.model_discovery_service.llm_provider._validate_base_url", lambda _parsed: None)
    assert model_discovery_service.build_models_url_candidates("https://provider.example/v1/?keep=no#fragment") == [
        "https://provider.example/v1/models",
    ]
    assert model_discovery_service.build_models_url_candidates("https://provider.example") == [
        "https://provider.example/v1/models", "https://provider.example/models",
    ]
    calls: list[tuple[str, str]] = []

    def fake_get(endpoint: str, api_key: str) -> tuple[int, bytes]:
        calls.append((endpoint, api_key))
        return 200, b'{"data":[{"id":" Qwen-3 "},{"id":"qwen-3"},{"id":"deepseek"},{"id":""},{"id":8}]}'

    monkeypatch.setattr(model_discovery_service, "_get", fake_get)
    result = model_discovery_service.discover(base_url="https://provider.example/v1", api_key="test-secret")
    assert calls == [("https://provider.example/v1/models", "test-secret")]
    assert [item["id"] for item in result["models"]] == ["deepseek", "Qwen-3"]
    assert "test-secret" not in str(result)

    monkeypatch.setattr(model_discovery_service, "_get", lambda _endpoint, _key: (200, b'{"data":[{"id":" "}]}'))
    with pytest.raises(ValueError, match="未返回可用的模型 ID"):
        model_discovery_service.discover(base_url="https://provider.example/v1", api_key="test-secret")


def test_model_discovery_falls_back_on_not_found_and_keeps_auth_error_safe(monkeypatch) -> None:
    monkeypatch.setattr("app.services.model_discovery_service.llm_provider._validate_base_url", lambda _parsed: None)
    calls: list[str] = []

    def fake_get(endpoint: str, _api_key: str) -> tuple[int, bytes]:
        calls.append(endpoint)
        return (404, b"") if len(calls) == 1 else (200, b'{"data":[{"id":"model-b"}]}')

    monkeypatch.setattr(model_discovery_service, "_get", fake_get)
    assert model_discovery_service.discover(base_url="https://provider.example", api_key="test-secret")["models"][0]["id"] == "model-b"
    assert calls == ["https://provider.example/v1/models", "https://provider.example/models"]

    monkeypatch.setattr(model_discovery_service, "_get", lambda _endpoint, _key: (401, b"secret should not surface"))
    with pytest.raises(ValueError, match="API Key 鉴权失败") as error:
        model_discovery_service.discover(base_url="https://provider.example", api_key="test-secret")
    assert "test-secret" not in str(error.value)


def test_model_discovery_api_returns_only_normalized_public_fields(monkeypatch) -> None:
    monkeypatch.setattr("app.services.model_discovery_service.llm_provider._validate_base_url", lambda _parsed: None)
    monkeypatch.setattr(
        model_discovery_service,
        "_get",
        lambda _endpoint, _key: (200, b'{"data":[{"id":"model-a","owned_by":"provider"}]}'),
    )
    response = TestClient(app).post(
        "/api/v3/evaluation/lab/models/discover",
        json={"base_url": "https://provider.example/v1", "api_key": "test-secret"},
    )
    assert response.status_code == 200
    assert response.json()["models"] == [{"id": "model-a", "display_name": None, "owned_by": "provider"}]
    assert "test-secret" not in response.text
