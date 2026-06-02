from fastapi import APIRouter, HTTPException, Query

from app.core.config import APP_NAME, SAFETY_NOTICE
from app.schemas import (
    ModelSelectRequest,
    PatientCardRequest,
    ReportDraftRequest,
    SkillRunRequest,
    SubmissionRequest,
    TutorChatRequest,
    TutorExplainRequest,
    TutorHintRequest,
)
from app.services.audit_service import audit_service
from app.services.dashboard_service import dashboard_service
from app.services.grading_service import grading_service
from app.services.memory_service import memory_service
from app.services.model_service import model_service
from app.services.question_service import question_service
from app.services.report_service import report_service
from app.services.skill_registry import skill_registry
from app.services.tutor_orchestrator import tutor_orchestrator

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": APP_NAME}


@router.get("/dashboard")
def dashboard() -> dict[str, object]:
    return dashboard_service.get_dashboard()


@router.get("/questions")
def list_questions(
    question_class: str | None = None,
    difficulty: str | None = None,
    false_premise: bool | None = Query(default=None),
) -> dict[str, object]:
    items = question_service.list_questions(question_class, difficulty, false_premise)
    return {"items": [item.model_dump() for item in items], "total": len(items)}


@router.get("/questions/{question_id}")
def get_question(question_id: str, learner_id: str = "demo_learner") -> dict[str, object]:
    try:
        question = question_service.get_question(question_id, learner_id)
        return {"item": question.model_dump()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/submit")
def submit_answer(request: SubmissionRequest) -> dict[str, object]:
    try:
        return grading_service.grade(request).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tutor/hint")
def tutor_hint(request: TutorHintRequest) -> dict[str, object]:
    try:
        return tutor_orchestrator.hint(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tutor/explain")
def tutor_explain(request: TutorExplainRequest) -> dict[str, object]:
    try:
        return tutor_orchestrator.explain(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tutor/chat")
def tutor_chat(request: TutorChatRequest) -> dict[str, object]:
    try:
        return tutor_orchestrator.chat(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/learner/profile")
def learner_profile() -> dict[str, object]:
    return memory_service.get_profile().model_dump()


@router.get("/learner/recommendations")
def learner_recommendations() -> dict[str, object]:
    return {"items": memory_service.get_recommendations(), "safety_notice": SAFETY_NOTICE}


@router.post("/report-draft")
def report_draft(request: ReportDraftRequest) -> dict[str, object]:
    return report_service.generate_report_draft(request).model_dump()


@router.post("/patient-card")
def patient_card(request: PatientCardRequest) -> dict[str, object]:
    return report_service.generate_patient_card(request).model_dump()


@router.get("/models")
def list_models() -> dict[str, object]:
    return {
        "items": [model.model_dump() for model in model_service.list_models()],
        "notice": "模型能力分为 mock/预留，不代表真实临床评测。",
        "safety_notice": SAFETY_NOTICE,
    }


@router.post("/models/select")
def select_model(request: ModelSelectRequest) -> dict[str, object]:
    try:
        return model_service.select_model(request.model_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/skills")
def list_skills() -> dict[str, object]:
    skills = skill_registry.list_skills()
    return {"items": [skill.model_dump() for skill in skills], "total": len(skills)}


@router.post("/skills/run")
def run_skill(request: SkillRunRequest) -> dict[str, object]:
    try:
        return skill_registry.run(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit")
def list_audit() -> dict[str, object]:
    logs = audit_service.list_logs()
    return {"items": [log.model_dump() for log in logs], "total": len(logs)}

