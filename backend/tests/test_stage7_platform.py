"""Stage 7 platform regression: two packs, one core, measurable boundaries."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import (
    DocumentVersionModel,
    KnowledgeChunkModel,
    LearnerMasteryModel,
    LearningMemoryItemModel,
    QuestionModel,
    ReviewCardModel,
    SourceDocumentModel,
)
from app.main import app
from app.services.agent_runtime import AgentContext, tutor_runner
from app.services.general_science_import_service import ARC_EASY_BANK_ID, import_arc_easy
from app.services.learning_memory_service import learning_memory_service
from app.services.model_eval_service import GENERAL_DATASET_ID, list_datasets
from app.services.platform_evaluation import (
    audit_domain_core_reuse,
    evaluate_tool_selection,
    measure_personalization_uplift,
)
from app.services.rag_service import rag_service


GENERAL_BANK_ID = "bank-general-science-foundations"
GENERAL_QUESTION_ID = "general_science_fixture_001"
MEDICAL_QUESTION_ID = "endo_text_esophagus_reflux_single"


def _wrong_option(question_id: str) -> str:
    with SessionLocal() as session:
        question = session.get(QuestionModel, question_id)
        assert question is not None
        answer = str(question.grading_payload["correct_option_id"])
        return next(str(item["id"]) for item in question.options if str(item["id"]) != answer)


def test_domain_manifest_and_catalog_filtering_are_public_and_v31_scoped() -> None:
    client = TestClient(app)
    domains = client.get("/api/v3/domains")
    assert domains.status_code == 200
    assert {item["domain_id"] for item in domains.json()["items"]} == {"endoscopy", "general_science"}

    general = client.get("/api/v3/question-banks", params={"domain_id": "general_science"})
    assert general.status_code == 200
    # General Science remains an internal compatibility/evaluation domain, but
    # V3.1 intentionally removes fixture packs from the learner catalog.
    assert general.json()["items"] == []

    medical = client.get("/api/v3/question-banks", params={"domain_id": "endoscopy"})
    assert medical.status_code == 200
    assert {item["bank_id"] for item in medical.json()["items"]} == {"bank-cmexam-real"}


def test_hidden_general_fixture_cannot_start_a_learner_session() -> None:
    client = TestClient(app)
    learner_id = f"stage7-general-{uuid4().hex[:8]}"
    study = client.post("/api/v3/practice/sessions", json={
        "learner_id": learner_id, "bank_id": GENERAL_BANK_ID, "mode": "study", "question_count": 2, "shuffle_seed": 7,
    })
    assert study.status_code == 404, study.text


def test_cross_domain_mastery_and_memory_are_isolated_even_for_same_label() -> None:
    learner_id = f"stage7-isolation-{uuid4().hex[:8]}"
    point = "同名知识点"
    with SessionLocal() as session:
        session.add_all([
            LearnerMasteryModel(mastery_id=f"mastery_{uuid4().hex[:12]}", learner_id=learner_id, domain_id="endoscopy", knowledge_point=point),
            LearnerMasteryModel(mastery_id=f"mastery_{uuid4().hex[:12]}", learner_id=learner_id, domain_id="general_science", knowledge_point=point),
        ])
        session.commit()
        rows = list(session.scalars(select(LearnerMasteryModel).where(
            LearnerMasteryModel.learner_id == learner_id,
            LearnerMasteryModel.knowledge_point == point,
        )))
        assert {row.domain_id for row in rows} == {"endoscopy", "general_science"}

        session.add_all([
            LearningMemoryItemModel(
                memory_id=f"memory_{uuid4().hex[:12]}", learner_id=learner_id, domain_id="endoscopy", kind="repeated_mistake",
                topic_keys=["力与运动"], concept_keys=[], summary="医疗域同名标签，不得注入通用科学。", status="active", confidence=0.8,
                evidence_refs=[{"attempt_id": "medical-evidence"}], source_type="graded_attempt", dedupe_key=f"medical-{uuid4().hex}",
            ),
            LearningMemoryItemModel(
                memory_id=f"memory_{uuid4().hex[:12]}", learner_id=learner_id, domain_id="general_science", kind="repeated_mistake",
                topic_keys=["力与运动"], concept_keys=[], summary="通用科学当前主题的学习事实。", status="active", confidence=0.8,
                evidence_refs=[{"attempt_id": "general-evidence"}], source_type="graded_attempt", dedupe_key=f"general-{uuid4().hex}",
            ),
        ])
        session.commit()
        memory = learning_memory_service.retrieve_relevant(
            session, learner_id=learner_id, question_id=GENERAL_QUESTION_ID, user_message="解释力与运动",
        )
    assert len(memory["items"]) == 1
    assert memory["items"][0]["domain_id"] == "general_science"
    assert "医疗域" not in memory["items"][0]["summary"]


def test_cross_domain_rag_retrieval_isolated() -> None:
    suffix = uuid4().hex[:10]
    marker = f"stage7marker{suffix}"
    second_marker = f"stage7anchor{uuid4().hex[:10]}"
    medical_document = f"stage7-medical-{suffix}"
    general_document = f"stage7-general-{suffix}"
    with SessionLocal() as session:
        for document_id, domain_id, namespace, content in (
            (medical_document, "endoscopy", "medical_general", f"医学专用术语，仅属于医疗资料。{marker}medical {second_marker}medical"),
            (general_document, "general_science", "general_science", f"能量转化需要依据题干给出的条件判断。{marker}general {second_marker}general"),
        ):
            version_id = f"version-{document_id}"
            session.add(SourceDocumentModel(
                document_id=document_id, domain_id=domain_id, bank_id=None, name=f"{domain_id} source", media_type="text/markdown",
                content_hash=suffix, status="indexed", business_usage="knowledge_base", license_gate_status="allow",
                ai_ingestion_allowed=True, namespace=namespace,
            ))
            session.add(DocumentVersionModel(
                version_id=version_id, document_id=document_id, version_label="stage7-test", source_path="stage7-test",
                content_hash=suffix, parser="test", status="indexed",
            ))
            session.add(KnowledgeChunkModel(
                chunk_id=f"chunk-{document_id}", document_id=document_id, version_id=version_id, parent_section="test", page=1,
                ordinal=0, content=content, content_hash=suffix, token_count=len(content), namespace=namespace,
            ))
        session.commit()
    citations = rag_service.retrieve(
        f"{marker}general {second_marker}general", mode="sparse", limit=5, domain_id="general_science", namespaces=["general_science"],
    )
    assert citations
    assert {citation.namespace for citation in citations} == {"general_science"}
    assert {citation.document_id for citation in citations} == {general_document}


def test_arc_easy_local_import_keeps_source_out_of_ai_ingestion(tmp_path: Path) -> None:
    fixture = tmp_path / "arc_easy_train.parquet"
    table = pa.Table.from_pylist([{
        "id": f"stage7-{uuid4().hex[:8]}",
        "question": {"stem": "Which option is a scientific observation?", "choices": {"label": ["A", "B"], "text": ["Measured value", "Untested guess"]}},
        "answerKey": "A",
    }])
    pq.write_table(table, fixture)
    result = import_arc_easy(limit=1, path=fixture)
    assert result["bank_id"] == ARC_EASY_BANK_ID
    with SessionLocal() as session:
        source = session.get(SourceDocumentModel, "source-qbank-arc-easy-v1")
        assert source is not None and source.domain_id == "general_science"
        assert source.ai_ingestion_allowed is False


def test_general_evaluation_pack_is_available_without_medical_pack_dependency() -> None:
    datasets = list_datasets()
    general = next(item for item in datasets if item["dataset_id"] == GENERAL_DATASET_ID)
    assert general["domain_id"] == "general_science"
    assert general["tutor_indexed"] is False


def test_advanced_evaluation_and_architecture_guard_are_reproducible() -> None:
    tool_result = evaluate_tool_selection()
    assert tool_result["metrics"] == {
        "tool_selection_accuracy": 1.0,
        "unnecessary_tool_rate": 0.0,
        "missing_tool_rate": 0.0,
    }
    assert all(case["passed"] for case in tool_result["cases"])
    reuse = audit_domain_core_reuse()
    assert reuse["result"] == "pass" and reuse["duplicated_core_engines"] == []


def test_personalization_uplift_is_defined_as_scheduling_behavior() -> None:
    result = measure_personalization_uplift(
        evidence_topic="力与运动",
        baseline_topics=["物态变化", "力与运动", "电路", "地球运动"],
        evidence_aware_topics=["力与运动", "力与运动", "电路", "力与运动"],
    )
    assert result["uplift"] == 0.5
    assert "not a learning-score" in result["not_a_claim"]
