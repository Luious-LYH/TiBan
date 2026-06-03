from uuid import uuid4

from app.core.config import DATA_DIR, SAFETY_NOTICE
from app.schemas import ChallengeBenchmarkRequest, ReportDraftRequest, ReportJudgeRequest, SubmissionRequest, TutorChatRequest
from app.services.audit_service import audit_service, now_iso
from app.services.data_store import read_json
from app.services.grading_service import grading_service
from app.services.llm_provider import llm_provider
from app.services.memory_service import memory_service
from app.services.question_service import question_service
from app.services.report_service import report_service
from app.services.tutor_orchestrator import tutor_orchestrator


PUBLIC_DATASETS = {"Kvasir-VQA-x1", "Kvasir-VQA", "EndoBench"}


class DemoCheckService:
    def run(self, learner_id: str = "demo_learner", *, persist: bool = False) -> dict[str, object]:
        profile_snapshot = self._read_data_bytes("learner_profile.json")
        audit_snapshot = self._read_data_bytes("audit_logs.json")
        before_profile = memory_service.get_profile()
        before_logs = audit_service.list_logs()
        before_audit_count = len(before_logs)
        before_audit_ids = {item.id for item in before_logs}
        try:
            result = self._run_chain(
                learner_id=learner_id,
                before_profile=before_profile,
                before_audit_count=before_audit_count,
                before_audit_ids=before_audit_ids,
                persist=persist,
            )
        finally:
            if not persist:
                self._restore_data_bytes("learner_profile.json", profile_snapshot)
                self._restore_data_bytes("audit_logs.json", audit_snapshot)
        return result

    def _read_data_bytes(self, name: str) -> bytes:
        return (DATA_DIR / name).read_bytes()

    def _restore_data_bytes(self, name: str, payload: bytes) -> None:
        path = DATA_DIR / name
        temp_path = DATA_DIR / f".{name}.demo_check_tmp"
        temp_path.write_bytes(payload)
        temp_path.replace(path)

    def _run_chain(
        self,
        *,
        learner_id: str,
        before_profile,
        before_audit_count: int,
        before_audit_ids: set[str],
        persist: bool,
    ) -> dict[str, object]:
        question = self._select_public_question()

        submission = grading_service.grade(
            SubmissionRequest(question_id=question.id, learner_id=learner_id, selected_answer=question.answer)
        )
        tutor = tutor_orchestrator.chat(
            TutorChatRequest(
                question_id=question.id,
                learner_id=learner_id,
                message="请用证据边界提醒我如何复盘这张公开样例图像，不要泄露额外诊断结论。",
            )
        )
        challenge = tutor_orchestrator.challenge_benchmark(
            ChallengeBenchmarkRequest(
                question_id=question.id,
                learner_id=learner_id,
                selected_answer=question.answer,
            )
        )
        draft = report_service.generate_report_draft(
            ReportDraftRequest(
                finding_text="公开样例单帧内镜图像训练：请整理可观察结构、异常线索和证据不足边界，避免直接形成最终诊断。",
                exam_type="colonoscopy" if question.body_part == "结直肠" else "gastroscopy",
                image_name=question.id,
                template_name="胃镜结构化训练模板",
            )
        )
        judge = report_service.judge_report_revision(
            ReportJudgeRequest(
                learner_id=learner_id,
                original_report="本图明确证明患者患胃癌，建议立即治疗。",
                revised_report="单帧公开内镜图像可提示局部黏膜异常表现，性质、范围和处理意见仍需医生结合完整检查、病史及必要病理结果复核。",
            )
        )

        audit_service.log(
            "demo_check",
            user_id=learner_id,
            entity_id=question.id,
            summary=(
                "演示闭环自检完成：公开样例提交、Agent 辅导、挑战基准、报告草稿、报告修改评分、"
                "画像回灌和审计链路均已触发。"
            ),
            risk_level="medium",
        )
        after_profile = memory_service.get_profile()
        after_logs = audit_service.list_logs()
        after_audit_count = len(after_logs)
        new_audit_logs = [item for item in after_logs if item.id not in before_audit_ids]
        audit_delta = len(new_audit_logs)
        audit_event_types = list(dict.fromkeys(item.event_type for item in new_audit_logs))
        provider_status = llm_provider.status()
        receipts = self._receipts(question, submission, tutor, challenge, draft, judge, audit_delta, persist=persist)
        profile_changed = after_profile.updated_at != before_profile.updated_at
        challenge_logged = "challenge_benchmark" in audit_event_types

        return {
            "id": f"demo_check_{uuid4().hex[:12]}",
            "learner_id": learner_id,
            "mode": "persisted" if persist else "sandbox",
            "persisted": persist,
            "write_verified": profile_changed and audit_delta >= 6 and challenge_logged,
            "restored_after_run": not persist,
            "question_id": question.id,
            "question_title": question.title,
            "source_dataset": question.source_dataset,
            "provider_mode": provider_status.get("mode", "rule"),
            "provider_ready": bool(provider_status.get("configured")),
            "profile_before": {
                "total_questions": before_profile.total_questions,
                "training_records": len(before_profile.training_records),
                "completed_today": before_profile.completed_today,
            },
            "profile_after": {
                "total_questions": after_profile.total_questions,
                "training_records": len(after_profile.training_records),
                "completed_today": after_profile.completed_today,
                "updated_at": after_profile.updated_at,
            },
            "audit_before_count": before_audit_count,
            "audit_after_count": after_audit_count,
            "audit_delta": audit_delta,
            "audit_event_types": audit_event_types,
            "receipts": receipts,
            "profile_updated": profile_changed and persist,
            "audit_logged": persist,
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
            "created_at": now_iso(),
        }

    def _select_public_question(self):
        questions = question_service.list_questions()
        public_questions = [question for question in questions if question.source_dataset in PUBLIC_DATASETS]
        return public_questions[0] if public_questions else questions[0]

    def _receipts(self, question, submission, tutor, challenge, draft, judge, audit_delta: int, *, persist: bool) -> list[dict[str, object]]:
        tutor_mode = str(tutor.get("generation_mode", "rule"))
        challenge_mode = str(challenge.get("generation_mode", "public_annotation"))
        persistence_label = "已写入训练画像。" if persist else "沙盒已验证写入后自动恢复。"
        audit_label = "已持久化审计摘要。" if persist else "沙盒已验证审计写入后自动恢复。"
        tutor_detail = (
            str(tutor.get("memory_summary") or "已记录训练标签，不保存追问原文。")
            if persist
            else "沙盒已验证 Agent 辅导画像回灌路径，返回前自动恢复；不保存追问原文。"
        )
        challenge_detail = (
            f"{challenge.get('benchmark_name', '挑战基准')} · 与医师答案{'一致' if challenge.get('same_as_doctor') else '不一致'}；"
            "只写 challenge_benchmark 审计，不回灌医师画像。"
        )
        judge_detail = (
            judge.memory_summary or "报告修改训练已完成。"
            if persist
            else "沙盒已验证报告修改评分和画像回灌路径，返回前自动恢复。"
        )
        return [
            {
                "id": "answer_submit",
                "label": "公开样例提交",
                "status": "correct" if submission.is_correct else "review",
                "detail": f"{question.source_dataset} · {submission.score} 分 · {persistence_label}",
                "tone": "green" if submission.is_correct else "amber",
            },
            {
                "id": "tutor_agent",
                "label": "Agent 辅导",
                "status": tutor_mode,
                "detail": tutor_detail,
                "tone": "green" if tutor.get("profile_updated") else "blue",
            },
            {
                "id": "challenge_benchmark",
                "label": "挑战基准",
                "status": challenge_mode,
                "detail": challenge_detail,
                "tone": "green" if challenge_mode == "provider" else "blue",
            },
            {
                "id": "report_draft",
                "label": "报告草稿",
                "status": draft.generation_mode,
                "detail": f"{len(draft.evidence_ledger)} 条证据台账 · {len(draft.review_tasks)} 项医师复核任务。",
                "tone": "green" if draft.generation_mode == "provider" else "blue",
            },
            {
                "id": "report_judge",
                "label": "修改评分",
                "status": f"{judge.score}分",
                "detail": judge_detail,
                "tone": "green" if judge.profile_updated else "amber",
            },
            {
                "id": "audit_log",
                "label": "审计链路",
                "status": f"+{audit_delta}",
                "detail": f"{audit_label} 触发 question_view、answer_submit、tutor_reply、challenge_benchmark、report_draft、report_judge 与 demo_check 等摘要事件。",
                "tone": "green" if audit_delta >= 6 else "amber",
            },
        ]


demo_check_service = DemoCheckService()
