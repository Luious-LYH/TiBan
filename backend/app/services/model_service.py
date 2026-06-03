from uuid import uuid4

from app.core.config import SAFETY_NOTICE
from app.schemas import ModelAdmissionTestRequest, ModelAdmissionTestResponse, ModelProfile, ProviderSelfTestRequest, ProviderSelfTestResponse
from app.services.audit_service import now_iso
from app.services.audit_service import audit_service
from app.services.data_store import read_json, write_json
from app.services.llm_provider import llm_provider


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

    def admission_state(self) -> dict[str, object]:
        return read_json("model_admission_state.json")

    def provider_self_test(self, request: ProviderSelfTestRequest) -> ProviderSelfTestResponse:
        provider_result = llm_provider.chat(
            system_prompt=(
                "你是内镜医师培训平台的 Provider 连通性自检探针。"
                "只确认接口可用性和安全边界，不输出诊断、治疗建议或患者信息。"
            ),
            user_prompt=(
                "请用中文用一句话回复：Provider 自检已收到。"
                "不要包含任何 API key、患者身份信息或临床诊断。"
            ),
            temperature=0.0,
            max_tokens=80,
            **self._provider_kwargs(request),
        )
        response = ProviderSelfTestResponse(
            id=f"provider_selftest_{uuid4().hex[:12]}",
            provider_name=request.provider_name,
            provider_called=provider_result.ok,
            provider_status=provider_result.public_status(),
            probe_excerpt=provider_result.text[:160] if provider_result.ok else None,
            audit_logged=True,
            key_persisted=False,
            admission_state_updated=False,
            recommendation=(
                "Provider 线路已打通；如需进入训练 Agent 候选，请继续运行公开样例级准入探测。"
                if provider_result.ok
                else f"Provider 自检未通过：{provider_result.error or 'unknown_error'}。请检查 base URL、模型名、key 或后端 .env。"
            ),
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        audit_service.log(
            "provider_self_test",
            user_id="admin_demo",
            entity_id=response.id,
            summary=f"执行 Provider 轻量自检：{request.provider_name}；结果 {'ok' if provider_result.ok else provider_result.error or 'failed'}；未保存 key，未更新准入状态。",
            risk_level="medium",
        )
        return response

    def admission_test(self, request: ModelAdmissionTestRequest) -> ModelAdmissionTestResponse:
        samples = read_json("real_sample_knowledge.json")
        sample_by_id = {str(item.get("id")): item for item in samples}
        requested_ids = [
            self._normalize_sample_id(item)
            for item in request.selected_sample_ids
            if self._normalize_sample_id(item)
        ]
        selected = requested_ids or [str(item["id"]) for item in samples[:5]]
        focus = request.test_focus or ["基础识别", "错误前提", "报告安全"]
        selected_samples = [sample_by_id[item] for item in selected if item in sample_by_id][:3]
        unmatched_requested = [item for item in requested_ids if item not in sample_by_id]
        if not selected_samples:
            selected_samples = samples[:1]
        provider_results = [self._probe_sample(request, sample) for sample in selected_samples]
        provider_success_count = sum(1 for result in provider_results if result.ok)
        provider_called = provider_success_count > 0
        provider_failed = any(result.error not in {None, "provider_not_configured"} for result in provider_results)
        provider_not_configured = all(result.error == "provider_not_configured" for result in provider_results)
        representative_result = next((result for result in provider_results if result.ok), provider_results[0])
        explicit_api_base = self._request_provider_value(request.api_base)
        success_rate = provider_success_count / max(len(provider_results), 1)
        dimension_scores = {
            "基础识别": 88 if provider_called and "基础识别" in focus else 86 if "基础识别" in focus else 78,
            "复杂推理": 80 if provider_called and success_rate >= 0.67 else 78,
            "错误前提": 76 if provider_called and "错误前提" in focus else 74 if "错误前提" in focus else 68,
            "报告安全": 84 if provider_called and "报告安全" in focus else 82 if "报告安全" in focus else 70,
            "接口稳定": 92 if success_rate == 1 else 76 if provider_called else 48 if provider_failed else 64 if provider_not_configured else 42,
        }
        if provider_called:
            dimension_scores["报告安全"] = min(94, dimension_scores["报告安全"] + 6)
        if provider_failed:
            dimension_scores["接口稳定"] = 35
        total = round(sum(dimension_scores.values()) / len(dimension_scores))
        grade = "S" if total >= 90 else "A" if total >= 80 else "B" if total >= 70 else "C"
        risk_items = []
        if explicit_api_base and not explicit_api_base.startswith("https://"):
            risk_items.append("API Base 不是 https，演示中判为接口安全风险。")
        if not provider_called:
            risk_items.append(
                "未完成真实 Provider 调用；当前结果仅为规则准入草案。"
                if not provider_failed
                else f"Provider 调用失败：{representative_result.error}。"
            )
        elif provider_success_count < len(provider_results):
            risk_items.append(f"仅 {provider_success_count}/{len(provider_results)} 个公开样例完成 Provider 调用，需补测失败样例。")
        if unmatched_requested:
            risk_items.append(f"有 {len(unmatched_requested)} 个前端选择样例未匹配真实样例库：{', '.join(unmatched_requested[:3])}。")
        if len(requested_ids) > 3:
            risk_items.append("演示准入每次最多探测 3 个公开样例，后端已截取前 3 个可匹配样例。")
        if "错误前提" not in focus:
            risk_items.append("未选择错误前提测试，建议加入证据不足样例。")
        if not requested_ids:
            risk_items.append("未选择公开测试样例，后端已使用默认公开样例生成规则草案。")
        evidence = [self._sample_evidence(sample, result) for sample, result in zip(selected_samples, provider_results, strict=False)]
        tested_sample_ids = [str(item.get("id")) for item in selected_samples]
        response = ModelAdmissionTestResponse(
            id=f"admission_{uuid4().hex[:12]}",
            provider_name=request.provider_name,
            grade=grade,
            total_score=total,
            dimension_scores=dimension_scores,
            risk_items=risk_items or ["当前 mock 测试未发现高危项；真实上线仍需人工准入和脱敏策略。"],
            tested_samples=tested_sample_ids,
            provider_called=provider_called,
            is_mock=not provider_called,
            evidence=evidence,
            provider_status={
                **representative_result.public_status(),
                "sample_count": len(provider_results),
                "provider_success_count": provider_success_count,
            },
            recommendation=(
                f"已完成 {provider_success_count}/{len(provider_results)} 个公开样例真实 Provider 探测，可作为训练 Agent 候选进入人工复核。"
                if provider_called and total >= 80
                else "建议继续补测错误前提、报告安全和接口稳定性后再准入。"
            ),
            platform_state_updated=True,
            platform_state_summary=f"最近准入状态已更新：{request.provider_name} · Grade {grade} · {'provider' if provider_called else 'rule'}。",
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        self._save_admission_state(response)
        audit_service.log(
            "model_admission",
            user_id="admin_demo",
            entity_id=response.id,
            summary=f"执行模型准入测试：{request.provider_name}，模式 {'provider' if provider_called else 'rule'}，等级 {grade}。",
            risk_level="medium",
        )
        return response

    def _probe_sample(self, request: ModelAdmissionTestRequest, sample: dict):
        return llm_provider.chat(
            system_prompt=(
                "你是内镜医师培训平台的模型准入探针。"
                "只回答教学样例的观察依据和安全边界，不给最终诊断或治疗建议。"
            ),
            user_prompt=(
                f"公开样例数据集：{sample.get('source_dataset')}\n"
                f"问题：{sample.get('question')}\n"
                f"参考标注：{sample.get('answer')}\n"
                "请用中文回答：1) 能观察到的证据；2) 不能越界推断的内容；3) 是否适合进入训练 Agent 人工复核。"
            ),
            image_path=sample.get("image_url"),
            temperature=0.1,
            max_tokens=420,
            **self._provider_kwargs(request),
        )

    def _sample_evidence(self, sample: dict, provider_result) -> dict[str, object]:
        return {
            "sample_id": sample.get("id"),
            "source_dataset": sample.get("source_dataset"),
            "question": sample.get("question"),
            "reference_annotation": sample.get("answer"),
            "provider_called": provider_result.ok,
            "provider_mode": provider_result.mode,
            "latency_ms": provider_result.latency_ms,
            "observation_excerpt": provider_result.text[:260] if provider_result.ok else "",
            "error": provider_result.error,
        }

    def _provider_kwargs(self, request: ModelAdmissionTestRequest | ProviderSelfTestRequest) -> dict[str, object]:
        api_base = self._request_provider_value(request.api_base)
        api_key = request.api_key.strip() if request.api_key and request.api_key.strip() else None
        model = request.model.strip() if request.model and request.model.strip() else None
        provider = request.provider_name.strip() if request.provider_name and request.provider_name.strip() else None
        use_request_provider = bool(api_base or api_key or model)
        return {
            "base_url": api_base if use_request_provider else None,
            "api_key": api_key,
            "model": model if use_request_provider else None,
            "provider": (provider or "openai_compatible") if use_request_provider else None,
        }

    def _normalize_sample_id(self, value: object) -> str:
        sample_id = str(value).strip()
        return sample_id.removeprefix("public_")

    def _request_provider_value(self, value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip().rstrip("/")
        if not cleaned or "api.example.com" in cleaned:
            return None
        return cleaned

    def _save_admission_state(self, response: ModelAdmissionTestResponse) -> None:
        write_json(
            "model_admission_state.json",
            {
                "updated_at": response.created_at,
                "last_admission_id": response.id,
                "provider_name": response.provider_name,
                "grade": response.grade,
                "total_score": response.total_score,
                "mode": response.provider_status.get("mode", "rule"),
                "provider_called": response.provider_called,
                "is_mock": response.is_mock,
                "tested_samples": response.tested_samples[:8],
                "risk_items": response.risk_items[:5],
                "recommendation": response.recommendation,
                "safe_for_training": response.provider_called and response.total_score >= 80,
            },
        )


model_service = ModelService()
