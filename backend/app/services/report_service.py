from uuid import uuid4

from app.core.config import SAFETY_NOTICE
from app.schemas import PatientCard, PatientCardRequest, ReportDraft, ReportDraftRequest
from app.services.audit_service import audit_service, now_iso
from app.services.safety_service import safety_service


class ReportService:
    def generate_report_draft(self, request: ReportDraftRequest) -> ReportDraft:
        raw_text = request.finding_text.strip()
        text = safety_service.redact_sensitive_text(raw_text)
        findings = self._split_findings(text)
        review = safety_service.review_text(raw_text)
        uncertainty_notes = [
            "草稿仅整理医生输入的所见文本，不自动补充未提供的病灶、部位或病因。",
            "如需形成正式报告，应由内镜医生结合完整图像、病史和必要检查复核。",
        ]
        if not review["passed"]:
            uncertainty_notes.insert(0, "输入中可能包含敏感或越界表述，已在草稿回显中脱敏或提示复核。")
        review_points = [
            "确认部位、范围、数量和图片证据是否一致。",
            "检查是否存在“明确诊断”“必须治疗”等过强表述。",
            "必要时补充活检、病理或其他检查结果。",
        ]
        draft = ReportDraft(
            id=f"report_{uuid4().hex[:12]}",
            input_finding_text=text,
            exam_type=request.exam_type,
            structured_findings=findings,
            draft_impression=self._draft_impression(findings),
            review_points=review_points,
            uncertainty_notes=uncertainty_notes,
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        audit_service.log(
            "report_draft",
            user_id="doctor_demo",
            entity_id=draft.id,
            summary="生成结构化报告草稿；医生审核必需。" if review["passed"] else "报告草稿触发安全审查提醒。",
            risk_level="high",
        )
        return draft

    def generate_patient_card(self, request: PatientCardRequest) -> PatientCard:
        summary = safety_service.redact_sensitive_text(request.diagnosis_summary.strip())
        review_status = "doctor_reviewed_input" if request.reviewed_by_doctor else "doctor_review_pending"
        review_phrase = "医生已审核输入" if request.reviewed_by_doctor else "医生待审核输入"
        card = PatientCard(
            id=f"card_{uuid4().hex[:12]}",
            card_title="内镜检查结果说明卡（医生审核前草稿）",
            plain_language_explanation=(
                f"根据{review_phrase}，本卡片将“{summary}”转写为更容易理解的说明。"
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
            review_status=review_status,
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        audit_service.log(
            "patient_card",
            user_id="doctor_demo",
            entity_id=card.id,
            summary="生成患者科普卡片草稿并附医生审核提示。",
            risk_level="high",
        )
        return card

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


report_service = ReportService()
