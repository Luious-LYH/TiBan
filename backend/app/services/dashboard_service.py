from app.core.config import SAFETY_NOTICE
from app.services.memory_service import memory_service
from app.services.model_service import model_service
from app.services.question_service import question_service


class DashboardService:
    def get_dashboard(self) -> dict[str, object]:
        profile = memory_service.get_profile()
        active_model = model_service.active_model()
        questions = question_service.list_questions()
        return {
            "today_training": {
                "completed": 6,
                "target": 12,
                "streak_days": 5,
                "review_queue": len(profile.recent_errors),
            },
            "learner_profile": profile.model_dump(),
            "ability_radar": [{"dimension": k, "score": v} for k, v in profile.skill_scores.items()],
            "recommended_training": [
                {"label": cls, "count": len([q for q in questions if q.question_class == cls])}
                for cls in profile.recommended_question_classes
            ],
            "active_model": active_model.model_dump(),
            "safety_notice": SAFETY_NOTICE,
            "mock_evaluation_notice": "模型能力分为演示 mock 和接口预留，不代表真实临床评测结果。",
            "reference_inspirations": [
                "HyperKvasir: GI 内镜图像/视频数据底座",
                "Kvasir-VQA-x1: GI-VQA 课程分层与复杂问答参考",
                "MediaEval Medico: VQA + 多模态解释能力参考",
            ],
        }


dashboard_service = DashboardService()

