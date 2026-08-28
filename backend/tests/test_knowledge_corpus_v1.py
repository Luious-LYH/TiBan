from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.services.data_governance import source_can_enter_tutor


ROOT = Path(__file__).resolve().parents[2]


def test_knowledge_corpus_v1_is_license_gated_and_reproducible() -> None:
    manifest = json.loads((ROOT / "knowledge" / "corpus-v1" / "manifest.json").read_text(encoding="utf-8"))
    registry = yaml.safe_load((ROOT / "knowledge" / "registry" / "sources.yaml").read_text(encoding="utf-8"))
    sources = {item["source_id"]: item for item in registry["sources"]}
    source = sources[manifest["license_gate"]["source_id"]]

    assert manifest["corpus_id"] == "knowledge-corpus-v1"
    assert 30 <= manifest["document_count"] <= 80
    assert source_can_enter_tutor(
        business_usage="knowledge_base",
        license_gate_status=source["status"],
        ai_ingestion_allowed=source["ai_ingestion_allowed"],
    )
    for document in manifest["documents"]:
        assert document["source_id"] == source["source_id"]
        assert document["namespace"] == "endoscopy"
        assert len(document["content_hash"]) == 64
        assert (ROOT / document["path"]).is_file()


def test_retrieval_eval_v2_is_frozen_and_honest_about_human_review() -> None:
    fixture = json.loads((ROOT / "docs" / "fixtures" / "retrieval-eval-v2.json").read_text(encoding="utf-8"))
    test_cases = [item for item in fixture["queries"] if item["split"] == "test"]

    assert 80 <= len(fixture["queries"]) <= 150
    assert len(test_cases) >= 60
    assert fixture["review_policy"]["human_review_required_before_external_effectiveness_claim"] is True
    assert fixture["review_policy"]["status"] == "pending"
    assert all(item["relevant_document_ids"] for item in fixture["queries"])


def test_question_judge_eval_v2_is_candidate_data_not_fake_manual_review() -> None:
    fixture = json.loads((ROOT / "docs" / "fixtures" / "question-judge-eval-v2.json").read_text(encoding="utf-8"))
    assert 60 <= fixture["sample_count"] <= 100
    assert fixture["review_policy"]["human_review_required_before_accuracy_claim"] is True
    assert fixture["review_policy"]["status"] == "pending"
    assert {item["issue"] for item in fixture["cases"]} >= {"safe_pass", "citation_mismatch", "unsupported_claim", "duplicate_distractor"}
