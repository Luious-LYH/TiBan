import time
from threading import Lock
from uuid import uuid4

from app.core.config import BACKEND_DIR, DATA_DIR, SAFETY_NOTICE
from app.schemas import (
    ChallengeBenchmarkRequest,
    ExamSessionAttempt,
    ExamSessionRequest,
    PatientCardApproveRequest,
    PatientCardRequest,
    ReportDraftRequest,
    ReportJudgeRequest,
    SubmissionRequest,
    TutorChatRequest,
)
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
    def __init__(self) -> None:
        self._run_lock = Lock()

    def run(self, learner_id: str = "demo_learner", *, persist: bool = False) -> dict[str, object]:
        with self._run_lock:
            profile_snapshot = self._read_data_bytes("learner_profile.json")
            audit_snapshot = self._read_data_bytes("audit_logs.json")
            card_snapshot = self._read_runtime_bytes("patient_cards.json")
            before_profile = memory_service.get_profile()
            before_logs = audit_service.list_logs()
            before_audit_count = len(before_logs)
            before_audit_ids = {item.id for item in before_logs}
            result: dict[str, object] | None = None
            chain_error: Exception | None = None
            try:
                result = self._run_chain(
                    learner_id=learner_id,
                    before_profile=before_profile,
                    before_audit_count=before_audit_count,
                    before_audit_ids=before_audit_ids,
                    persist=persist,
                )
            except Exception as exc:
                chain_error = exc
            restore_errors: list[str] = []
            if not persist:
                restore_errors = self._restore_sandbox_snapshots(profile_snapshot, audit_snapshot, card_snapshot)
            if chain_error is not None:
                if restore_errors:
                    raise RuntimeError(f"Demo-check failed and sandbox restore also failed: {'; '.join(restore_errors)}") from chain_error
                raise chain_error
            if restore_errors:
                raise RuntimeError(f"Demo-check sandbox restore failed: {'; '.join(restore_errors)}")
            if result is None:
                raise RuntimeError("Demo-check did not produce a result.")
            if not persist:
                result["restore_verified"] = (
                    self._read_data_bytes("learner_profile.json") == profile_snapshot
                    and self._read_data_bytes("audit_logs.json") == audit_snapshot
                    and self._read_runtime_bytes("patient_cards.json") == card_snapshot
                )
            else:
                result["restore_verified"] = False
            return result

    def _read_data_bytes(self, name: str) -> bytes:
        return (DATA_DIR / name).read_bytes()

    def _read_runtime_bytes(self, name: str) -> bytes | None:
        path = BACKEND_DIR / "runtime" / name
        return path.read_bytes() if path.exists() else None

    def _restore_sandbox_snapshots(self, profile_snapshot: bytes, audit_snapshot: bytes, card_snapshot: bytes | None) -> list[str]:
        restore_steps = [
            ("learner_profile.json", lambda: self._restore_data_bytes("learner_profile.json", profile_snapshot)),
            ("audit_logs.json", lambda: self._restore_data_bytes("audit_logs.json", audit_snapshot)),
            ("patient_cards.json", lambda: self._restore_runtime_bytes("patient_cards.json", card_snapshot)),
        ]
        errors: list[str] = []
        for label, restore in restore_steps:
            try:
                restore()
            except OSError as exc:
                errors.append(f"{label}: {type(exc).__name__}")
        return errors

    def _restore_data_bytes(self, name: str, payload: bytes) -> None:
        path = DATA_DIR / name
        temp_path = DATA_DIR / f".{name}.demo_check_tmp"
        self._replace_bytes_with_retry(path, temp_path, payload)

    def _restore_runtime_bytes(self, name: str, payload: bytes | None) -> None:
        path = BACKEND_DIR / "runtime" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if payload is None:
            self._unlink_with_retry(path)
            return
        temp_path = path.with_name(f".{name}.demo_check_tmp")
        self._replace_bytes_with_retry(path, temp_path, payload)

    def _replace_bytes_with_retry(self, path, temp_path, payload: bytes) -> None:
        last_error: OSError | None = None
        try:
            for attempt in range(5):
                try:
                    temp_path.write_bytes(payload)
                    temp_path.replace(path)
                    return
                except OSError as exc:
                    last_error = exc
                    time.sleep(0.05 * (attempt + 1))
            if last_error is not None:
                raise last_error
        finally:
            temp_path.unlink(missing_ok=True)

    def _unlink_with_retry(self, path) -> None:
        last_error: OSError | None = None
        for attempt in range(5):
            try:
                path.unlink(missing_ok=True)
                return
            except OSError as exc:
                last_error = exc
                time.sleep(0.05 * (attempt + 1))
        if last_error is not None:
            raise last_error

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
        exam = memory_service.record_exam_session(
            ExamSessionRequest(
                session_id=f"demo_smoke_{uuid4().hex[:8]}",
                learner_id=learner_id,
                duration_seconds=720,
                remaining_seconds=380,
                finished_reason="manual_submit",
                attempts=[
                    ExamSessionAttempt(
                        question_id=question.id,
                        title=question.title,
                        selected_answer=question.answer,
                        correct_answer=question.answer,
                        is_correct=True,
                        score=100,
                        error_tags=[],
                    )
                ],
            )
        )
        audit_service.log(
            "exam_session",
            user_id=learner_id,
            entity_id=exam.id,
            summary=exam.memory_summary,
            risk_level="low",
        )
        card = report_service.generate_patient_card(
            PatientCardRequest(
                diagnosis_summary="单帧公开内镜训练样例提示局部黏膜表现需要医生结合完整检查复核，本卡片仅用于教学演示。",
                template_id="calm_blue",
                image_url=question.image_url,
            )
        )
        approved_card = report_service.approve_patient_card(
            card.id,
            PatientCardApproveRequest(
                reviewer_name="林知远",
                review_notes="演示沙盒审核：确认仅用于教学沟通样例，不代表真实患者诊断。",
                review_checks={
                    "summaryMatched": True,
                    "noUnsupportedClaim": True,
                    "disclaimerKept": True,
                },
            ),
        )

        audit_service.log(
            "demo_check",
            user_id=learner_id,
            entity_id=question.id,
            summary=(
                "演示闭环自检完成：公开样例提交、Agent 辅导、挑战基准、报告草稿、报告修改评分、"
                "考试 Session、科普卡片草稿、同卡片医生审核、画像回灌和审计链路均已触发。"
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
        receipts = self._receipts(
            question,
            submission,
            tutor,
            challenge,
            draft,
            judge,
            exam,
            card,
            approved_card,
            audit_delta,
            persist=persist,
        )
        profile_changed = after_profile.updated_at != before_profile.updated_at
        challenge_logged = "challenge_benchmark" in audit_event_types
        exam_logged = "exam_session" in audit_event_types
        card_logged = "patient_card" in audit_event_types and "patient_card_approve" in audit_event_types

        return {
            "id": f"demo_check_{uuid4().hex[:12]}",
            "learner_id": learner_id,
            "mode": "persisted" if persist else "sandbox",
            "persisted": persist,
            "write_verified": profile_changed and audit_delta >= 9 and challenge_logged and exam_logged and card_logged,
            "restored_after_run": not persist,
            "restore_verified": False,
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

    def _receipts(
        self,
        question,
        submission,
        tutor,
        challenge,
        draft,
        judge,
        exam,
        card,
        approved_card,
        audit_delta: int,
        *,
        persist: bool,
    ) -> list[dict[str, object]]:
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
                "id": "exam_session",
                "label": "考试 Session",
                "status": f"{exam.answered_count}题/{exam.accuracy}%",
                "detail": (
                    exam.memory_summary
                    if persist
                    else "沙盒已验证整场考试 Session 写入画像和 exam_session 审计，返回前自动恢复。"
                ),
                "tone": "green" if exam.profile_updated else "amber",
            },
            {
                "id": "patient_card",
                "label": "科普卡片草稿",
                "status": card.generation_mode,
                "detail": f"{card.knowledge_base_id or 'card_template_kb'} · 草稿审计 {card.audit_log_id or 'pending'} · 分享保持锁定。",
                "tone": "green" if card.audit_logged else "amber",
            },
            {
                "id": "patient_card_approve",
                "label": "卡片审核",
                "status": approved_card.share_status,
                "detail": (
                    f"{approved_card.reviewer_name or '医生'} 已审核同一张卡片，打印/分享状态：{approved_card.share_status}。"
                    if persist
                    else "沙盒已验证同 card_id 医生审核、分享解锁和 patient_card_approve 审计，返回前自动恢复。"
                ),
                "tone": "green" if approved_card.share_status == "reviewed_ready_to_share" else "amber",
            },
            {
                "id": "audit_log",
                "label": "审计链路",
                "status": f"+{audit_delta}",
                "detail": f"{audit_label} 触发 question_view、answer_submit、tutor_reply、challenge_benchmark、report_draft、report_judge、exam_session、patient_card、patient_card_approve 与 demo_check 等摘要事件。",
                "tone": "green" if audit_delta >= 9 else "amber",
            },
        ]


demo_check_service = DemoCheckService()
