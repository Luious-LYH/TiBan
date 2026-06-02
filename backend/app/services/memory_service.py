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
        if not submission.is_correct:
            profile.recent_errors = [submission.question_id, *profile.recent_errors]
            profile.recent_errors = list(dict.fromkeys(profile.recent_errors))[:8]
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
        profile.updated_at = now_iso()
        write_json("learner_profile.json", profile.model_dump())
        return profile


memory_service = MemoryService()

