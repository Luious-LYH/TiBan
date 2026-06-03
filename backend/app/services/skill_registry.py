from typing import Any

from app.core.config import SAFETY_NOTICE
from app.schemas import (
    PatientCardRequest,
    ReportDraftRequest,
    SkillDefinition,
    SkillRunRequest,
    SubmissionRequest,
    TutorExplainRequest,
    TutorHintRequest,
)
from app.services.audit_service import audit_service
from app.services.data_store import read_json
from app.services.grading_service import grading_service
from app.services.memory_service import memory_service
from app.services.question_service import question_service
from app.services.report_service import report_service
from app.services.safety_service import safety_service
from app.services.tutor_orchestrator import tutor_orchestrator


class SkillRegistry:
    def list_skills(self) -> list[SkillDefinition]:
        return [SkillDefinition(**item) for item in read_json("skills.json")]

    def run(self, request: SkillRunRequest) -> dict[str, Any]:
        skill = self._get_skill(request.skill_id)
        if not skill.enabled:
            raise ValueError("Skill is disabled")
        payload = request.payload
        result: dict[str, Any]
        if skill.id == "question_hint":
            result = tutor_orchestrator.hint(
                TutorHintRequest(question_id=str(payload.get("question_id", "q001")), learner_id=request.learner_id)
            )
        elif skill.id == "answer_explain":
            result = tutor_orchestrator.explain(
                TutorExplainRequest(
                    question_id=str(payload.get("question_id", "q001")),
                    learner_id=request.learner_id,
                    selected_answer=payload.get("selected_answer"),
                )
            )
        elif skill.id == "atomic_feedback":
            submission = grading_service.grade(
                SubmissionRequest(
                    question_id=str(payload.get("question_id", "q005")),
                    learner_id=request.learner_id,
                    selected_answer=str(payload.get("selected_answer", "")),
                ),
                record=False,
            )
            result = {
                "atomic_feedback": [fact.model_dump() for fact in submission.fact_feedback],
                "error_tags": submission.error_tags,
                "doctor_review_required": True,
                "safety_notice": SAFETY_NOTICE,
            }
        elif skill.id == "false_premise_guard":
            question = question_service.get_question(str(payload.get("question_id", "q005")), request.learner_id)
            result = {
                "false_premise": question.false_premise_flag,
                "message": "该题包含错误前提或证据不足训练。" if question.false_premise_flag else "该题未标记为错误前提题。",
                "atomic_trace": [fact.model_dump() for fact in question.atomic_trace],
                "doctor_review_required": True,
                "safety_notice": SAFETY_NOTICE,
            }
        elif skill.id == "next_question":
            result = {"recommendations": memory_service.get_recommendations(), "safety_notice": SAFETY_NOTICE}
        elif skill.id == "report_structure":
            draft = report_service.generate_report_draft(
                ReportDraftRequest(
                    finding_text=str(payload.get("finding_text", "胃窦黏膜充血，可见散在糜烂。")),
                    exam_type=str(payload.get("exam_type", "gastroscopy")),
                )
            )
            result = {"draft": draft.model_dump()}
        elif skill.id == "patient_card":
            card = report_service.generate_patient_card(
                PatientCardRequest(
                    diagnosis_summary=str(payload.get("diagnosis_summary", "胃黏膜炎症样改变，等待医生审核。")),
                    audience="patient",
                )
            )
            result = {"card": card.model_dump()}
        elif skill.id == "safety_review":
            result = safety_service.review_text(str(payload.get("text", "")))
        elif skill.id == "audit_log":
            log = audit_service.log(
                "skill_run",
                request.learner_id,
                str(payload.get("summary", "手动记录 skill 调用。")),
                skill.risk_level,
                skill.id,
            )
            result = {"log_id": log.id, "safety_notice": SAFETY_NOTICE}
        else:
            raise ValueError("Unknown skill")
        audit_service.log(
            "skill_run",
            request.learner_id,
            f"运行 skill：{skill.name}",
            skill.risk_level,
            skill.id,
            doctor_review_required=skill.risk_level != "low",
        )
        result.setdefault("doctor_review_required", skill.risk_level != "low")
        result.setdefault("safety_notice", SAFETY_NOTICE)
        return result

    def _get_skill(self, skill_id: str) -> SkillDefinition:
        for skill in self.list_skills():
            if skill.id == skill_id:
                return skill
        raise KeyError(f"Skill not found: {skill_id}")


skill_registry = SkillRegistry()
