from uuid import uuid4

from app.core.config import SAFETY_NOTICE
from app.schemas import ExamSessionRequest, ExamSessionResponse, LearnerProfile, Question, ReportJudgeResponse, SubmissionResponse
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

    def record_exam_session(self, request: ExamSessionRequest) -> ExamSessionResponse:
        profile = self.get_profile()
        answered_count = len(request.attempts)
        correct_count = sum(1 for attempt in request.attempts if attempt.is_correct)
        average_score = round(sum(attempt.score for attempt in request.attempts) / max(answered_count, 1))
        accuracy = round((correct_count / max(answered_count, 1)) * 100)
        wrong_questions = [attempt.question_id for attempt in request.attempts if not attempt.is_correct]
        elapsed_seconds = max(0, min(request.duration_seconds, request.duration_seconds - request.remaining_seconds))
        session_id = request.session_id or f"exam_{uuid4().hex[:12]}"
        created_at = now_iso()
        response_id = f"exam_session_{uuid4().hex[:12]}"

        profile.question_type_coverage["考试Session"] = profile.question_type_coverage.get("考试Session", 0) + 1
        if wrong_questions and "考试错题复盘" not in profile.weakness_tags:
            profile.weakness_tags.insert(0, "考试错题复盘")
        if wrong_questions:
            profile.recent_errors = list(dict.fromkeys([*wrong_questions, *profile.recent_errors]))[:8]
            profile.wrong_questions = list(dict.fromkeys([*wrong_questions, *profile.wrong_questions]))[:16]

        record = {
            "date": created_at[:10],
            "question_id": session_id,
            "score": average_score,
            "result": f"考试Session {answered_count}题/{accuracy}%",
        }
        profile.training_records = [item for item in profile.training_records if item.get("question_id") != session_id]
        profile.training_records.insert(0, record)
        profile.training_records = profile.training_records[:12]
        profile.exam_sessions = [item for item in profile.exam_sessions if item.get("session_id") != session_id]
        profile.exam_sessions.insert(
            0,
            {
                "id": response_id,
                "session_id": session_id,
                "date": created_at[:10],
                "answered_count": answered_count,
                "correct_count": correct_count,
                "accuracy": accuracy,
                "average_score": average_score,
                "wrong_questions": wrong_questions,
                "elapsed_seconds": elapsed_seconds,
                "finished_reason": request.finished_reason,
                "profile_updated": True,
                "created_at": created_at,
            },
        )
        profile.exam_sessions = profile.exam_sessions[:8]
        profile.growth_trend = self._append_growth(profile)
        profile.updated_at = created_at
        write_json("learner_profile.json", profile.model_dump())

        summary = (
            f"已写入{profile.name}的考试 Session：{answered_count} 题，正确率 {accuracy}%，"
            f"平均分 {average_score}，错题 {len(wrong_questions)} 题；单题提交已分别记录，本汇总不重复增加题量。"
        )
        return ExamSessionResponse(
            id=response_id,
            learner_id=request.learner_id,
            answered_count=answered_count,
            correct_count=correct_count,
            accuracy=accuracy,
            average_score=average_score,
            wrong_questions=wrong_questions,
            elapsed_seconds=elapsed_seconds,
            finished_reason=request.finished_reason,
            profile_updated=True,
            memory_summary=summary,
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=created_at,
        )

    def record_report_judge(self, judge: ReportJudgeResponse) -> str:
        profile = self.get_profile()
        profile.completed_today = min(profile.daily_target, profile.completed_today + 1)
        profile.question_type_coverage["报告修改"] = profile.question_type_coverage.get("报告修改", 0) + 1

        report_delta = 3 if judge.score >= 85 else 1 if judge.score >= 70 else -3
        evidence_delta = 2 if judge.rubric_scores.get("不确定性表达", 0) >= 20 else -3
        safety_delta = 2 if judge.rubric_scores.get("安全边界", 0) >= 20 else -4
        profile.skill_scores["事实组合"] = self._bounded_score(profile.skill_scores.get("事实组合", 70), report_delta)
        profile.skill_scores["证据不足识别"] = self._bounded_score(profile.skill_scores.get("证据不足识别", 70), evidence_delta)
        profile.skill_scores["属性判断"] = self._bounded_score(profile.skill_scores.get("属性判断", 70), safety_delta)

        weakness_map = {
            "所见与诊断区分": "报告安全",
            "不确定性表达": "证据不足",
            "安全边界": "错误前提",
        }
        for rubric, tag in weakness_map.items():
            if judge.rubric_scores.get(rubric, 0) < 20 and tag not in profile.weakness_tags:
                profile.weakness_tags.insert(0, tag)
        if judge.score >= 85:
            profile.weakness_tags = [tag for tag in profile.weakness_tags if tag not in {"报告安全"}]

        if "报告纠错" in profile.recommended_question_classes:
            profile.recommended_question_classes = [
                "报告纠错",
                *[item for item in profile.recommended_question_classes if item != "报告纠错"],
            ]
        else:
            profile.recommended_question_classes.insert(0, "报告纠错")
        profile.recommended_question_classes = profile.recommended_question_classes[:4]

        profile.training_records.insert(
            0,
            {
                "date": now_iso()[:10],
                "question_id": judge.id,
                "score": judge.score,
                "result": "报告修改训练",
            },
        )
        profile.training_records = profile.training_records[:12]
        profile.growth_trend = self._append_growth(profile)
        profile.updated_at = now_iso()
        write_json("learner_profile.json", profile.model_dump())
        return f"已回灌林知远医师画像：报告修改 {judge.score} 分，事实组合/证据边界能力已更新。"

    def record_tutor_interaction(self, question: Question, *, generation_mode: str, safety_passed: bool) -> tuple[list[str], str]:
        profile = self.get_profile()
        interaction_tags = list(dict.fromkeys([
            *question.teaching_tags[:3],
            *(fact.skill_dimension for fact in question.atomic_trace[:2]),
            *([] if safety_passed else ["安全边界"]),
            generation_mode,
        ]))
        profile.question_type_coverage["Agent追问"] = profile.question_type_coverage.get("Agent追问", 0) + 1
        for fact in question.atomic_trace[:2]:
            old_score = profile.skill_scores.get(fact.skill_dimension, 70)
            profile.skill_scores[fact.skill_dimension] = self._bounded_score(old_score, 1 if safety_passed else -2)
        if not safety_passed and "安全边界" not in profile.weakness_tags:
            profile.weakness_tags.insert(0, "安全边界")
        profile.training_records.insert(
            0,
            {
                "date": now_iso()[:10],
                "question_id": question.id,
                "score": 0,
                "result": "Agent辅导",
            },
        )
        profile.training_records = profile.training_records[:12]
        profile.growth_trend = self._append_growth(profile)
        profile.updated_at = now_iso()
        write_json("learner_profile.json", profile.model_dump())
        summary = (
            f"已记录 Agent 辅导事件：{question.title}；"
            f"训练标签 {', '.join(interaction_tags[:3])}；未保存追问原文。"
        )
        return interaction_tags, summary

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
        exam_sessions = profile.exam_sessions or []
        return {
            "profile": profile.model_dump(),
            "wrong_questions": profile.wrong_questions,
            "favorite_questions": profile.favorite_questions,
            "exam_sessions": exam_sessions,
            "latest_exam_session": exam_sessions[0] if exam_sessions else None,
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

    def _bounded_score(self, current: int, delta: int) -> int:
        return min(96, max(35, current + delta))


memory_service = MemoryService()
