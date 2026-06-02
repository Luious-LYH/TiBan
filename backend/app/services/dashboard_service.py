from app.core.config import SAFETY_NOTICE
from app.services.memory_service import memory_service
from app.services.model_service import model_service
from app.services.question_service import question_service


class DashboardService:
    def get_dashboard(self) -> dict[str, object]:
        profile = memory_service.get_profile()
        active_model = model_service.active_model()
        admission_state = model_service.admission_state()
        questions = question_service.list_questions()
        wrong_set = set(profile.wrong_questions or profile.recent_errors)
        favorite_set = set(profile.favorite_questions)
        continue_question = next((q for q in questions if q.id in wrong_set), questions[0])
        return {
            "today_training": {
                "completed": profile.completed_today,
                "target": profile.daily_target,
                "streak_days": profile.streak_days,
                "review_queue": len(wrong_set),
            },
            "learner_profile": profile.model_dump(),
            "ability_radar": [{"dimension": k, "score": v} for k, v in profile.skill_scores.items()],
            "recommended_training": [
                {"label": cls, "count": len([q for q in questions if q.question_class == cls])}
                for cls in profile.recommended_question_classes
            ],
            "today_plan": [
                {
                    "label": "错题复盘",
                    "target": min(4, len(wrong_set) or 4),
                    "status": "优先",
                    "href": "/training?view=wrong",
                },
                {"label": "公开样例考试块", "target": 3, "status": "计时", "href": "/training?mode=exam"},
                {"label": "报告修改训练", "target": 2, "status": "AI judge", "href": "/report"},
            ],
            "continue_training": {
                "question_id": continue_question.id,
                "title": continue_question.title,
                "source_dataset": continue_question.source_dataset,
                "reason": "根据最近错因优先复盘证据不足与错误前提。",
            },
            "favorite_count": len(favorite_set),
            "wrong_count": len(wrong_set),
            "recent_tutor_summary": [
                "Agent 提醒：先描述可观察事实，再判断题干前提是否成立。",
                "报告训练建议：避免把单帧图像所见写成最终诊断。",
                "下一题推荐：公开复杂问答样例，训练多事实组合表达。",
            ],
            "growth_trend": profile.growth_trend,
            "active_model": active_model.model_dump(),
            "model_admission_state": admission_state,
            "safety_notice": SAFETY_NOTICE,
            "mock_evaluation_notice": "模型能力分为演示 mock 和接口预留，不代表真实临床评测结果。",
            "reference_inspirations": [
                "AMBOSS: Study/Exam Mode 与 session analysis 的题库训练组织",
                "UWorld: Tutor/Timed 模式与错题解释卡片",
                "Lecturio: Qbank、AI Tutor 与持续表现追踪",
                "Kvasir/EndoBench: 公开内镜样例用于教学原型素材",
            ],
        }


dashboard_service = DashboardService()
