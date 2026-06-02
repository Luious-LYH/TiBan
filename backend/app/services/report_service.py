from uuid import uuid4

from app.core.config import SAFETY_NOTICE
from app.schemas import (
    PatientCard,
    PatientCardRequest,
    ReportDraft,
    ReportDraftRequest,
    ReportJudgeRequest,
    ReportJudgeResponse,
)
from app.services.audit_service import audit_service, now_iso
from app.services.data_store import read_json
from app.services.safety_service import safety_service


class ReportService:
    def generate_report_draft(self, request: ReportDraftRequest) -> ReportDraft:
        raw_text = request.finding_text.strip()
        kb = self.report_knowledge_base()
        text = safety_service.redact_sensitive_text(raw_text)
        findings = self._split_findings(text or self._default_finding(kb))
        review = safety_service.review_text(raw_text)
        uncertainty_notes = [
            "草稿优先整理医生输入；未上传图片时，仅基于模板知识库生成训练样例。",
            "如需形成正式报告，应由内镜医生结合完整图像、病史和必要检查复核。",
        ]
        if request.image_name:
            uncertainty_notes.insert(0, f"已接收图片占位：{request.image_name}；当前 demo 不执行真实图像诊断。")
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
            template_name=request.template_name or self._template_name(kb, request.exam_type),
            evidence_source=[
                "医生输入所见" if raw_text else "报告知识库模板",
                "图片上传占位" if request.image_name else "未上传图片",
                "report_knowledge_base.json",
            ],
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

    def judge_report_revision(self, request: ReportJudgeRequest) -> ReportJudgeResponse:
        revised = safety_service.redact_sensitive_text(request.revised_report.strip())
        original = request.original_report.strip()
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
        response = ReportJudgeResponse(
            id=f"judge_{uuid4().hex[:12]}",
            score=score,
            strengths=strengths,
            issues=issues or ["未发现明显越界表达，仍需医生最终审核。"],
            suggested_revision=self._suggest_revision(revised),
            rubric_scores=rubric_scores,
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        audit_service.log(
            "report_judge",
            user_id=request.learner_id,
            entity_id=response.id,
            summary=f"报告修改训练评分：{score} 分；医生审核必需。",
            risk_level="high",
        )
        return response

    def generate_patient_card(self, request: PatientCardRequest) -> PatientCard:
        summary = safety_service.redact_sensitive_text(request.diagnosis_summary.strip())
        template = self._card_template(request.template_id)
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
            template_id=request.template_id,
            visual_tone=template.get("tone", "稳健、清楚、适合打印"),
            image_url=request.image_url,
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

    def report_knowledge_base(self) -> dict:
        return read_json("report_knowledge_base.json")

    def card_template_knowledge_base(self) -> dict:
        return read_json("card_template_knowledge.json")

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
