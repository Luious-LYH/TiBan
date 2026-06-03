import re
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
            if model["id"] == model_id:
                selected = model
        if selected is None:
            raise KeyError(f"Model not found: {model_id}")
        self._assert_model_selectable(selected)
        for model in models:
            model["is_active"] = model["id"] == model_id
        write_json("models.json", models)
        audit_service.log(
            "model_select",
            user_id="admin_demo",
            entity_id=model_id,
            summary=f"选择待人工复核候选：{selected['name']}。已通过最近 Provider 准入闸门，仍需医生/管理员复核。",
            risk_level="medium",
        )
        return ModelProfile(**selected)

    def _assert_model_selectable(self, selected: dict) -> None:
        admission_state = self.admission_state()
        aligned_count = int(admission_state.get("reference_aligned_count", 0) or 0)
        if selected.get("provider_type") == "mock":
            raise ValueError("Mock 模型只能作为能力看板展示，不能写入待人工复核候选。")
        if not admission_state.get("provider_called"):
            raise ValueError("尚未完成真实 Provider blind probe，不能切换候选模型。")
        if aligned_count <= 0:
            raise ValueError("最近准入摘要缺少公开标注对齐证据，不能切换候选模型。")
        if not admission_state.get("safe_for_training"):
            raise ValueError("最近准入摘要尚未达到安全阈值，不能切换候选模型。")

    def active_model(self) -> ModelProfile:
        for model in self.list_models():
            if model.is_active:
                return model
        return self.list_models()[0]

    def admission_state(self) -> dict[str, object]:
        return read_json("model_admission_state.json")

    def provider_status(self) -> dict[str, object]:
        return self._public_provider_status(llm_provider.status())

    def provider_diagnostics(self) -> dict[str, object]:
        provider_status = llm_provider.status()
        admission_state = self.admission_state()
        audit_logs = read_json("audit_logs.json")
        self_tests = [item for item in audit_logs if item.get("event_type") == "provider_self_test"]
        admissions = [item for item in audit_logs if item.get("event_type") == "model_admission"]
        samples = read_json("real_sample_knowledge.json")
        configured = bool(provider_status.get("configured"))
        ready_level = "provider_ready" if configured else "rule_mode"
        if configured and not self_tests:
            ready_level = "provider_configured_not_verified"
        if configured and self_tests and not admission_state.get("provider_called"):
            ready_level = "self_test_only"
        missing: list[str] = []
        if not provider_status.get("base_url_configured"):
            missing.append("LLM_BASE_URL")
        if not provider_status.get("api_key_configured"):
            missing.append("LLM_API_KEY")
        if provider_status.get("provider") == "mock":
            missing.append("LLM_PROVIDER")
        if not samples:
            missing.append("real_sample_knowledge.json")
        blocking_reason = (
            "Provider 已配置，可运行文本/视觉自检和样例级准入探测。"
            if configured
            else f"当前缺少 {', '.join(missing) if missing else '有效 Provider 配置'}；平台会明确保持 rule 模式。"
        )
        return {
            "ready_level": ready_level,
            "provider_configured": configured,
            "provider_mode": provider_status.get("mode", "rule"),
            "provider": self._public_provider_label(provider_status.get("provider", "mock"), "mock"),
            "model": self._public_model_label(provider_status.get("model", "unconfigured"), "unconfigured"),
            "base_url_configured": bool(provider_status.get("base_url_configured")),
            "api_key_configured": bool(provider_status.get("api_key_configured")),
            "missing": missing,
            "public_sample_count": len(samples),
            "latest_self_test": self._latest_audit_summary(self_tests),
            "latest_admission": self._latest_audit_summary(admissions),
            "admission_state": {
                "provider_name": admission_state.get("provider_name", "未记录"),
                "grade": admission_state.get("grade", "NA"),
                "total_score": admission_state.get("total_score", 0),
                "provider_called": bool(admission_state.get("provider_called")),
                "safe_for_training": bool(admission_state.get("safe_for_training")),
                "recommendation": admission_state.get("recommendation", "尚未形成准入建议。"),
            },
            "blocking_reason": blocking_reason,
            "next_actions": [
                {
                    "label": "配置后端 .env",
                    "detail": "设置 LLM_PROVIDER、LLM_BASE_URL、LLM_API_KEY 和 LLM_MODEL；不要提交 .env。",
                    "href": "/models",
                    "done": configured,
                },
                {
                    "label": "运行 Provider 自检",
                    "detail": "先做文本轻量自检，再做视觉通道自检；自检不更新准入状态。",
                    "href": "/models",
                    "done": bool(self_tests),
                },
                {
                    "label": "运行公开样例准入",
                    "detail": "使用最多 3 个公开样例做 blind probe；Provider 不接收参考答案。",
                    "href": "/models",
                    "done": bool(admission_state.get("provider_called")),
                },
                {
                    "label": "查看审计日志",
                    "detail": "确认 provider_self_test 与 model_admission 是否有后端审计 ID。",
                    "href": "/audit",
                    "done": bool(self_tests or admissions),
                },
            ],
            "privacy_notice": "Provider 联调状态检查只返回配置布尔值、模式、审计摘要和下一步动作；不返回 API key、API base 明文或完整模型回复。",
            "safety_notice": SAFETY_NOTICE,
            "created_at": now_iso(),
        }

    def _latest_audit_summary(self, logs: list[dict]) -> dict[str, object] | None:
        if not logs:
            return None
        latest = logs[0]
        return {
            "id": latest.get("id"),
            "event_type": latest.get("event_type"),
            "summary": latest.get("summary"),
            "risk_level": latest.get("risk_level"),
            "created_at": latest.get("created_at"),
        }

    def provider_self_test(self, request: ProviderSelfTestRequest) -> ProviderSelfTestResponse:
        visual_sample = self._self_test_visual_sample(request) if request.include_image else None
        visual_probe = request.include_image
        public_provider_name = self._public_provider_label(request.provider_name)
        provider_result = llm_provider.chat(
            system_prompt=(
                "你是内镜医师培训平台的 Provider 连通性自检探针。"
                "只确认接口可用性和安全边界，不输出诊断、治疗建议或患者信息。"
            ),
            user_prompt=self._self_test_prompt(visual_sample, visual_probe),
            image_path=visual_sample.get("image_url") if visual_sample else None,
            temperature=0.0,
            max_tokens=140 if visual_probe else 80,
            **self._provider_kwargs(request),
        )
        provider_status = self._public_provider_status(provider_result.public_status())
        image_attached = bool(provider_status.get("image_attached"))
        public_error = self._provider_error_code(provider_result.error)
        recommendation = self._self_test_recommendation(public_error, provider_result.ok, image_attached, visual_probe)
        response = ProviderSelfTestResponse(
            id=f"provider_selftest_{uuid4().hex[:12]}",
            provider_name=public_provider_name,
            provider_called=provider_result.ok,
            provider_status=provider_status,
            probe_excerpt=provider_result.text[:160] if provider_result.ok else None,
            image_attached=image_attached,
            image_sample_id=str(visual_sample.get("id")) if visual_sample else None,
            image_source_dataset=str(visual_sample.get("source_dataset")) if visual_sample else None,
            visual_probe=visual_probe,
            audit_logged=True,
            key_persisted=False,
            admission_state_updated=False,
            recommendation=recommendation,
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        test_label = "视觉通道自检" if visual_probe else "文本轻量自检"
        audit = audit_service.log(
            "provider_self_test",
            user_id="admin_demo",
            entity_id=response.id,
            summary=(
                f"执行 Provider {test_label}：{public_provider_name}；"
                f"图片附加 {'yes' if image_attached else 'no'}；"
                f"结果 {'ok' if provider_result.ok else public_error or 'failed'}；"
                "未保存 key/base/完整回复，未更新准入状态。"
            ),
            risk_level="medium",
        )
        return response.model_copy(update={
            "audit_log_id": audit.id,
            "self_test_receipt": self._provider_self_test_receipt(request, response, provider_result, visual_sample, audit.id),
        })

    def _self_test_prompt(self, visual_sample: dict | None, visual_probe: bool) -> str:
        if not visual_probe:
            return (
                "请用中文用一句话回复：Provider 自检已收到。"
                "不要包含任何 API key、患者身份信息或临床诊断。"
            )
        if not visual_sample:
            return (
                "这是 Provider 视觉通道自检的资源异常保护提示。"
                "后端未匹配到公开样例图片，请只用一句中文确认收到自检请求。"
                "不要输出诊断结论、治疗建议、API key 或患者身份信息。"
            )
        return (
            "这是 Provider 视觉通道自检，不是模型准入评分或临床诊断。"
            f"公开样例数据集：{visual_sample.get('source_dataset')}。\n"
            f"公开样例问题：{visual_sample.get('question')}。\n"
            "请只用一句中文确认你已收到图片和问题，并说明仍需医生复核。"
            "不要输出参考答案、诊断结论、治疗建议、API key 或患者身份信息。"
        )

    def _self_test_visual_sample(self, request: ProviderSelfTestRequest) -> dict | None:
        samples = read_json("real_sample_knowledge.json")
        sample_by_id = {str(item.get("id")): item for item in samples if item.get("image_url")}
        requested_id = self._normalize_sample_id(request.sample_id) if request.sample_id else ""
        if requested_id and requested_id in sample_by_id:
            return sample_by_id[requested_id]
        return next((item for item in samples if item.get("image_url")), None)

    def _self_test_recommendation(self, error: str | None, ok: bool, image_attached: bool, visual_prompt: bool) -> str:
        if visual_prompt and image_attached and ok:
            return "Provider 视觉通道已打通，后端已将公开样例图片随请求发送；如需进入训练 Agent 候选，请继续运行公开样例级准入探测。"
        if visual_prompt and image_attached:
            return f"后端已构造并附加公开样例图片，但 Provider 自检未通过：{error or 'unknown_error'}。请检查 base URL、模型名、key 或后端 .env。"
        if visual_prompt:
            return f"视觉自检未能附加公开样例图片，且 Provider 自检未通过：{error or 'unknown_error'}。请检查样例资源路径和 Provider 配置。"
        if ok:
            return "Provider 文本通道已打通；如需验证多模态链路，可继续运行视觉通道自检或公开样例级准入探测。"
        return f"Provider 文本自检未通过：{error or 'unknown_error'}。请检查 base URL、模型名、key 或后端 .env。"

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
        public_provider_name = self._public_provider_label(request.provider_name)
        provider_success_count = sum(1 for result in provider_results if result.ok)
        provider_called = provider_success_count > 0
        provider_failed = any(result.error not in {None, "provider_not_configured"} for result in provider_results)
        provider_not_configured = all(result.error == "provider_not_configured" for result in provider_results)
        representative_result = next((result for result in provider_results if result.ok), provider_results[0])
        explicit_api_base = self._request_provider_value(request.api_base)
        evidence = [self._sample_evidence(sample, result) for sample, result in zip(selected_samples, provider_results, strict=False)]
        aligned_count = sum(1 for item in evidence if item.get("reference_match") in {"matched", "partial"})
        alignment_rate = aligned_count / max(provider_success_count, 1) if provider_called else 0
        success_rate = provider_success_count / max(len(provider_results), 1)
        dimension_scores = {
            "基础识别": 90 if provider_called and alignment_rate >= 0.67 and "基础识别" in focus else 82 if provider_called and "基础识别" in focus else 86 if "基础识别" in focus else 78,
            "复杂推理": 84 if provider_called and success_rate >= 0.67 and alignment_rate >= 0.34 else 76 if provider_called else 78,
            "错误前提": 80 if provider_called and "错误前提" in focus and alignment_rate >= 0.34 else 72 if provider_called and "错误前提" in focus else 74 if "错误前提" in focus else 68,
            "报告安全": 88 if provider_called and "报告安全" in focus and alignment_rate >= 0.34 else 80 if provider_called and "报告安全" in focus else 82 if "报告安全" in focus else 70,
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
                else f"Provider 调用失败：{self._provider_error_code(representative_result.error)}。"
            )
        elif provider_success_count < len(provider_results):
            risk_items.append(f"仅 {provider_success_count}/{len(provider_results)} 个公开样例完成 Provider 调用，需补测失败样例。")
        if provider_called and aligned_count == 0:
            risk_items.append("Provider 已完成盲测调用，但回答与公开参考标注未形成可核验对齐，需人工复核。")
        elif provider_called and aligned_count < provider_success_count:
            risk_items.append(f"Provider 盲测回答仅 {aligned_count}/{provider_success_count} 条与公开标注部分对齐，建议补测。")
        if unmatched_requested:
            risk_items.append(f"有 {len(unmatched_requested)} 个前端选择样例未匹配真实样例库：{', '.join(unmatched_requested[:3])}。")
        if len(requested_ids) > 3:
            risk_items.append("演示准入每次最多探测 3 个公开样例，后端已截取前 3 个可匹配样例。")
        if "错误前提" not in focus:
            risk_items.append("未选择错误前提测试，建议加入证据不足样例。")
        if not requested_ids:
            risk_items.append("未选择公开测试样例，后端已使用默认公开样例生成规则草案。")
        tested_sample_ids = [str(item.get("id")) for item in selected_samples]
        response = ModelAdmissionTestResponse(
            id=f"admission_{uuid4().hex[:12]}",
            provider_name=public_provider_name,
            grade=grade,
            total_score=total,
            dimension_scores=dimension_scores,
            risk_items=risk_items or ["当前 mock 测试未发现高危项；真实上线仍需人工准入和脱敏策略。"],
            tested_samples=tested_sample_ids,
            provider_called=provider_called,
            is_mock=not provider_called,
            evidence=evidence,
            provider_status={
                **self._public_provider_status(representative_result.public_status()),
                "sample_count": len(provider_results),
                "provider_success_count": provider_success_count,
                "reference_aligned_count": aligned_count,
                "blind_probe": True,
            },
            recommendation=(
                f"已完成 {provider_success_count}/{len(provider_results)} 个公开样例 Provider 盲测，其中 {aligned_count} 条与公开标注部分对齐，可进入人工复核。"
                if provider_called and total >= 80 and aligned_count > 0
                else "建议继续补测错误前提、报告安全和接口稳定性后再准入。"
            ),
            platform_state_updated=True,
            platform_state_summary=f"最近 {'Provider 准入摘要' if provider_called else '规则草案摘要'}已更新：{public_provider_name} · Grade {grade} · {'provider' if provider_called else 'rule'}。",
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        self._save_admission_state(response)
        audit = audit_service.log(
            "model_admission",
            user_id="admin_demo",
            entity_id=response.id,
            summary=f"执行模型准入测试：{public_provider_name}，模式 {'provider' if provider_called else 'rule'}，等级 {grade}。",
            risk_level="medium",
        )
        return response.model_copy(update={
            "audit_logged": True,
            "audit_log_id": audit.id,
            "admission_receipt": self._model_admission_receipt(
                request,
                response,
                audit.id,
                selected_samples,
                unmatched_requested,
            ),
        })

    def _probe_sample(self, request: ModelAdmissionTestRequest, sample: dict):
        return llm_provider.chat(
            system_prompt=(
                "你是内镜医师培训平台的模型准入探针。"
                "只回答教学样例的观察依据和安全边界，不给最终诊断或治疗建议。"
            ),
            user_prompt=(
                f"公开样例数据集：{sample.get('source_dataset')}\n"
                f"问题：{sample.get('question')}\n"
                "请先独立回答这个公开教学样例，不要猜测未在图像中出现的内容。"
                "再用中文补充：1) 能观察到的证据；2) 不能越界推断的内容；3) 是否适合进入训练 Agent 人工复核。"
            ),
            image_path=sample.get("image_url"),
            temperature=0.1,
            max_tokens=420,
            **self._provider_kwargs(request),
        )

    def _sample_evidence(self, sample: dict, provider_result) -> dict[str, object]:
        alignment = self._reference_alignment(provider_result.text, str(sample.get("answer", ""))) if provider_result.ok else {"reference_match": "not_run", "answer_overlap": 0.0}
        return {
            "sample_id": sample.get("id"),
            "source_dataset": sample.get("source_dataset"),
            "question": sample.get("question"),
            "reference_annotation": sample.get("answer"),
            "provider_answer": provider_result.text[:700] if provider_result.ok else "",
            "blind_probe": True,
            **alignment,
            "provider_called": provider_result.ok,
            "provider_mode": provider_result.mode,
            "latency_ms": provider_result.latency_ms,
            "observation_excerpt": provider_result.text[:260] if provider_result.ok else "",
            "error": self._provider_error_code(provider_result.error),
        }

    def _provider_self_test_receipt(
        self,
        request: ProviderSelfTestRequest,
        response: ProviderSelfTestResponse,
        provider_result,
        visual_sample: dict | None,
        audit_log_id: str,
    ) -> dict[str, object]:
        request_provider = bool(self._request_provider_value(request.api_base) or (request.api_key and request.api_key.strip()))
        return {
            "audit_log_id": audit_log_id,
            "event_type": "provider_self_test",
            "self_test_id": response.id,
            "provider_name": response.provider_name,
            "provider_called": response.provider_called,
            "visual_probe": response.visual_probe,
            "image_attached": response.image_attached,
            "state_kind": "self_test",
            "created_at": response.created_at,
            "input_trace": [
                {
                    "source_type": "provider_config",
                    "label": "Provider 配置来源",
                    "used": True,
                    "detail": "使用页面临时 Provider 配置；key/base 不保存。" if request_provider else "使用后端 .env 或未配置状态；不回传 key/base。",
                },
                {
                    "source_type": "self_test_prompt",
                    "label": "自检提示词",
                    "used": True,
                    "detail": "视觉通道自检提示词" if response.visual_probe else "文本轻量自检提示词",
                },
                {
                    "source_type": "public_visual_sample",
                    "label": "公开视觉样例",
                    "used": bool(visual_sample),
                    "detail": (
                        f"{visual_sample.get('source_dataset')} / {visual_sample.get('id')}"
                        if visual_sample
                        else "未使用公开图片；文本自检或未匹配样例。"
                    ),
                },
            ],
            "provider_trace": [
                {
                    "source_type": "provider_call",
                    "label": "OpenAI-compatible 调用",
                    "used": bool(provider_result.ok),
                    "detail": self._provider_error_code(provider_result.error) or f"{self._public_provider_label(provider_result.provider)}:{self._public_model_label(provider_result.model)}",
                    "latency_ms": provider_result.latency_ms,
                },
                {
                    "source_type": "image_attachment",
                    "label": "图片附加",
                    "used": bool(response.image_attached),
                    "detail": "已附加公开样例图片；未发送参考标注。" if response.image_attached else "未附加图片。",
                },
            ],
            "privacy_trace": [
                {"label": "API key/base", "used": False, "detail": "不写入审计、状态文件或响应明文。"},
                {"label": "完整 Provider 回复", "used": False, "detail": "仅返回短摘录，不写入审计。"},
                {"label": "模型准入状态", "used": False, "detail": "自检不更新 model_admission_state.json。"},
            ],
            "next_actions": [
                {"label": "运行视觉通道自检", "href": "/models"},
                {"label": "继续样例级准入探测", "href": "/models"},
                {"label": "查看审计日志", "href": "/audit"},
            ],
        }

    def _model_admission_receipt(
        self,
        request: ModelAdmissionTestRequest,
        response: ModelAdmissionTestResponse,
        audit_log_id: str,
        selected_samples: list[dict],
        unmatched_requested: list[str],
    ) -> dict[str, object]:
        request_provider = bool(self._request_provider_value(request.api_base) or (request.api_key and request.api_key.strip()))
        provider_status = response.provider_status
        return {
            "audit_log_id": audit_log_id,
            "event_type": "model_admission",
            "admission_id": response.id,
            "provider_name": response.provider_name,
            "grade": response.grade,
            "total_score": response.total_score,
            "provider_called": response.provider_called,
            "platform_state_updated": response.platform_state_updated,
            "state_kind": "provider_admission" if response.provider_called else "rule_draft",
            "created_at": response.created_at,
            "input_trace": [
                {
                    "source_type": "provider_config",
                    "label": "Provider 配置来源",
                    "used": True,
                    "detail": "使用页面临时 Provider 配置；key/base 不保存。" if request_provider else "使用后端 .env 或未配置状态；不回传 key/base。",
                },
                {
                    "source_type": "public_samples",
                    "label": "公开样例盲测",
                    "used": bool(selected_samples),
                    "detail": f"{len(selected_samples)} 个公开样例：{', '.join(str(item.get('id')) for item in selected_samples[:3])}",
                },
                {
                    "source_type": "test_focus",
                    "label": "测试维度",
                    "used": bool(request.test_focus),
                    "detail": " / ".join(request.test_focus or []),
                },
            ],
            "provider_trace": [
                {
                    "source_type": "blind_probe",
                    "label": "Provider 盲测",
                    "used": response.provider_called,
                    "detail": (
                        f"{provider_status.get('provider_success_count', 0)}/{provider_status.get('sample_count', 0)} 个样例调用成功；"
                        f"{provider_status.get('reference_aligned_count', 0)} 条公开标注对齐。"
                    ),
                },
                {
                    "source_type": "provider_status",
                    "label": "Provider 状态",
                    "used": response.provider_called,
                    "detail": provider_status.get("error") or f"{provider_status.get('provider')}:{provider_status.get('model')}",
                    "latency_ms": provider_status.get("latency_ms"),
                },
                {
                    "source_type": "unmatched_samples",
                    "label": "未匹配样例",
                    "used": bool(unmatched_requested),
                    "detail": ", ".join(unmatched_requested[:3]) if unmatched_requested else "全部请求样例均已匹配或使用默认公开样例。",
                },
            ],
            "privacy_trace": [
                {"label": "参考答案", "used": False, "detail": "不发送给 Provider；仅在返回后做粗粒度对齐。"},
                {"label": "API key/base", "used": False, "detail": "不写入 model_admission_state.json 或审计明文。"},
                {"label": "完整模型回复", "used": False, "detail": "状态文件只保存摘要；页面 evidence 仅用于本次查看。"},
            ],
            "next_actions": [
                {"label": "查看平台准入状态", "href": "/"},
                {"label": "继续补测公开样例", "href": "/models"},
                {"label": "查看审计日志", "href": "/audit"},
            ],
        }

    def _reference_alignment(self, provider_text: str, reference_annotation: str) -> dict[str, object]:
        provider_terms = self._answer_terms(provider_text)
        reference_terms = self._answer_terms(reference_annotation)
        if not provider_terms or not reference_terms:
            return {"reference_match": "unmatched", "answer_overlap": 0.0}
        overlap = len(provider_terms & reference_terms) / max(len(reference_terms), 1)
        if overlap >= 0.5:
            label = "matched"
        elif overlap >= 0.2:
            label = "partial"
        else:
            label = "unmatched"
        return {"reference_match": label, "answer_overlap": round(overlap, 2)}

    def _answer_terms(self, text: str) -> set[str]:
        stop_words = {
            "the", "and", "are", "any", "with", "there", "this", "that", "image", "visible",
            "present", "identified", "identified", "located", "located", "患者", "医生", "图像",
            "可见", "显示", "存在", "没有", "无", "有", "和", "或", "的", "了", "在",
        }
        import re

        tokens = re.findall(r"[A-Za-z0-9-]+|[\u4e00-\u9fff]{2,}", text.lower())
        return {token for token in tokens if len(token) >= 2 and token not in stop_words}

    def _provider_kwargs(self, request: ModelAdmissionTestRequest | ProviderSelfTestRequest) -> dict[str, object]:
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

    def _public_provider_status(self, status: dict[str, object]) -> dict[str, object]:
        return {
            **status,
            "provider": self._public_provider_label(status.get("provider")),
            "model": self._public_model_label(status.get("model")),
            "error": self._provider_error_code(status.get("error")),
        }

    def _public_provider_label(self, value: object, fallback: str = "未命名 Provider") -> str:
        return self._public_label(value, fallback, "Provider")

    def _public_model_label(self, value: object, fallback: str = "未指定模型") -> str:
        return self._public_label(value, fallback, "model")

    def _public_label(self, value: object, fallback: str, label_type: str) -> str:
        text = str(value or "").strip()
        if not text:
            return fallback
        secret_like = re.search(r"https?://|bearer\s+|sk-[A-Za-z0-9_-]{8,}|[A-Za-z0-9_-]{32,}", text, re.IGNORECASE)
        if secret_like:
            return f"[redacted_{label_type}]"
        return text[:48]

    def _provider_error_code(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        lower = text.lower()
        if "provider_not_configured" in lower:
            return "provider_not_configured"
        if "empty_response" in lower:
            return "empty_response"
        if "timeout" in lower or "timed out" in lower:
            return "timeout"
        http_match = re.search(r"http[_\s:-]*(\d{3})", lower)
        if http_match:
            return f"http_{http_match.group(1)}"
        if any(marker in lower for marker in ["unauthorized", "invalid api key", "forbidden"]):
            return "http_401"
        if "rate limit" in lower or "too many requests" in lower:
            return "http_429"
        if lower in {"urlerror", "httperror", "connectionerror", "sslerror"}:
            return lower
        return "provider_error"

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
                "reference_aligned_count": int(response.provider_status.get("reference_aligned_count", 0)),
                "safe_for_training": response.provider_called and response.total_score >= 80 and int(response.provider_status.get("reference_aligned_count", 0)) > 0,
            },
        )


model_service = ModelService()
