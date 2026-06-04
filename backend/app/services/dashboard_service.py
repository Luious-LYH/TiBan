from collections import Counter

from app.core.config import PROJECT_DIR, SAFETY_NOTICE
from app.services.audit_service import now_iso
from app.services.data_store import read_json
from app.services.llm_provider import llm_provider
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
            "platform_readiness": self.get_readiness(),
            "safety_notice": SAFETY_NOTICE,
            "mock_evaluation_notice": "模型能力分为演示 mock 和接口预留，不代表真实临床评测结果。",
            "reference_inspirations": [
                "AMBOSS: Study/Exam Mode 与 session analysis 的题库训练组织",
                "UWorld: Tutor/Timed 模式与错题解释卡片",
                "Lecturio: Qbank、AI Tutor 与持续表现追踪",
                "Kvasir/EndoBench: 公开内镜样例用于医师训练素材",
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

    def get_readiness(self) -> dict[str, object]:
        profile = memory_service.get_profile()
        questions = question_service.list_questions()
        public_questions = [q for q in questions if q.source_dataset in {"Kvasir-VQA-x1", "Kvasir-VQA", "EndoBench"}]
        admission_state = model_service.admission_state()
        provider_status = llm_provider.status()
        real_sample_kb = read_json("real_sample_knowledge.json")
        report_kb = read_json("report_knowledge_base.json")
        card_kb = read_json("card_template_knowledge.json")
        real_sample_coverage = self._real_sample_coverage(real_sample_kb, public_questions)
        audit_logs = read_json("audit_logs.json")
        challenge_logs = [item for item in audit_logs if item.get("event_type") == "challenge_benchmark"]
        provider_self_tests = [item for item in audit_logs if item.get("event_type") == "provider_self_test"]
        latest_exam_replay = self._latest_exam_replay(profile)
        modules = [
            self._module(
                "backend_api",
                "后端 API",
                "live",
                "FastAPI 服务在线，前端调用会标注 backend/fallback。",
                "/",
                "green",
            ),
            self._module(
                "real_samples",
                "真实公开样例",
                "ready" if public_questions else "empty",
                f"已接入 {len(public_questions)} 条 Kvasir/EndoBench 公开图文样例。",
                "/training?source=public",
                "green" if public_questions else "amber",
            ),
            self._module(
                "training_memory",
                "医师画像回灌",
                "ready" if profile.training_records else "seed",
                f"{profile.name} 当前有 {len(profile.training_records)} 条训练/Agent/报告记录。",
                "/profile",
                "green" if profile.training_records else "amber",
            ),
            self._module(
                "exam_replay",
                "考试 Session 复盘",
                "ready" if latest_exam_replay else "not_run",
                (
                    f"{latest_exam_replay['session_id']} · 错题 {latest_exam_replay['wrong_count']} 题，可直接复盘。"
                    if latest_exam_replay
                    else "尚未写入考试 Session；可从考试模式交卷生成复盘队列。"
                ),
                latest_exam_replay["href"] if latest_exam_replay else "/training?mode=exam",
                "green" if latest_exam_replay else "blue",
            ),
            self._module(
                "report_kb",
                "报告知识库",
                "ready" if report_kb.get("templates") else "empty",
                f"报告模板 {len(report_kb.get('templates', []))} 个，科普模板 {len(card_kb.get('templates', []))} 个。",
                "/report",
                "green" if report_kb.get("templates") else "amber",
            ),
            self._module(
                "provider",
                "推理 Provider",
                "provider" if provider_status.get("configured") else "rule",
                (
                    f"{provider_status.get('provider', 'provider')} · {provider_status.get('model', 'model')} 可真实调用。"
                    if provider_status.get("configured")
                    else "未配置后端 Provider，平台显式降级为规则/知识库草案。"
                ),
                "/models",
                "green" if provider_status.get("configured") else "amber",
            ),
            self._module(
                "model_admission",
                "模型准入状态",
                "provider called" if admission_state.get("provider_called") else "rule draft",
                f"{admission_state.get('provider_name', 'Provider')} · Grade {admission_state.get('grade', 'NA')} · {admission_state.get('total_score', 0)} 分。",
                "/models",
                "green" if admission_state.get("provider_called") else "blue",
            ),
            self._module(
                "audit",
                "审计日志",
                "ready" if audit_logs else "empty",
                f"已记录 {len(audit_logs)} 条训练、报告、准入或上传事件。",
                "/audit",
                "green" if audit_logs else "amber",
            ),
        ]
        readiness_score = round(sum(1 for item in modules if item["tone"] == "green") / len(modules) * 100)
        gaps: list[str] = []
        if not provider_status.get("configured"):
            gaps.append("如需展示真实大模型推理，请在后端 .env 配置 OpenAI-compatible Provider，或在模型准入页临时输入 key。")
        if not admission_state.get("provider_called"):
            gaps.append("最近模型准入仍是规则草案；可用公开样例运行一次真实 Provider 探测。")
        if len(public_questions) < 6:
            gaps.append("真实公开样例数量偏少，后续可继续从本地 VQA 数据集中扩充题库和报告知识库。")
        return {
            "generated_at": now_iso(),
            "overall_score": readiness_score,
            "backend_ready": True,
            "provider_ready": bool(provider_status.get("configured")),
            "provider_mode": provider_status.get("mode", "rule"),
            "knowledge_ready": bool(public_questions and report_kb.get("templates")),
            "memory_ready": bool(profile.training_records),
            "qbank_count": len(questions),
            "real_sample_count": len(public_questions),
            "real_sample_coverage": real_sample_coverage,
            "report_template_count": len(report_kb.get("templates", [])),
            "training_record_count": len(profile.training_records),
            "exam_session_count": len(profile.exam_sessions or []),
            "latest_exam_replay": latest_exam_replay,
            "audit_log_count": len(audit_logs),
            "admission_grade": admission_state.get("grade", "NA"),
            "admission_provider_called": bool(admission_state.get("provider_called")),
            "knowledge_source_chain": self._knowledge_source_chain(real_sample_kb, public_questions, report_kb, card_kb),
            "evidence_receipts": [
                self._receipt(
                    "real_sample_kb",
                    "真实公开样例库",
                    "ready" if public_questions else "missing",
                    f"{len(public_questions)} 条公开图文题已由 real_sample_knowledge.json 映射到题库；图片资产 {real_sample_coverage['asset_present_count']}/{real_sample_coverage['asset_checked_count']} 已校验存在。",
                    "/training?source=public",
                    "green" if public_questions else "amber",
                ),
                self._receipt(
                    "exam_replay",
                    "考试 Session 复盘",
                    "ready" if latest_exam_replay else "not_run",
                    (
                        f"{latest_exam_replay['session_id']} 已写入画像；错题队列 {latest_exam_replay['wrong_count']} 题，复盘不会重复计数。"
                        if latest_exam_replay
                        else "尚未产生考试 Session；从考试模式交卷后会生成可复盘收据。"
                    ),
                    latest_exam_replay["href"] if latest_exam_replay else "/training?mode=exam",
                    "green" if latest_exam_replay else "blue",
                ),
                self._receipt(
                    "report_kb",
                    "报告/科普知识库",
                    "ready" if report_kb.get("templates") and card_kb.get("templates") else "partial",
                    f"报告模板 {len(report_kb.get('templates', []))} 个，卡片模板 {len(card_kb.get('templates', []))} 个。",
                    "/report",
                    "green" if report_kb.get("templates") and card_kb.get("templates") else "amber",
                ),
                self._receipt(
                    "provider_status",
                    "Provider 通道",
                    "provider" if provider_status.get("configured") else "rule",
                    (
                        f"{provider_status.get('provider')} · {provider_status.get('model')} 已由后端 .env 配置。"
                        if provider_status.get("configured")
                        else "后端未配置真实 Provider；页面和接口会显式标注 rule/fallback。"
                    ),
                    "/models",
                    "green" if provider_status.get("configured") else "amber",
                ),
                self._receipt(
                    "provider_self_test",
                    "Provider 轻量自检",
                    "logged" if provider_self_tests else "not_run",
                    (
                        f"最近已有 {len(provider_self_tests)} 条 provider_self_test 摘要审计。"
                        if provider_self_tests
                        else "尚未运行轻量自检；可在模型页验证通道且不更新准入状态。"
                    ),
                    "/models",
                    "green" if provider_self_tests else "blue",
                ),
                self._receipt(
                    "model_admission",
                    "样例级模型准入",
                    "provider_called" if admission_state.get("provider_called") else "rule_draft",
                    (
                        f"最近准入 {admission_state.get('provider_name', 'Provider')} · Grade {admission_state.get('grade', 'NA')} · {'provider called' if admission_state.get('provider_called') else 'rule draft'}。"
                    ),
                    "/models",
                    "green" if admission_state.get("provider_called") else "blue",
                ),
                self._receipt(
                    "challenge_audit",
                    "训练挑战基准",
                    "audited" if challenge_logs else "sandbox_available",
                    (
                        f"已有 {len(challenge_logs)} 条 challenge_benchmark 审计；基准不重复回灌画像。"
                        if challenge_logs
                        else "暂无持久 challenge_benchmark 审计；首页沙盒自检可即时验证并自动恢复，点击“写入演示画像”或提交比拼题可保留审计。"
                    ),
                    "/training?view=challenge",
                    "green" if challenge_logs else "blue",
                ),
                self._receipt(
                    "audit_log",
                    "审计日志",
                    "ready" if audit_logs else "empty",
                    f"当前 audit_logs.json 保存 {len(audit_logs)} 条摘要事件，不保存 API key 或自由追问原文。",
                    "/audit",
                    "green" if audit_logs else "amber",
                ),
            ],
            "modules": modules,
            "demo_path": [
                {
                    "step": 1,
                    "title": "训练驾驶舱",
                    "detail": "确认医师身份、今日任务、能力画像和平台真实性状态。",
                    "href": "/",
                    "expected_state": "后端在线 + 公开样例已接入",
                },
                {
                    "step": 2,
                    "title": "公开样例刷题",
                    "detail": "选择真实内镜图像题，提交后回灌错题/能力画像。",
                    "href": "/training?source=public",
                    "expected_state": "真实图文样例 + Agent 可追问",
                },
                {
                    "step": 3,
                    "title": "考试 Session 复盘",
                    "detail": "交卷后按 session 恢复本场错题队列，复盘视图不重复增加训练计数。",
                    "href": latest_exam_replay["href"] if latest_exam_replay else "/training?mode=exam",
                    "expected_state": "exam_session + wrong queue + profile updated",
                },
                {
                    "step": 4,
                    "title": "边刷边问 Agent",
                    "detail": "围绕当前题追问证据链，系统记录训练标签但不保存自由文本。",
                    "href": "/training",
                    "expected_state": "Tutor chat + memory summary",
                },
                {
                    "step": 5,
                    "title": "报告生成与修改",
                    "detail": "用同一批公开样例生成报告草稿，再用 AI judge 评分改写。",
                    "href": "/report",
                    "expected_state": "来源追踪 + 幻觉审查 + 画像回灌",
                },
                {
                    "step": 6,
                    "title": "模型准入探测",
                    "detail": "用公开样例测试用户自带 Provider，结果同步到首页和模型中心。",
                    "href": "/models",
                    "expected_state": "provider called 或 rule draft 明确标注",
                },
            ],
            "gaps": gaps,
            "safety_notice": SAFETY_NOTICE,
        }

    def get_delivery_report(self) -> dict[str, object]:
        readiness = self.get_readiness()
        profile = memory_service.get_profile()
        admission_state = model_service.admission_state()
        provider_status = llm_provider.status()
        audit_logs = read_json("audit_logs.json")
        real_sample_kb = read_json("real_sample_knowledge.json")
        report_kb = read_json("report_knowledge_base.json")
        card_kb = read_json("card_template_knowledge.json")
        event_counts = Counter(str(item.get("event_type", "unknown")) for item in audit_logs)
        provider_self_tests = [item for item in audit_logs if item.get("event_type") == "provider_self_test"]
        provider_self_test_passed = any(self._provider_self_test_ok(item) for item in provider_self_tests)
        latest_self_test_state = (
            self._provider_self_test_state(provider_self_tests[0])
            if provider_self_tests
            else "not_run"
        )
        admission_provider_called = bool(admission_state.get("provider_called"))
        provider_configured = bool(provider_status.get("configured"))
        real_inference_verified = bool(provider_self_test_passed or admission_provider_called)
        if real_inference_verified:
            provider_verification_label = "真实调用已验证"
            provider_verification_note = "交付证据中已有 Provider 自检成功或样例级准入调用记录。"
        elif provider_configured:
            provider_verification_label = "已配置，未验证调用"
            provider_verification_note = "后端 Provider 配置齐全，但当前交付报告没有成功自检或样例准入调用证据。"
        else:
            provider_verification_label = "规则/知识库模式"
            provider_verification_note = "后端未配置真实 Provider；训练输出保持 rule/fallback 标注。"
        source_chain = readiness.get("knowledge_source_chain", [])
        evidence_receipts = readiness.get("evidence_receipts", [])
        latest_exam = readiness.get("latest_exam_replay")
        return {
            "generated_at": now_iso(),
            "title": "ARIS v2.0 交付证据报告",
            "scope": "内镜医师教学训练、刷题复盘、报告修改训练、患者沟通卡片和模型接入前准入检查。",
            "doctor_context": {
                "learner_id": profile.learner_id,
                "name": profile.name,
                "title": profile.title,
                "department": profile.department,
                "training_stage": profile.training_stage,
                "daily_target": profile.daily_target,
                "completed_today": profile.completed_today,
                "streak_days": profile.streak_days,
            },
            "platform_summary": {
                "overall_score": readiness.get("overall_score"),
                "backend_ready": readiness.get("backend_ready"),
                "provider_mode": readiness.get("provider_mode"),
                "provider_ready": readiness.get("provider_ready"),
                "knowledge_ready": readiness.get("knowledge_ready"),
                "memory_ready": readiness.get("memory_ready"),
                "qbank_count": readiness.get("qbank_count"),
                "real_sample_count": readiness.get("real_sample_count"),
                "real_sample_coverage": readiness.get("real_sample_coverage"),
                "report_template_count": readiness.get("report_template_count"),
                "audit_log_count": readiness.get("audit_log_count"),
                "exam_session_count": readiness.get("exam_session_count"),
                "admission_grade": readiness.get("admission_grade"),
                "admission_provider_called": readiness.get("admission_provider_called"),
            },
            "workflow_proofs": [
                {
                    "id": "training_loop",
                    "name": "训练题库与画像回灌",
                    "status": "ready" if readiness.get("training_record_count") else "seed",
                    "evidence": f"{readiness.get('qbank_count')} 道题，{readiness.get('real_sample_count')} 条公开图文样例，{readiness.get('training_record_count')} 条训练/Agent/报告记录。",
                    "route": "/training",
                },
                {
                    "id": "exam_replay",
                    "name": "考试 Session 复盘",
                    "status": "ready" if latest_exam else "not_run",
                    "evidence": latest_exam.get("detail") if isinstance(latest_exam, dict) else "尚未生成持久考试 Session；首页沙盒自检可即时验证写入与恢复。",
                    "route": latest_exam.get("href") if isinstance(latest_exam, dict) else "/training?mode=exam",
                },
                {
                    "id": "challenge_benchmark",
                    "name": "医生 AI 比拼基准",
                    "status": "audited" if event_counts.get("challenge_benchmark") else "sandbox_available",
                    "evidence": f"持久 challenge_benchmark 审计 {event_counts.get('challenge_benchmark', 0)} 条；沙盒自检会真实触发并恢复。",
                    "route": "/training?view=challenge",
                },
                {
                    "id": "report_training",
                    "name": "诊断报告生成与修改训练",
                    "status": "ready" if report_kb.get("templates") else "partial",
                    "evidence": f"报告模板 {len(report_kb.get('templates', []))} 个；report_draft 审计 {event_counts.get('report_draft', 0)} 条，report_judge 审计 {event_counts.get('report_judge', 0)} 条。",
                    "route": "/report",
                },
                {
                    "id": "patient_card_review",
                    "name": "科普卡片医生审核闸门",
                    "status": "ready" if card_kb.get("templates") else "partial",
                    "evidence": f"卡片模板 {len(card_kb.get('templates', []))} 个；patient_card 审计 {event_counts.get('patient_card', 0)} 条，patient_card_approve 审计 {event_counts.get('patient_card_approve', 0)} 条。",
                    "route": "/card",
                },
                {
                    "id": "provider_admission",
                    "name": "用户 Provider 接入与样例级准入",
                    "status": "provider_called" if admission_state.get("provider_called") else "rule_draft",
                    "evidence": f"{admission_state.get('provider_name', 'Provider')} · Grade {admission_state.get('grade', 'NA')} · provider_called={bool(admission_state.get('provider_called'))}。",
                    "route": "/models",
                },
                {
                    "id": "audit_safety",
                    "name": "审计与隐私边界",
                    "status": "ready" if audit_logs else "empty",
                    "evidence": f"当前保存 {len(audit_logs)} 条摘要审计；接口和脚本不返回 API key、API base 明文或自由追问全文。",
                    "route": "/audit",
                },
            ],
            "knowledge_source_chain": source_chain,
            "evidence_receipts": evidence_receipts,
            "audit_event_counts": [{"event_type": event_type, "count": count} for event_type, count in event_counts.most_common()],
            "provider_state": {
                "configured": provider_configured,
                "mode": provider_status.get("mode", "rule"),
                "provider_declared": bool(provider_status.get("provider") and provider_status.get("provider") != "mock"),
                "model": provider_status.get("model", "gpt-4o-mini"),
                "self_test_logged": bool(provider_self_tests),
                "self_test_count": len(provider_self_tests),
                "self_test_verified": provider_self_test_passed,
                "latest_self_test_state": latest_self_test_state,
                "admission_provider_called": admission_provider_called,
                "admission_state_kind": "provider_admission" if admission_provider_called else "rule_draft",
                "admission_safe_for_training": bool(admission_state.get("safe_for_training")),
                "real_inference_verified": real_inference_verified,
                "verification_label": provider_verification_label,
                "verification_note": provider_verification_note,
            },
            "verification_commands": [
                {
                    "name": "总控验证",
                    "command": "python scripts\\verify_all.py",
                    "covers": "后端闭环、Provider 体检、UI 路由、lint/build、真实图片资产、密钥扫描和状态文件漂移。",
                },
                {
                    "name": "演示闭环 smoke",
                    "command": "python scripts\\demo_smoke.py",
                    "covers": "公开样例提交、Agent 辅导、挑战基准、报告训练、考试 Session、卡片审核和沙盒恢复。",
                },
                {
                    "name": "前端主图 smoke",
                    "command": "node scripts\\ui_smoke.mjs",
                    "covers": "关键路由非空白、Live evidence、训练/报告/卡片关键主图真实加载。",
                },
                {
                    "name": "Provider 体检",
                    "command": "python scripts\\provider_doctor.py",
                    "covers": ".env 忽略状态、Provider diagnostics、Base URL 预检；默认不发送模型请求。",
                },
                {
                    "name": "交付证据导出",
                    "command": "python scripts\\export_delivery_report.py --output docs\\DELIVERY_EVIDENCE_REPORT.md",
                    "covers": "从当前后端 readiness、知识库和审计状态导出可交付 Markdown 证据包。",
                },
            ],
            "current_boundaries": [
                "平台定位是教学训练和医生审核前辅助，不作为独立诊断依据。",
                "未配置 Provider 时会明确显示 rule/fallback，不伪装成真实模型推理。",
                "模型准入是训练 Agent 接入前检查，不是批量临床评测或统计学评测。",
                "公开样例来自本地知识库映射和公开图像资产，只用于演示训练闭环。",
                "本机上传图只用于受控预览或教学流转，不应包含真实患者身份信息。",
            ],
            "gaps": readiness.get("gaps", []),
            "safety_notice": SAFETY_NOTICE,
            "report_integrity": {
                "source": "backend_runtime_state",
                "writes_state": False,
                "secrets_included": False,
                "api_key_returned": False,
                "provider_base_returned": False,
            },
        }

    def _provider_self_test_ok(self, audit_item: dict[str, object]) -> bool:
        metadata = audit_item.get("metadata")
        if isinstance(metadata, dict) and "provider_called" in metadata:
            return bool(metadata.get("provider_called"))
        return "结果 ok" in str(audit_item.get("summary", ""))

    def _provider_self_test_state(self, audit_item: dict[str, object]) -> str:
        metadata = audit_item.get("metadata")
        if isinstance(metadata, dict) and "provider_called" in metadata:
            return "ok" if metadata.get("provider_called") else "failed"
        return "ok" if "结果 ok" in str(audit_item.get("summary", "")) else "logged_failed_or_unknown"

    def _latest_exam_replay(self, profile) -> dict[str, object] | None:
        sessions = profile.exam_sessions or []
        if not sessions:
            return None
        session = sessions[0]
        session_id = str(session.get("session_id") or session.get("id") or "exam_session")
        wrong_questions = [str(item) for item in session.get("wrong_questions", [])]
        return {
            "id": str(session.get("id", session_id)),
            "session_id": session_id,
            "date": str(session.get("date", "")),
            "answered_count": int(session.get("answered_count", 0) or 0),
            "correct_count": int(session.get("correct_count", 0) or 0),
            "accuracy": int(session.get("accuracy", 0) or 0),
            "average_score": int(session.get("average_score", 0) or 0),
            "wrong_count": len(wrong_questions),
            "wrong_questions": wrong_questions,
            "elapsed_seconds": int(session.get("elapsed_seconds", 0) or 0),
            "profile_updated": bool(session.get("profile_updated", False)),
            "created_at": str(session.get("created_at", "")),
            "href": f"/feedback?session={session_id}",
            "profile_href": "/profile?tab=records",
            "status": "已写入画像" if session.get("profile_updated", False) else "待核查",
            "detail": f"本场考试 {session.get('answered_count', 0)} 题，正确率 {session.get('accuracy', 0)}%，错题 {len(wrong_questions)} 题。",
        }

    def _knowledge_source_chain(
        self,
        real_sample_kb: list[dict],
        public_questions: list,
        report_kb: dict,
        card_kb: dict,
    ) -> list[dict[str, object]]:
        sample_ids = [str(item.get("id")) for item in real_sample_kb[:4] if item.get("id")]
        report_templates = [str(item.get("name")) for item in report_kb.get("templates", []) if item.get("name")]
        card_templates = [str(item.get("name")) for item in card_kb.get("templates", []) if item.get("name")]
        return [
            {
                "id": "real_sample_knowledge",
                "label": "真实公开图文样例",
                "source_file": "real_sample_knowledge.json",
                "record_count": len(real_sample_kb),
                "sample_ids": sample_ids,
                "used_by": ["题库训练", "报告中心", "科普卡片配图", "模型准入"],
                "proof": f"{len(public_questions)} 道训练题由公开样例映射生成；报告、科普卡片配图和模型准入复用同一批样例 ID。公开教学样例不代表批量临床评测。",
                "href": "/training?source=public",
                "tone": "green" if real_sample_kb and public_questions else "amber",
            },
            {
                "id": "report_knowledge_base",
                "label": "诊断报告知识库",
                "source_file": "report_knowledge_base.json",
                "record_count": len(report_templates),
                "sample_ids": report_templates[:4],
                "used_by": ["报告草稿", "报告修改评分", "幻觉审查"],
                "proof": "模板、证据等级和审查规则会进入报告草稿 source_trace 与 judge rubric。",
                "href": "/report",
                "tone": "green" if report_templates else "amber",
            },
            {
                "id": "card_template_knowledge",
                "label": "科普卡片模板库",
                "source_file": "card_template_knowledge.json",
                "record_count": len(card_templates),
                "sample_ids": card_templates[:4],
                "used_by": ["科普卡片草稿", "医生审核闸门", "分享/打印锁"],
                "proof": "模板 ID、视觉规则和免责声明会写入 patient_card 收据，审核通过后才解锁分享。",
                "href": "/card",
                "tone": "green" if card_templates else "amber",
            },
        ]

    def _real_sample_coverage(self, real_sample_kb: list[dict], public_questions: list) -> dict[str, object]:
        asset_root = PROJECT_DIR / "frontend" / "public"
        dataset_counter = Counter(str(item.get("source_dataset", "unknown")) for item in real_sample_kb)
        use_counter = Counter(str(item.get("use", "unknown")) for item in real_sample_kb)
        complexity_counter = Counter(str(item.get("complexity", "unknown")) for item in real_sample_kb)
        missing_assets: list[str] = []
        present_assets = 0
        for item in real_sample_kb:
            image_url = str(item.get("image_url", ""))
            if not image_url:
                missing_assets.append(str(item.get("id", "missing_image_url")))
                continue
            relative_parts = image_url.lstrip("/").split("/")
            if asset_root.joinpath(*relative_parts).exists():
                present_assets += 1
            else:
                missing_assets.append(str(item.get("id", image_url)))
        return {
            "source_file": "real_sample_knowledge.json",
            "local_data_hint": r"E:\2.Projects\ARIS\VQA\data",
            "total_records": len(real_sample_kb),
            "mapped_question_count": len(public_questions),
            "asset_checked_count": len(real_sample_kb),
            "asset_present_count": present_assets,
            "missing_assets": missing_assets[:12],
            "dataset_distribution": [{"label": label, "count": count} for label, count in dataset_counter.most_common()],
            "use_distribution": [{"label": label, "count": count} for label, count in use_counter.most_common()],
            "complexity_distribution": [{"label": label, "count": count} for label, count in complexity_counter.most_common()],
            "sample_ids": [str(item.get("id")) for item in real_sample_kb[:8] if item.get("id")],
            "coverage_note": "当前抽取本地 VQA 公开样例构建演示级知识库；用于医师教学训练、报告/卡片配图和模型准入，不代表完整数据集评测。",
        }

    def _module(
        self,
        module_id: str,
        label: str,
        status: str,
        detail: str,
        href: str,
        tone: str,
    ) -> dict[str, str]:
        return {
            "id": module_id,
            "label": label,
            "status": status,
            "detail": detail,
            "href": href,
            "tone": tone,
        }

    def _receipt(
        self,
        receipt_id: str,
        label: str,
        status: str,
        detail: str,
        href: str,
        tone: str,
    ) -> dict[str, str]:
        return {
            "id": receipt_id,
            "label": label,
            "status": status,
            "detail": detail,
            "href": href,
            "tone": tone,
        }


dashboard_service = DashboardService()
