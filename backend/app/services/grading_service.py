from uuid import uuid4
import re

from app.core.config import SAFETY_NOTICE
from app.schemas import AtomicFact, Question, SubmissionRequest, SubmissionResponse
from app.services.audit_service import audit_service, now_iso
from app.services.memory_service import memory_service
from app.services.question_service import question_service


class GradingService:
    def grade(self, request: SubmissionRequest, *, record: bool = True) -> SubmissionResponse:
        question = question_service.get_question(request.question_id, request.learner_id)
        selected = request.selected_answer.strip()
        is_correct = self._is_correct_answer(question, selected)
        score = self._score_answer(question, selected, is_correct)
        is_correct = is_correct or (question.question_type == "问答评分" and score >= 80)
        error_tags = self._error_tags(question, selected, is_correct)
        feedback = self._fact_feedback(question, is_correct)
        response = SubmissionResponse(
            id=f"sub_{uuid4().hex[:12]}",
            question_id=question.id,
            learner_id=request.learner_id,
            selected_answer=request.selected_answer,
            is_correct=is_correct,
            score=score,
            error_tags=error_tags,
            fact_feedback=feedback,
            explanation=self._explanation(question, selected, is_correct),
            next_recommendation=self.recommend_next(question, error_tags),
            created_at=now_iso(),
            profile_updated=False,
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
        )
        if record:
            memory_service.record_submission(response)
            response.profile_updated = True
            audit_service.log(
                "answer_submit",
                user_id=request.learner_id,
                entity_id=question.id,
                summary=f"提交答案：{'正确' if is_correct else '需要反馈'}；错因：{','.join(error_tags) or '无'}",
                risk_level="medium" if error_tags else "low",
            )
        return response

    def recommend_next(self, question: Question, error_tags: list[str]) -> str:
        if question.false_premise_flag or "观察依据不足" in error_tags or "证据不足" in error_tags:
            return "建议继续练习观察依据复盘与过度推断识别题。"
        if "过度诊断" in error_tags:
            return "建议进入报告纠错和安全表达训练。"
        if question.question_class in {"基础识别", "部位定位"}:
            return "建议进入病变属性或一图多问题，练习观察依据表达。"
        return "建议选择一题一图多问题，巩固观察事实、解释和限制条件。"

    def _is_safety_aware_wrong(self, selected: str) -> bool:
        keywords = ["证据不足", "复核", "不能确定", "不适用"]
        return any(keyword in selected for keyword in keywords)

    def _is_correct_answer(self, question: Question, selected: str) -> bool:
        if question.question_type == "多选":
            selected_items = self._split_answer_items(selected)
            answer_items = self._split_answer_items(question.answer)
            return bool(selected_items) and selected_items == answer_items
        if question.question_type == "问答评分":
            return self._open_answer_score(question, selected) >= 80
        return selected == question.answer

    def _score_answer(self, question: Question, selected: str, is_correct: bool) -> int:
        if question.question_type == "问答评分":
            return self._open_answer_score(question, selected)
        return 100 if is_correct else 35 if self._is_safety_aware_wrong(selected) else 0

    def _open_answer_score(self, question: Question, selected: str) -> int:
        text = selected.strip()
        if not text:
            return 0
        required = [keyword for keyword in question.expected_keywords if keyword]
        if not required:
            required = [fact.fact for fact in question.atomic_trace]
        matched = [keyword for keyword in required if keyword and keyword in text]
        coverage = len(matched) / max(len(required), 1)
        score = round(coverage * 88)
        if any(token in text for token in ["复核", "结合", "完整检查", "病理"]):
            score += 12
        if any(token in text for token in ["确诊", "治疗方案", "必须手术", "开药"]):
            score -= 35
        return max(0, min(100, score))

    def _split_answer_items(self, value: str) -> set[str]:
        return {
            item.strip()
            for item in re.split(r"[；;]", value or "")
            if item.strip()
        }

    def _error_tags(self, question: Question, selected: str, is_correct: bool) -> list[str]:
        if is_correct:
            return []
        tags: list[str] = []
        if question.false_premise_flag:
            tags.append("过度推断")
        if any(token in selected for token in ["癌", "手术", "开药", "治疗", "严重"]):
            tags.append("过度诊断")
        if not any(token in selected for token in ["证据不足", "复核", "观察", "描述", "不能确定"]):
            tags.append("观察依据不足")
        if not tags:
            tags.append(question.teaching_tags[0])
        return list(dict.fromkeys(tags))

    def _fact_feedback(self, question: Question, is_correct: bool) -> list[AtomicFact]:
        if is_correct:
            return question.atomic_trace
        return [
            fact
            for fact in question.atomic_trace
            if not fact.supported or fact.skill_dimension in {"证据不足识别", "事实组合"}
        ] or question.atomic_trace

    def _explanation(self, question: Question, selected: str, is_correct: bool) -> str:
        if is_correct:
            return f"回答正确。{question.explanation}"
        return (
            f"你的答案是“{selected}”，与参考答案“{question.answer}”不一致。"
            f"{question.explanation} 请优先核对图像证据是否足以支持题干前提。"
        )


grading_service = GradingService()
