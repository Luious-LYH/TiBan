from uuid import uuid4

from app.core.config import SAFETY_NOTICE
from app.schemas import ModelAdmissionTestRequest, ModelAdmissionTestResponse, ModelProfile
from app.services.audit_service import now_iso
from app.services.audit_service import audit_service
from app.services.data_store import read_json, write_json


class ModelService:
    def list_models(self) -> list[ModelProfile]:
        return [ModelProfile(**item) for item in read_json("models.json")]

    def select_model(self, model_id: str) -> ModelProfile:
        models = read_json("models.json")
        selected: dict | None = None
        for model in models:
            model["is_active"] = model["id"] == model_id
            if model["is_active"]:
                selected = model
        if selected is None:
            raise KeyError(f"Model not found: {model_id}")
        write_json("models.json", models)
        audit_service.log(
            "model_select",
            user_id="admin_demo",
            entity_id=model_id,
            summary=f"选择模型：{selected['name']}。能力看板仍为 mock/预留。",
            risk_level="medium",
        )
        return ModelProfile(**selected)

    def active_model(self) -> ModelProfile:
        for model in self.list_models():
            if model.is_active:
                return model
        return self.list_models()[0]

    def admission_test(self, request: ModelAdmissionTestRequest) -> ModelAdmissionTestResponse:
        samples = read_json("real_sample_knowledge.json")
        selected = request.selected_sample_ids or [item["id"] for item in samples[:5]]
        focus = request.test_focus or ["基础识别", "错误前提", "报告安全"]
        dimension_scores = {
            "基础识别": 86 if "基础识别" in focus else 78,
            "复杂推理": 78,
            "错误前提": 74 if "错误前提" in focus else 68,
            "报告安全": 82 if "报告安全" in focus else 70,
            "接口稳定": 88 if request.api_base.startswith("https://") else 62,
        }
        total = round(sum(dimension_scores.values()) / len(dimension_scores))
        grade = "S" if total >= 90 else "A" if total >= 80 else "B" if total >= 70 else "C"
        risk_items = []
        if not request.api_base.startswith("https://"):
            risk_items.append("API Base 不是 https，演示中判为接口安全风险。")
        if "错误前提" not in focus:
            risk_items.append("未选择错误前提测试，建议加入证据不足样例。")
        if not selected:
            risk_items.append("未选择公开测试样例，无法形成样例级追溯。")
        response = ModelAdmissionTestResponse(
            id=f"admission_{uuid4().hex[:12]}",
            provider_name=request.provider_name,
            grade=grade,
            total_score=total,
            dimension_scores=dimension_scores,
            risk_items=risk_items or ["当前 mock 测试未发现高危项；真实上线仍需人工准入和脱敏策略。"],
            tested_samples=selected,
            recommendation="可作为训练 Agent 候选模型进入人工复核阶段。" if total >= 80 else "建议继续补测错误前提、报告安全和接口稳定性后再准入。",
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        audit_service.log(
            "model_select",
            user_id="admin_demo",
            entity_id=response.id,
            summary=f"执行模型准入 mock 测试：{request.provider_name}，等级 {grade}。",
            risk_level="medium",
        )
        return response


model_service = ModelService()
