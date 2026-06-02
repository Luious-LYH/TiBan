from app.schemas import LearnerProfile, SubmissionResponse
from app.services.audit_service import now_iso
from app.services.data_store import read_json, write_json


class MemoryService:
    def get_profile(self) -> LearnerProfile:
        return LearnerProfile(**read_json("learner_profile.json"))

    def get_recommendations(self) -> list[dict[str, str]]:
        profile = self.get_profile()
        return [
            {
                "question_class": cls,
                "reason": f"当前薄弱标签包含：{', '.join(profile.weakness_tags[:2])}",
                "priority": "high" if cls == profile.recommended_question_classes[0] else "medium",
            }
            for cls in profile.recommended_question_classes
        ]

    def record_submission(self, submission: SubmissionResponse) -> LearnerProfile:
        profile = self.get_profile()
        total = profile.total_questions + 1
        correct_count = round(profile.accuracy * profile.total_questions) + (1 if submission.is_correct else 0)
        profile.total_questions = total
        profile.accuracy = round(correct_count / total, 2)
        profile.completed_today = min(profile.daily_target, profile.completed_today + 1)
        if not submission.is_correct:
            profile.recent_errors = [submission.question_id, *profile.recent_errors]
            profile.recent_errors = list(dict.fromkeys(profile.recent_errors))[:8]
            profile.wrong_questions = [submission.question_id, *profile.wrong_questions]
            profile.wrong_questions = list(dict.fromkeys(profile.wrong_questions))[:16]
            for tag in submission.error_tags:
                if tag not in profile.weakness_tags:
                    profile.weakness_tags.insert(0, tag)
            for fact in submission.fact_feedback:
                old_score = profile.skill_scores.get(fact.skill_dimension, 70)
                profile.skill_scores[fact.skill_dimension] = max(35, old_score - 3)
        else:
            for fact in submission.fact_feedback:
                old_score = profile.skill_scores.get(fact.skill_dimension, 70)
                profile.skill_scores[fact.skill_dimension] = min(96, old_score + 1)
            profile.wrong_questions = [qid for qid in profile.wrong_questions if qid != submission.question_id]
        profile.training_records.insert(
            0,
            {
                "date": now_iso()[:10],
                "question_id": submission.question_id,
                "score": submission.score,
                "result": "正确" if submission.is_correct else "待复盘",
            },
        )
        profile.training_records = profile.training_records[:12]
        profile.growth_trend = self._append_growth(profile)
        profile.updated_at = now_iso()
        write_json("learner_profile.json", profile.model_dump())
        return profile

    def set_favorite(self, question_id: str, favorited: bool = True) -> LearnerProfile:
        profile = self.get_profile()
        if favorited:
            profile.favorite_questions = [question_id, *profile.favorite_questions]
            profile.favorite_questions = list(dict.fromkeys(profile.favorite_questions))[:32]
        else:
            profile.favorite_questions = [qid for qid in profile.favorite_questions if qid != question_id]
        profile.updated_at = now_iso()
        write_json("learner_profile.json", profile.model_dump())
        return profile

    def training_state(self) -> dict[str, object]:
        profile = self.get_profile()
        return {
            "profile": profile.model_dump(),
            "wrong_questions": profile.wrong_questions,
            "favorite_questions": profile.favorite_questions,
            "review_queue": len(profile.wrong_questions or profile.recent_errors),
            "next_plan": [
                {"label": "证据不足复盘", "count": 4, "reason": "最近错因集中在错误前提和过度诊断"},
                {"label": "公开样例考试块", "count": 3, "reason": "使用 EndoBench/Kvasir 样例检验迁移能力"},
                {"label": "报告修改训练", "count": 2, "reason": "强化所见与诊断边界"},
            ],
        }

    def _append_growth(self, profile: LearnerProfile) -> list[dict[str, int | str]]:
        trend = profile.growth_trend or []
        trend.append(
            {
                "date": now_iso()[:10],
                "accuracy": int(round(profile.accuracy * 100)),
                "evidence": profile.skill_scores.get("证据不足识别", 0),
                "report": profile.skill_scores.get("事实组合", 0),
            }
        )
        return trend[-8:]


memory_service = MemoryService()
