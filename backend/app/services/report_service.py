import re
import json
from uuid import uuid4

from app.core.config import BACKEND_DIR, SAFETY_NOTICE
from app.schemas import (
    PatientCard,
    PatientCardApproveRequest,
    PatientCardRequest,
    ReportDraft,
    ReportDraftRequest,
    ReportJudgeRequest,
    ReportJudgeResponse,
)
from app.services.audit_service import audit_service, now_iso
from app.services.data_store import read_json
from app.services.llm_provider import llm_provider
from app.services.safety_service import safety_service


HIGH_RISK_TERMS = ["癌", "恶性", "早癌", "高级别", "活动性出血", "穿孔", "切除", "活检", "病理"]
UNSUPPORTED_SINGLE_FRAME_PATTERNS = [
    r"全结肠.*未见",
    r"全胃.*未见",
    r"观察范围包括",
    r"到达.*回盲部",
    r"退镜时间",
    r"病理提示",
    r"已行.*切除",
    r"已取.*活检",
]
PATIENT_CARD_STORE = BACKEND_DIR / "runtime" / "patient_cards.json"


class ReportService:
    def generate_report_draft(self, request: ReportDraftRequest) -> ReportDraft:
        raw_text = request.finding_text.strip()
        kb = self.report_knowledge_base()
        text = safety_service.redact_sensitive_text(raw_text)
        sample = self._sample_from_image_name(request.image_name)
        image_path = self._provider_image_path(request.image_name, sample)
        provider_result = self._provider_observation(request, text, sample, image_path)
        model_observation = provider_result.text if provider_result.ok else None
        findings = self._split_findings(text or self._default_finding(kb))
        if model_observation:
            findings.append(f"模型视觉观察摘要（需医师复核）：{model_observation[:180]}")
        review = safety_service.review_text(raw_text)
        uncertainty_notes = [
            "草稿优先整理医生输入；未上传图片时，仅基于模板知识库生成训练样例。",
            "如需形成正式报告，应由内镜医生结合完整图像、病史和必要检查复核。",
        ]
        if sample:
            uncertainty_notes.insert(0, f"已载入公开样例标注：{sample.get('source_dataset')}；标注仅作为教学参考。")
        elif request.image_name and request.image_name.startswith("uploads/"):
            note = "已接收上传图片；"
            note += "已尝试调用视觉 Provider 生成观察摘要。" if provider_result.ok else "Provider 未配置或调用失败，当前不执行真实视觉推理。"
            uncertainty_notes.insert(0, note)
        elif request.image_name:
            uncertainty_notes.insert(0, f"已接收图片引用：{request.image_name}；若非公开样例或受控上传，后端不会进行视觉推理。")
        if provider_result.error and provider_result.error != "provider_not_configured":
            uncertainty_notes.insert(0, f"Provider 调用失败，已降级为规则/知识库草稿：{provider_result.error}")
        if not review["passed"]:
            uncertainty_notes.insert(0, "输入中可能包含敏感或越界表述，已在草稿回显中脱敏或提示复核。")
        review_points = [
            "确认部位、范围、数量和图片证据是否一致。",
            "检查是否存在“明确诊断”“必须治疗”等过强表述。",
            "必要时补充活检、病理或其他检查结果。",
        ]
        single_frame = bool(request.image_name)
        image_quality = self._image_quality(request.image_name, findings)
        exam_context = self._exam_context(request.exam_type, request.image_name)
        draft_impression = self._draft_impression(findings)
        audit = self._hallucination_audit([*findings, *draft_impression], single_frame=single_frame)
        evidence_ledger = self._evidence_ledger(request, findings, draft_impression, sample, provider_result.ok)
        review_tasks = self._review_tasks(audit, request.image_name)
        generation_mode = "provider" if provider_result.ok else "fallback" if provider_result.error and provider_result.error != "provider_not_configured" else "rule"
        source_trace = self._source_trace(request, sample, provider_result)
        draft = ReportDraft(
            id=f"report_{uuid4().hex[:12]}",
            input_finding_text=text,
            exam_type=request.exam_type,
            structured_findings=findings,
            draft_impression=draft_impression,
            review_points=review_points,
            uncertainty_notes=uncertainty_notes,
            template_name=request.template_name or self._template_name(kb, request.exam_type),
            evidence_source=[
                "医生输入所见" if raw_text else "报告知识库模板",
                "图片上传占位" if request.image_name else "未上传图片",
                "report_knowledge_base.json",
            ],
            draft_status="needs_human_review",
            exam_context=exam_context,
            image_quality=image_quality,
            evidence_ledger=evidence_ledger,
            hallucination_audit=audit,
            review_tasks=review_tasks,
            generation_mode=generation_mode,
            provider_status=provider_result.public_status(),
            model_observation=model_observation,
            source_trace=source_trace,
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        audit_service.log(
            "report_draft",
            user_id="doctor_demo",
            entity_id=draft.id,
            summary=f"生成结构化报告草稿；模式 {generation_mode}；医生审核必需。" if review["passed"] else "报告草稿触发安全审查提醒。",
            risk_level="high",
        )
        return draft

    def judge_report_revision(self, request: ReportJudgeRequest) -> ReportJudgeResponse:
        revised = safety_service.redact_sensitive_text(request.revised_report.strip())
        original = safety_service.redact_sensitive_text(request.original_report.strip())
        provider_result = self._provider_report_judge(request, original, revised)
        rubric_scores = {
            "部位描述": 25 if any(token in revised for token in ["胃", "肠", "食管", "胃窦", "结肠"]) else 12,
            "所见与诊断区分": 25 if any(token in revised for token in ["所见", "表现", "考虑", "建议复核"]) else 10,
            "不确定性表达": 25 if any(token in revised for token in ["需", "结合", "复核", "证据不足"]) else 8,
            "安全边界": 25 if not any(token in revised for token in ["确诊", "必须", "立即治疗", "保证"]) else 5,
        }
        score = sum(rubric_scores.values())
        issues: list[str] = []
        if "确诊" in original or "明确证明" in original:
            issues.append("原报告存在过强确定性，修改时应改为观察性描述。")
        if rubric_scores["安全边界"] < 20:
            issues.append("修改稿仍含可能越界的诊疗承诺或最终诊断语气。")
        if rubric_scores["不确定性表达"] < 20:
            issues.append("建议补充医生复核、病理或完整检查上下文。")
        strengths = [
            "已尝试保留内镜所见。",
            "修改稿可作为医生审核前训练文本。",
        ]
        if provider_result.ok:
            strengths.append("已完成一次请求级 Provider 评阅，建议仅作为医生训练反馈参考。")
        elif provider_result.error and provider_result.error != "provider_not_configured":
            issues.append(f"Provider 评阅调用失败，已降级为规则 rubric：{provider_result.error}")
        generation_mode = "provider" if provider_result.ok else "fallback" if provider_result.error and provider_result.error != "provider_not_configured" else "rule"
        response = ReportJudgeResponse(
            id=f"judge_{uuid4().hex[:12]}",
            score=score,
            strengths=strengths,
            issues=issues or ["未发现明显越界表达，仍需医生最终审核。"],
            suggested_revision=self._suggest_revision(revised),
            rubric_scores=rubric_scores,
            recommended_drills=self._recommended_report_drills(rubric_scores),
            generation_mode=generation_mode,
            provider_status=provider_result.public_status(),
            provider_feedback=provider_result.text if provider_result.ok else None,
            source_trace=[
                {
                    "source_type": "rule_rubric",
                    "label": "规则 rubric",
                    "used": True,
                    "detail": "部位描述 / 所见与诊断区分 / 不确定性表达 / 安全边界",
                },
                {
                    "source_type": "provider",
                    "label": "Provider 评阅",
                    "used": provider_result.ok,
                    "detail": provider_result.error or f"{provider_result.provider}:{provider_result.model}",
                    "latency_ms": provider_result.latency_ms,
                },
            ],
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        from app.services.memory_service import memory_service

        response.memory_summary = memory_service.record_report_judge(response)
        response.profile_updated = True
        audit_service.log(
            "report_judge",
            user_id=request.learner_id,
            entity_id=response.id,
            summary=f"报告修改训练评分：{score} 分；模式 {generation_mode}；已回灌医师画像；医生审核必需。",
            risk_level="high",
        )
        return response

    def generate_patient_card(self, request: PatientCardRequest) -> PatientCard:
        summary = safety_service.redact_sensitive_text(request.diagnosis_summary.strip())
        kb = self.card_template_knowledge_base()
        template = self._card_template(request.template_id)
        image_url = self._card_image_url(request.image_url)
        template_name = template.get("name", "科普卡片模板")
        source_trace = [
            {
                "source_type": "doctor_input",
                "label": "医生审核前摘要",
                "used": bool(summary),
                "detail": "已脱敏后用于生成患者沟通草稿；仍需医生审核。",
            },
            {
                "source_type": "card_template_kb",
                "label": template_name,
                "used": True,
                "detail": kb.get("id", "card_template_knowledge.json"),
            },
            {
                "source_type": "image",
                "label": "卡片图像",
                "used": bool(image_url),
                "detail": image_url or "未写入后端图片；本机上传仅用于浏览器预览。",
            },
        ]
        card = PatientCard(
            id=f"card_{uuid4().hex[:12]}",
            card_title="内镜检查结果说明卡（医生审核前草稿）",
            plain_language_explanation=(
                f"根据医生待审核输入，本卡片将“{summary}”转写为更容易理解的说明。"
                "它只帮助沟通检查发现，不替代医生面对面解释。"
            ),
            what_it_means=[
                "内镜描述通常反映医生在检查中看到的黏膜外观。",
                "某些表现需要结合病史、病理或复查才能判断意义。",
                "如果文字中包含不确定性，说明还需要更多信息支持。"
            ],
            what_to_watch=[
                "是否出现持续或加重的不适。",
                "医生是否建议进一步检查或复诊。",
                "报告中是否有需要带回门诊讨论的复核点。"
            ],
            follow_up_reminder="请按照医生给出的复诊或检查安排执行；如症状明显变化，请及时联系医疗机构。",
            disclaimer="本卡片为医生审核前沟通草稿；如输入尚未审核，必须先由医生确认后才能用于患者沟通。",
            template_id=request.template_id,
            visual_tone=template.get("tone", "稳健、清楚、适合打印"),
            image_url=image_url,
            review_status="doctor_review_pending",
            share_status="locked_pending_review",
            reviewer_name=None,
            review_notes=None,
            reviewed_at=None,
            review_steps=[
                {
                    "label": "摘要来自医生确认的报告或训练输入",
                    "checked": False,
                    "detail": "未确认前，卡片只能用于教学预览。",
                },
                {
                    "label": "未加入未提供的病理、治疗或疗效承诺",
                    "checked": False,
                    "detail": "高风险医学表述保持解释性和复核边界。",
                },
                {
                    "label": "患者沟通前保留免责声明和复诊提醒",
                    "checked": True,
                    "detail": "卡片始终提示不替代医生面对面解释。",
                },
            ],
            generation_mode="rule",
            source_trace=source_trace,
            knowledge_base_id=kb.get("id", "card_template_knowledge.json"),
            audit_logged=False,
            audit_log_id=None,
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        audit = audit_service.log(
            "patient_card",
            user_id="doctor_demo",
            entity_id=card.id,
            summary="生成患者科普卡片草稿；分享和打印保持锁定，等待医生审核。",
            risk_level="high",
        )
        card = card.model_copy(
            update={
                "audit_logged": True,
                "audit_log_id": audit.id,
                "source_trace": [
                    *source_trace,
                    {
                        "source_type": "audit",
                        "label": "生成审计收据",
                        "used": True,
                        "detail": f"已写入 patient_card 审计：{audit.id}",
                    },
                ],
            }
        )
        self._upsert_patient_card(card)
        return card

    def approve_patient_card(self, card_id: str, request: PatientCardApproveRequest) -> PatientCard:
        reviewer_name = request.reviewer_name.strip()
        if not reviewer_name:
            raise ValueError("reviewer_name_required")
        required_checks = ("summaryMatched", "noUnsupportedClaim", "disclaimerKept")
        if not all(bool(request.review_checks.get(item)) for item in required_checks):
            raise ValueError("review_checks_incomplete")
        cards = self._load_patient_cards()
        card_index = next((index for index, item in enumerate(cards) if item.get("id") == card_id), -1)
        if card_index < 0:
            raise KeyError(card_id)
        card = PatientCard(**cards[card_index])
        review_notes = safety_service.redact_sensitive_text(request.review_notes.strip()) if request.review_notes else None
        now = now_iso()
        approved = card.model_copy(
            update={
                "card_title": "内镜检查结果说明卡（医生已审核）",
                "plain_language_explanation": card.plain_language_explanation.replace("医生待审核输入", "医生已审核输入"),
                "review_status": "doctor_reviewed_input",
                "share_status": "reviewed_ready_to_share",
                "reviewer_name": reviewer_name,
                "review_notes": review_notes,
                "reviewed_at": now,
                "review_steps": self._approved_review_steps(request.review_checks),
            }
        )
        cards[card_index] = approved.model_dump()
        self._save_patient_cards(cards)
        audit_service.log(
            "patient_card_approve",
            user_id="doctor_demo",
            entity_id=approved.id,
            summary=f"医生审核通过科普卡片 {approved.id}；审核人 {reviewer_name}；分享和打印已解锁。",
            risk_level="high",
        )
        return approved

    def report_knowledge_base(self) -> dict:
        return read_json("report_knowledge_base.json")

    def card_template_knowledge_base(self) -> dict:
        return read_json("card_template_knowledge.json")

    def _approved_review_steps(self, review_checks: dict[str, bool]) -> list[dict[str, object]]:
        return [
            {
                "label": "摘要来自医生确认的报告或训练输入",
                "checked": bool(review_checks.get("summaryMatched", True)),
                "detail": "审核通过后，卡片可用于患者沟通前说明。",
            },
            {
                "label": "未加入未提供的病理、治疗或疗效承诺",
                "checked": bool(review_checks.get("noUnsupportedClaim", True)),
                "detail": "高风险医学表述保持解释性和复核边界。",
            },
            {
                "label": "患者沟通前保留免责声明和复诊提醒",
                "checked": bool(review_checks.get("disclaimerKept", True)),
                "detail": "卡片始终提示不替代医生面对面解释。",
            },
        ]

    def _load_patient_cards(self) -> list[dict[str, object]]:
        if not PATIENT_CARD_STORE.exists():
            return []
        with PATIENT_CARD_STORE.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, list) else []

    def _save_patient_cards(self, cards: list[dict[str, object]]) -> None:
        PATIENT_CARD_STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PATIENT_CARD_STORE.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(cards[:80], f, ensure_ascii=False, indent=2)
        tmp.replace(PATIENT_CARD_STORE)

    def _upsert_patient_card(self, card: PatientCard) -> None:
        cards = [item for item in self._load_patient_cards() if item.get("id") != card.id]
        cards.insert(0, card.model_dump())
        self._save_patient_cards(cards)

    def _card_image_url(self, image_url: str | None) -> str | None:
        if not image_url:
            return None
        cleaned = image_url.strip()
        if cleaned.startswith("blob:") or cleaned.startswith("data:") or cleaned.startswith("file:"):
            return None
        if cleaned.startswith("/assets/real_samples/") or cleaned.startswith("uploads/"):
            return cleaned
        return None

    def _split_findings(self, text: str) -> list[str]:
        separators = ["。", "；", ";", "\n"]
        chunks = [text]
        for sep in separators:
            next_chunks: list[str] = []
            for chunk in chunks:
                next_chunks.extend(chunk.split(sep))
            chunks = next_chunks
        cleaned = [chunk.strip(" ，,") for chunk in chunks if chunk.strip(" ，,")]
        return cleaned or ["未提供明确所见文本。"]

    def _draft_impression(self, findings: list[str]) -> list[str]:
        impressions: list[str] = []
        joined = "；".join(findings)
        if any(token in joined for token in ["糜烂", "充血", "红斑", "发红"]):
            impressions.append("胃黏膜炎症样/糜烂样改变，需医生结合完整检查复核。")
        if any(token in joined for token in ["息肉", "隆起"]):
            impressions.append("局部隆起/息肉样描述待医生确认部位、大小和处理意见。")
        if not impressions:
            impressions.append("已按输入所见生成结构化草稿，正式印象需医生复核。")
        return impressions

    def _exam_context(self, exam_type: str, image_name: str | None) -> dict[str, object]:
        return {
            "exam_type": exam_type,
            "patient_context_available": False,
            "procedure_context_available": False,
            "missing_context_note": (
                "仅提供单帧图片占位；患者信息、适应证、完整检查范围、操作记录、病理结果均未提供。"
                if image_name
                else "未上传图片；当前仅根据医生输入文本和模板知识库生成训练草稿。"
            ),
            "single_frame": bool(image_name),
        }

    def _image_quality(self, image_name: str | None, findings: list[str]) -> dict[str, object]:
        artifacts = ["reflection"] if image_name else ["unknown"]
        clarity = "acceptable" if image_name else "unknown"
        if any("模糊" in item or "遮挡" in item for item in findings):
            clarity = "poor"
            artifacts.append("occlusion")
        return {
            "clarity": clarity,
            "artifacts": list(dict.fromkeys(artifacts)),
            "single_frame_limitation": bool(image_name),
        }

    def _evidence_ledger(
        self,
        request: ReportDraftRequest,
        findings: list[str],
        impressions: list[str],
        sample: dict | None,
        provider_called: bool,
    ) -> list[dict[str, object]]:
        ledger = [
            {
                "evidence_id": "doctor_input_001" if request.finding_text.strip() else "kb_001",
                "source_type": "doctor_input" if request.finding_text.strip() else "template_kb",
                "source_ref": "finding_text" if request.finding_text.strip() else "report_knowledge_base.json",
                "supports": [*findings[:3], *impressions[:2]] or ["结构化报告模板训练样例"],
            }
        ]
        if sample:
            ledger.append(
                {
                    "evidence_id": "public_sample_001",
                    "source_type": "public_sample_annotation",
                    "source_ref": sample.get("id", "public_sample"),
                    "supports": [str(sample.get("question", "")), str(sample.get("answer", ""))],
                }
            )
        elif request.image_name and request.image_name.startswith("uploads/"):
            ledger.append(
                {
                    "evidence_id": "upload_001",
                    "source_type": "provider_image_observation" if provider_called else "image_preview_only",
                    "source_ref": request.image_name,
                    "supports": ["Provider 已生成视觉观察摘要"] if provider_called else ["仅保存上传图片供预览/后续人工复核；未作为图像诊断证据"],
                }
            )
        return ledger

    def _source_trace(self, request: ReportDraftRequest, sample: dict | None, provider_result) -> list[dict[str, object]]:
        trace = [
            {
                "source_type": "doctor_input" if request.finding_text.strip() else "template_kb",
                "label": "医生输入所见" if request.finding_text.strip() else "报告知识库模板",
                "used": True,
                "detail": "已脱敏后进入结构化草稿。" if request.finding_text.strip() else "未输入所见，使用模板样例。",
            },
            {
                "source_type": "template_kb",
                "label": "报告模板知识库",
                "used": True,
                "detail": "report_knowledge_base.json",
            },
            {
                "source_type": "provider",
                "label": "视觉/语言 Provider",
                "used": bool(provider_result.ok),
                "detail": provider_result.error or f"{provider_result.provider}:{provider_result.model}",
                "latency_ms": provider_result.latency_ms,
            },
        ]
        if sample:
            trace.insert(
                1,
                {
                    "source_type": "public_sample_annotation",
                    "label": "公开样例标注",
                    "used": True,
                    "detail": f"{sample.get('source_dataset')} / {sample.get('id')}",
                },
            )
        elif request.image_name:
            trace.insert(
                1,
                {
                    "source_type": "uploaded_image" if request.image_name.startswith("uploads/") else "image_reference",
                    "label": "图片输入",
                    "used": bool(provider_result.ok),
                    "detail": request.image_name,
                },
            )
        return trace

    def _sample_from_image_name(self, image_name: str | None) -> dict | None:
        if not image_name:
            return None
        sample_id = image_name.removeprefix("public_")
        for sample in read_json("real_sample_knowledge.json"):
            if sample.get("id") == sample_id:
                return sample
        return None

    def _provider_image_path(self, image_name: str | None, sample: dict | None) -> str | None:
        if sample:
            return str(sample.get("image_url") or "")
        if image_name and image_name.startswith("uploads/"):
            return image_name
        if image_name and image_name.startswith("/assets/real_samples/"):
            return image_name
        return None

    def _provider_observation(self, request: ReportDraftRequest, finding_text: str, sample: dict | None, image_path: str | None):
        sample_text = ""
        if sample:
            sample_text = (
                f"\n公开样例问题：{sample.get('question', '')}"
                "\n公开样例参考标注不会发送给 Provider，只保留在来源台账中供医生复核。"
            )
        return llm_provider.chat(
            system_prompt=(
                "你是消化内镜医师培训平台中的报告辅助 Agent。"
                "只输出医生审核前的教学观察摘要，不给最终诊断、不建议治疗、不编造病史、病理或完整检查范围。"
                "若证据不足，请明确写出缺失上下文。"
            ),
            user_prompt=(
                f"检查类型：{request.exam_type}\n"
                f"医生输入所见：{finding_text or '未提供'}"
                f"{sample_text}\n"
                "请用中文输出 3-5 条谨慎的视觉/文本观察线索，供结构化报告草稿参考。"
            ),
            image_path=image_path,
            temperature=0.1,
            max_tokens=520,
            **self._provider_kwargs(request),
        )

    def _provider_report_judge(self, request: ReportJudgeRequest, original: str, revised: str):
        return llm_provider.chat(
            system_prompt=(
                "你是消化内镜医师培训平台中的报告修改评阅 Agent。"
                "只评价训练文本的表达质量、安全边界和证据充分性，不给最终诊断或治疗建议。"
                "请用中文输出：1) 2条优点；2) 2-3条风险或遗漏；3) 一句建议改写。"
            ),
            user_prompt=(
                f"原报告：{original or '未提供'}\n"
                f"医师修改稿：{revised or '未提供'}\n"
                "请严格围绕所见与诊断区分、不确定性表达、单帧证据边界和医生审核要求进行评阅。"
            ),
            temperature=0.1,
            max_tokens=520,
            **self._provider_kwargs(request),
        )

    def _recommended_report_drills(self, rubric_scores: dict[str, int]) -> list[dict[str, object]]:
        drill_map = {
            "部位描述": {
                "label": "部位与范围定位专项",
                "href": "/training?source=report_judge&drill=location_scope&question_class=病变属性",
                "reason": "部位、范围、数量表达不足时，先回到病变属性/部位定位题练定位。",
                "drill_id": "location_scope",
            },
            "所见与诊断区分": {
                "label": "报告安全专项",
                "href": "/training?source=report_judge&drill=report_safety&question_class=报告纠错",
                "reason": "把观察性所见和诊断性结论拆开，减少越界表达。",
                "drill_id": "report_safety",
            },
            "不确定性表达": {
                "label": "证据不足识别专项",
                "href": "/training?source=report_judge&drill=evidence_boundary&question_class=错误前提",
                "reason": "训练在证据不足时主动写出缺失上下文和复核要求。",
                "drill_id": "evidence_boundary",
            },
            "安全边界": {
                "label": "错误前提挑战",
                "href": "/training?source=report_judge&drill=false_premise&question_class=错误前提",
                "reason": "识别“确诊、必须、立即”等高风险前提，练习降级表达。",
                "drill_id": "false_premise",
            },
        }
        weak = [
            {**drill_map[name], "rubric": name, "score": score}
            for name, score in rubric_scores.items()
            if score < 20 and name in drill_map
        ]
        if weak:
            return weak[:3]
        return [
            {
                "label": "报告表达进阶",
                "href": "/training?source=report_judge&drill=report_safety&question_class=报告纠错",
                "reason": "本次修改已达标，继续用报告纠错题巩固证据边界。",
                "rubric": "综合表达",
                "score": min(rubric_scores.values()) if rubric_scores else 0,
                "drill_id": "report_safety",
            }
        ]

    def _provider_kwargs(self, request: ReportDraftRequest | ReportJudgeRequest) -> dict[str, object]:
        api_base = self._request_provider_value(request.api_base)
        api_key = request.api_key.strip() if request.api_key and request.api_key.strip() else None
        model = request.model.strip() if request.model and request.model.strip() else None
        provider = request.provider_name.strip() if request.provider_name and request.provider_name.strip() else None
        use_request_provider = bool(api_base or api_key)
        return {
            "base_url": api_base if use_request_provider else None,
            "api_key": api_key,
            "model": model if use_request_provider else None,
            "provider": (provider or "openai_compatible") if use_request_provider else None,
        }

    def _request_provider_value(self, value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip().rstrip("/")
        if not cleaned or "api.example.com" in cleaned:
            return None
        return cleaned

    def _hallucination_audit(self, statements: list[str], *, single_frame: bool) -> dict[str, object]:
        text = "；".join(statements)
        unsupported: list[str] = []
        rewrites: list[str] = []
        if single_frame:
            for pattern in UNSUPPORTED_SINGLE_FRAME_PATTERNS:
                if re.search(pattern, text):
                    unsupported.append(pattern)
                    rewrites.append("删除或改写单帧图像无法支持的完整检查声明。")
        high_risk = [term for term in HIGH_RISK_TERMS if self._is_asserted_risk(text, term)]
        if high_risk:
            rewrites.append("高风险词必须有明确上下文或医师确认；否则降级为“考虑/待排/需复核”。")
        return {
            "audit_passed": not unsupported,
            "unsupported_claims": unsupported,
            "high_risk_flags": high_risk,
            "required_rewrites": list(dict.fromkeys(rewrites)),
            "evidence_policy": "image_supported/context_supported/derived_cautious only",
        }

    def _is_asserted_risk(self, text: str, term: str) -> bool:
        cursor = 0
        while True:
            index = text.find(term, cursor)
            if index == -1:
                return False
            prefix = text[max(0, index - 8):index]
            if not any(token in prefix for token in ["未见", "无", "未发现", "未明确"]):
                return True
            cursor = index + len(term)

    def _review_tasks(self, audit: dict[str, object], image_name: str | None) -> list[str]:
        tasks = [
            "确认检查类型、病灶解剖部位和完整检查范围。",
            "确认病灶数量、大小、形态分型和是否存在多视角证据。",
            "确认是否已有活检、切除或病理结果；未提供时不得写入正式报告。",
            "签发前逐条核对证据台账与报告声明。",
        ]
        if image_name:
            tasks.insert(0, "当前仅为单帧图片占位，不能写全胃/全结肠阴性结论。")
        if audit.get("high_risk_flags"):
            tasks.insert(0, "高风险诊断或操作词已标记，需医师确认或降级表达。")
        if audit.get("unsupported_claims"):
            tasks.insert(0, "存在单帧无法支持的声明，需删除或改写。")
        return tasks

    def _default_finding(self, kb: dict) -> str:
        samples = kb.get("sample_findings", [])
        return samples[0] if samples else "胃窦黏膜局部发红，性质需结合完整检查复核。"

    def _template_name(self, kb: dict, exam_type: str) -> str:
        templates = kb.get("templates", [])
        if exam_type == "colonoscopy":
            for template in templates:
                if "肠镜" in template.get("name", ""):
                    return template["name"]
        for template in templates:
            if "胃镜" in template.get("name", ""):
                return template["name"]
        return "结构化训练模板"

    def _suggest_revision(self, revised: str) -> str:
        if revised:
            return f"{revised} 建议由医生结合完整检查、病史及必要病理结果复核后形成正式报告。"
        return "图像/所见提示局部黏膜异常表现，性质与范围需结合完整检查和医生复核。"

    def _card_template(self, template_id: str) -> dict:
        kb = self.card_template_knowledge_base()
        for template in kb.get("templates", []):
            if template.get("id") == template_id:
                return template
        return kb.get("templates", [{}])[0]


report_service = ReportService()
