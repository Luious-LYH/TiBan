from app.schemas import ModelProfile
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


model_service = ModelService()

