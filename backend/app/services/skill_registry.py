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
            skill_log = audit_service.log(
                "skill_run",
                request.learner_id,
                str(payload.get("summary", "手动记录 skill 调用。")),
                skill.risk_level,
                skill.id,
            )
            result = {"log_id": skill_log.id, "safety_notice": SAFETY_NOTICE}
        else:
            raise ValueError("Unknown skill")
        if skill.id != "audit_log":
            skill_log = audit_service.log(
                "skill_run",
                request.learner_id,
                f"运行 skill：{skill.name}",
                skill.risk_level,
                skill.id,
                doctor_review_required=skill.risk_level != "low",
            )
        result.setdefault("doctor_review_required", skill.risk_level != "low")
        result.setdefault("safety_notice", SAFETY_NOTICE)
        result["skill_run_receipt"] = {
            "audit_log_id": skill_log.id,
            "skill_id": skill.id,
            "skill_name": skill.name,
            "risk_level": skill.risk_level,
            "learner_id": request.learner_id,
            "input_trace": self._input_trace(payload),
            "source_trace": self._source_trace(skill.id, result),
            "next_actions": self._next_actions(skill.category),
            "doctor_review_required": result["doctor_review_required"],
            "created_at": skill_log.created_at,
        }
        return result

    def _get_skill(self, skill_id: str) -> SkillDefinition:
        for skill in self.list_skills():
            if skill.id == skill_id:
                return skill
        raise KeyError(f"Skill not found: {skill_id}")

    def _input_trace(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        trace: list[dict[str, Any]] = []
        if payload.get("question_id"):
            trace.append({
                "source_type": "question_context",
                "label": "训练题上下文",
                "used": True,
                "detail": str(payload.get("question_id")),
            })
        if payload.get("selected_answer"):
            trace.append({
                "source_type": "doctor_answer",
                "label": "医师作答",
                "used": True,
                "detail": "已接收作答内容；仅记录来源类型。",
            })
        if payload.get("finding_text"):
            trace.append({
                "source_type": "report_text",
                "label": "报告所见文本",
                "used": True,
                "detail": "已接收报告训练文本；收据不保存全文。",
            })
        if payload.get("diagnosis_summary"):
            trace.append({
                "source_type": "card_summary",
                "label": "卡片摘要",
                "used": True,
                "detail": "已接收患者沟通摘要；收据不保存全文。",
            })
        if payload.get("text"):
            trace.append({
                "source_type": "safety_text",
                "label": "安全审查文本",
                "used": True,
                "detail": "已接收安全审查文本；收据不保存全文。",
            })
        if payload.get("summary") or payload.get("event_type"):
            trace.append({
                "source_type": "audit_summary",
                "label": "审计摘要输入",
                "used": True,
                "detail": "已接收审计摘要或事件类型；收据不保存自由文本全文。",
            })
        if payload.get("learner_id"):
            trace.append({
                "source_type": "learner_context",
                "label": "医师画像上下文",
                "used": True,
                "detail": str(payload.get("learner_id")),
            })
        if not trace:
            trace.append({
                "source_type": "platform_context",
                "label": "平台默认上下文",
                "used": True,
                "detail": "使用当前 demo learner 与默认样例上下文。",
            })
        return trace

    def _source_trace(self, skill_id: str, result: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(result.get("card"), dict):
            card = result["card"]
            return list(card.get("source_trace") or [])
        if isinstance(result.get("draft"), dict):
            draft = result["draft"]
            return list(draft.get("source_trace") or [])
        if result.get("atomic_feedback") or result.get("atomic_trace"):
            return [{
                "source_type": "atomic_facts",
                "label": "原子事实链",
                "used": True,
                "detail": "来自题库 atomic_trace 与评分服务。",
            }]
        if result.get("recommendations"):
            return [{
                "source_type": "learner_memory",
                "label": "医师画像记忆",
                "used": True,
                "detail": "来自 demo learner 训练记录和薄弱标签。",
            }]
        if result.get("hint") or result.get("explanation"):
            return [{
                "source_type": "tutor_service",
                "label": "Tutor 编排服务",
                "used": True,
                "detail": "来自当前题、原子事实和安全边界。",
            }]
        if result.get("log_id"):
            return [{
                "source_type": "audit",
                "label": "手动审计记录",
                "used": True,
                "detail": str(result.get("log_id")),
            }]
        return [{
            "source_type": "skill_registry",
            "label": "受控技能注册表",
            "used": True,
            "detail": f"{skill_id} 已由后端 skill_registry 执行。",
        }]

    def _next_actions(self, category: str) -> list[dict[str, str]]:
        action_map: dict[str, list[dict[str, str]]] = {
            "training": [{"label": "继续题库训练", "href": "/training"}],
            "feedback": [{"label": "查看错因复盘", "href": "/feedback"}],
            "report": [{"label": "进入报告训练", "href": "/report"}],
            "card": [{"label": "进入科普卡片审核", "href": "/card"}],
            "safety": [{"label": "进入错误前提训练", "href": "/false-premise"}],
            "audit": [{"label": "查看审计日志", "href": "/audit"}],
        }
        return action_map.get(category, [{"label": "返回训练中心", "href": "/training"}])


skill_registry = SkillRegistry()
