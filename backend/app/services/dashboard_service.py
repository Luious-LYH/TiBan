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
            "recent_tutor_summary": self._recent_tutor_summary(profile, admission_state),
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

    def _recent_tutor_summary(self, profile, admission_state: dict[str, object]) -> list[str]:
        summaries: list[str] = []
        for record in profile.training_records[:4]:
            result = str(record.get("result", ""))
            question_id = str(record.get("question_id", ""))
            score = record.get("score", 0)
            if result == "Agent辅导":
                summaries.append(f"Agent 追问已回灌：{question_id}，本次只记录训练标签和模式。")
            elif result == "报告修改训练":
                summaries.append(f"报告修改训练完成：{question_id}，得分 {score}，已更新报告表达画像。")
            elif result == "待复盘":
                summaries.append(f"错题待复盘：{question_id}，建议先核对证据边界再看标准解释。")
            elif result:
                summaries.append(f"训练记录：{question_id} · {result} · {score} 分。")
        summaries.append(
            "模型准入状态："
            f"{admission_state.get('provider_name', '未命名 Provider')} · "
            f"Grade {admission_state.get('grade', 'NA')} · "
            f"{'provider called' if admission_state.get('provider_called') else 'rule draft'}。"
        )
        summaries.append("下一步推荐：公开复杂问答样例，训练多事实组合表达。")
        return summaries[:5]


dashboard_service = DashboardService()
