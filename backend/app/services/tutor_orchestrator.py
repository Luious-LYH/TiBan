from app.core.config import SAFETY_NOTICE
from app.schemas import SubmissionRequest, TutorChatRequest, TutorExplainRequest, TutorHintRequest
from app.services.audit_service import audit_service
from app.services.grading_service import grading_service
from app.services.question_service import question_service
from app.services.safety_service import safety_service


class TutorOrchestrator:
    def hint(self, request: TutorHintRequest) -> dict[str, object]:
        question = question_service.get_question(request.question_id, request.learner_id)
        first_tag = question.teaching_tags[0] if question.teaching_tags else "图像证据"
        hint = (
            f"先不要急着选答案。请围绕“{first_tag}”观察："
            "这个选项是否有图像证据支持？有没有把观察事实过度升级为诊断？"
        )
        if question.false_premise_flag:
            hint = "这题可能有题干前提陷阱：先判断题干假设是否真的被图像支持，再决定是否作答。"
        audit_service.log(
            "tutor_reply",
            user_id=request.learner_id,
            entity_id=question.id,
            summary="智能辅导生成提示，未泄露标准答案。",
        )
        return {
            "hint": hint,
            "follow_up_question": "请指出你选择该答案时依赖的一个图像证据，或说明为什么证据不足。",
            "leak_answer": False,
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
        }

    def explain(self, request: TutorExplainRequest) -> dict[str, object]:
        question = question_service.get_question(request.question_id, request.learner_id)
        selected = request.selected_answer or question.answer
        grade = grading_service.grade(
            SubmissionRequest(question_id=question.id, learner_id=request.learner_id, selected_answer=selected)
        )
        audit_service.log(
            "tutor_reply",
            user_id=request.learner_id,
            entity_id=question.id,
            summary="智能辅导生成答案讲解和 atomic feedback。",
            risk_level="medium",
        )
        return {
            "explanation": grade.explanation,
            "error_tags": grade.error_tags,
            "atomic_feedback": [fact.model_dump() for fact in grade.fact_feedback],
            "next_recommendation": grade.next_recommendation,
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
        }

    def chat(self, request: TutorChatRequest) -> dict[str, object]:
        question = question_service.get_question(request.question_id, request.learner_id)
        review = safety_service.review_text(request.message)
        if not review["passed"]:
            reply = "这个问题可能涉及真实诊疗或敏感信息。我只能围绕当前教学题的图像证据、答案依据和复核点进行解释。"
            risk = "high"
        else:
            reply = (
                f"围绕当前题“{question.title}”，建议你先拆成两步："
                f"1. 找到可观察事实；2. 判断这些事实是否足以支持题干结论。"
                f"本题的关键训练标签是：{', '.join(question.teaching_tags)}。"
            )
            risk = "low"
        audit_service.log("tutor_reply", request.learner_id, reply, risk, question.id)
        return {"reply": reply, "scope": "current_question_only", "doctor_review_required": True, "safety_notice": SAFETY_NOTICE}


tutor_orchestrator = TutorOrchestrator()
