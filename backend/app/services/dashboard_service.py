from app.core.config import SAFETY_NOTICE
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
        audit_logs = read_json("audit_logs.json")
        challenge_logs = [item for item in audit_logs if item.get("event_type") == "challenge_benchmark"]
        provider_self_tests = [item for item in audit_logs if item.get("event_type") == "provider_self_test"]
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
            "report_template_count": len(report_kb.get("templates", [])),
            "training_record_count": len(profile.training_records),
            "audit_log_count": len(audit_logs),
            "admission_grade": admission_state.get("grade", "NA"),
            "admission_provider_called": bool(admission_state.get("provider_called")),
            "knowledge_source_chain": self._knowledge_source_chain(real_sample_kb, public_questions, report_kb, card_kb),
            "evidence_receipts": [
                self._receipt(
                    "real_sample_kb",
                    "真实公开样例库",
                    "ready" if public_questions else "missing",
                    f"{len(public_questions)} 条公开图文题已由 real_sample_knowledge.json 映射到题库。",
                    "/training?source=public",
                    "green" if public_questions else "amber",
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
                    "audited" if challenge_logs else "not_run",
                    (
                        f"已有 {len(challenge_logs)} 条 challenge_benchmark 审计；基准不重复回灌画像。"
                        if challenge_logs
                        else "尚未产生 challenge_benchmark 审计；可进入比拼模式提交一题。"
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
                    "title": "边刷边问 Agent",
                    "detail": "围绕当前题追问证据链，系统记录训练标签但不保存自由文本。",
                    "href": "/training",
                    "expected_state": "Tutor chat + memory summary",
                },
                {
                    "step": 4,
                    "title": "报告生成与修改",
                    "detail": "用同一批公开样例生成报告草稿，再用 AI judge 评分改写。",
                    "href": "/report",
                    "expected_state": "来源追踪 + 幻觉审查 + 画像回灌",
                },
                {
                    "step": 5,
                    "title": "模型准入探测",
                    "detail": "用公开样例测试用户自带 Provider，结果同步到首页和模型中心。",
                    "href": "/models",
                    "expected_state": "provider called 或 rule draft 明确标注",
                },
            ],
            "gaps": gaps,
            "safety_notice": SAFETY_NOTICE,
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
