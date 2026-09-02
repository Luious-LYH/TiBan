from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from app.application.factory.jobs import JobTransitionError, ensure_transition
from app.application.errors import ProviderRateLimitError, ProviderTimeoutError, normalize_provider_error
from app.application.practice.use_cases import PracticeUseCases
from app.db.database import SessionLocal
from app.db.models import FactoryJobModel
from app.services.agent_runtime import AgentContext, AgentRunner, ModelGateway, ToolRegistry, TutorDependencies, build_tutor_runtime
from app.services.factory_service import _now, enqueue_factory_job, import_allowed_document, recover_stale_factory_jobs


def test_practice_use_case_is_usable_with_a_fake_workflow() -> None:
    class FakeWorkflow:
        def submit(self, request):
            return {"question_id": request.question_id, "atomic": "grade-attempt-mastery-fsrs-memory"}

        def create_session(self, learner_id, bank_id, mode, question_count, shuffle_seed):
            return {"learner_id": learner_id, "bank_id": bank_id, "question_count": question_count}

    result = PracticeUseCases(FakeWorkflow()).submit_answer(type("Request", (), {"question_id": "q"})())
    assert result["atomic"] == "grade-attempt-mastery-fsrs-memory"


def test_tutor_application_runs_with_fake_model_and_retrieval_ports() -> None:
    class FakeGateway:
        name = "fake-llm"

        def select_tools(self, context, available_tools):
            return ["get_question_context", "retrieve_knowledge"]

        def compose(self, context, observations):
            return f"根据 {observations['retrieve_knowledge'][0]['document_name']} 复盘观察依据。"

    dependencies = TutorDependencies(
        question_context=lambda _: {"title": "fake question"},
        retrieve_knowledge=lambda _: [{"document_name": "fake source", "page": "1", "section": "section", "snippet": "evidence", "source_uri": "", "namespace": "test"}],
        learning_profile=lambda _: {"attempt_count": 0},
        learning_memory=lambda _: {"items": []},
        recent_mistakes=lambda _: [],
        grading_result=lambda _: {"score": 0},
        answer_explanation=lambda _: {},
        public_source=lambda _: None,
        record_explicit_confusion=lambda _, __: None,
    )
    events = list(build_tutor_runtime(dependencies, FakeGateway()).stream(AgentContext(question_id="q", learner_id="l", user_message="根据资料给我提示", phase="pre_submit")))
    assert [event.event for event in events][0] == "message_start"
    assert any(event.event == "source" and event.data["document_name"] == "fake source" for event in events)
    assert events[-1].event == "message_end"


def test_factory_job_idempotency_and_stale_recovery_are_durable() -> None:
    uploaded = import_allowed_document("stage6-durable.md", b"# Source\n\nA sufficiently long teaching evidence sentence for a Factory job.", "text/markdown")
    first = enqueue_factory_job(uploaded["document_id"])
    second = enqueue_factory_job(uploaded["document_id"])
    assert first["job_id"] == second["job_id"] and second["reused"] == "true"
    with SessionLocal() as session:
        job = session.get(FactoryJobModel, first["job_id"])
        assert job is not None
        job.status = "running"
        job.stage = "generating"
        job.heartbeat_at = _now() - timedelta(seconds=600)
        session.commit()
    assert first["job_id"] in recover_stale_factory_jobs(stale_after_seconds=60)
    with SessionLocal() as session:
        recovered = session.get(FactoryJobModel, first["job_id"])
        assert recovered is not None
        assert recovered.status == "queued" and recovered.stage == "queued"
        assert recovered.error_code == "worker_stale"


def test_durable_job_rules_reject_terminal_replay() -> None:
    ensure_transition("queued", "running")
    ensure_transition("running", "succeeded")
    with pytest.raises(JobTransitionError):
        ensure_transition("succeeded", "running")


def test_provider_errors_are_normalized_without_vendor_types() -> None:
    assert isinstance(normalize_provider_error("http_429"), ProviderRateLimitError)
    assert isinstance(normalize_provider_error("gateway timeout"), ProviderTimeoutError)


def test_application_modules_do_not_import_framework_or_concrete_adapters() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "application"
    forbidden = ("fastapi", "sqlalchemy", "qdrant", "dramatiq", "app.adapters", "app.routers")
    for source in root.rglob("*.py"):
        content = source.read_text(encoding="utf-8")
        assert not any(f"import {name}" in content or f"from {name}" in content for name in forbidden), source
