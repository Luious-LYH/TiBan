from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import model_eval_service as service
from app.services.llm_provider import LLMResult


def _pack() -> dict[str, object]:
    return {
        "dataset_id": "cmexam-text-eval-v1",
        "version": "cmexam-text-eval-v1",
        "source_dataset": "CMExam",
        "modality": "text",
        "supports_vision": False,
        "sample_count": 1,
        "dataset_hash": "test-hash",
        "tutor_indexed": False,
        "cases": [
            {
                "case_id": "eval-case-1",
                "source_item_id": "fixture:1",
                "question": "Which option is correct?",
                "options": [{"id": "A", "text": "First"}, {"id": "B", "text": "Second"}],
                "gold_answer": "B",
                "task": "text_single_choice",
                "topic": "fixture",
            },
        ],
    }


def test_evaluation_is_no_fallback_and_artifact_withholds_raw_output(monkeypatch, tmp_path) -> None:
    calls: list[dict[str, object]] = []

    def fake_chat(**kwargs):
        calls.append(kwargs)
        return LLMResult(
            True,
            '{"answer":"B"}',
            "provider",
            "byok_openai_compatible",
            "candidate-model",
            latency_ms=12,
            usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        )

    monkeypatch.setattr(service, "_load_pack", lambda _dataset_id: _pack())
    monkeypatch.setattr(service, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(service.llm_provider, "chat", fake_chat)

    result = service.run_evaluation(
        dataset_id="cmexam-text-eval-v1",
        base_url="http://provider.test/v1",
        api_key="secret-for-test-only",
        model="candidate-model",
        sample_count=1,
    )

    assert calls and calls[0]["allow_fallback"] is False
    assert result["fallback"] is False
    assert result["aggregate"]["accuracy"] == 1.0
    artifact_path = next(tmp_path.glob("evalrun_*.json"))
    artifact_text = artifact_path.read_text(encoding="utf-8")
    assert "secret-for-test-only" not in artifact_text
    assert "raw reasoning" not in artifact_text
    assert "E:\\" not in artifact_text

    run_id = str(result["eval_run_id"])
    hidden = service.get_run(run_id)
    assert hidden["gold_revealed"] is False
    assert hidden["cases"][0]["gold_answer"] is None
    assert hidden["cases"][0]["correct"] is None
    revealed = service.get_run(run_id, reveal_gold=True)
    assert revealed["cases"][0]["gold_answer"] == "B"
    assert revealed["cases"][0]["correct"] is True


def test_provider_failure_is_recorded_without_fallback_or_secret(monkeypatch, tmp_path) -> None:
    def fake_chat(**kwargs):
        assert kwargs["allow_fallback"] is False
        return LLMResult(
            False,
            "",
            "provider",
            "byok_openai_compatible",
            "candidate-model",
            "http_502: upstream rejected secret-for-test-only",
        )

    monkeypatch.setattr(service, "_load_pack", lambda _dataset_id: _pack())
    monkeypatch.setattr(service, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(service.llm_provider, "chat", fake_chat)

    result = service.run_evaluation(
        dataset_id="cmexam-text-eval-v1",
        base_url="http://provider.test/v1",
        api_key="secret-for-test-only",
        model="candidate-model",
        sample_count=1,
    )

    assert result["fallback"] is False
    assert result["status"] == "completed_with_failures"
    assert result["errors"][0]["category"] == "provider_error"
    assert "secret-for-test-only" not in json.dumps(result, ensure_ascii=False)


def test_legacy_portfolio_packs_are_not_exposed_by_evaluation_lab(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.evaluation.evaluation_lab_service.catalog",
        lambda: {"banks": [], "runtime_models": ["runtime-model"], "default_profile": {"name": "TiBan Default", "mode": "hybrid", "top_k": 5, "candidate_pool": 20, "rerank_enabled": False, "rrf_k": 60, "section_dedupe": True}, "prompt_version": "evaluation-lab-typed-answer-v1"},
    )
    response = TestClient(app).get("/api/v3/evaluation/lab/catalog")
    assert response.status_code == 200
    payload = response.json()
    assert payload["banks"] == []
    assert "EndoBench" not in str(payload)
