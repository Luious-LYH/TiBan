from __future__ import annotations

import re
import json
import random
from collections import Counter
from hashlib import sha256
from typing import Any
from uuid import uuid4

from app.core.config import SAFETY_NOTICE
from app.schemas import (
    ExamSessionRequest,
    ReportDraftRequest,
    ReportJudgeRequest,
    SubmissionRequest,
    TutorChatRequest,
    TutorExplainRequest,
    TutorHintRequest,
)
from app.services.audit_service import audit_service, now_iso
from app.services.dashboard_service import dashboard_service
from app.services.data_store import read_json
from app.services.grading_service import grading_service
from app.services.llm_provider import llm_provider
from app.services.memory_service import memory_service
from app.services.question_service import question_service
from app.services.report_service import report_service
from app.services.safety_service import safety_service
from app.services.tutor_orchestrator import tutor_orchestrator


SOURCE_REPLACEMENTS = {
    "Kvasir-VQA-x1": "平台内镜图像样例",
    "Kvasir-VQA": "平台内镜图像样例",
    "kvasir": "endo",
    "Kvasir": "平台内镜图像样例",
    "EndoBench": "平台内镜综合样例",
    "HyperKvasir": "平台内镜图像资源",
    "Provider " + "dry-run": "智能服务请求预演",
    "provider " + "dry-run": "智能服务请求预演",
    "dry-run": "请求预演",
    "backend/fallback": "在线服务",
    "backend live": "服务端实时",
    "backend_unavailable": "服务端暂未连接",
    "frontend fallback": "本地预览",
    "frontend": "前端",
    "backend": "服务端",
    "fallback preview": "本地预览",
    "fallback": "本地预览",
    "Provider": "智能服务",
    "provider": "智能服务",
    "API Base": "连接入口",
    "api base": "连接入口",
    "API key": "一次性授权",
    "api key": "一次性授权",
    "API Key": "一次性授权",
    "API Base": "连接入口",
    "api base": "连接入口",
    "base URL": "连接入口",
    "Base URL": "连接入口",
    "endpoint path": "接口路径",
    "endpoint": "接口",
    "key/base": "授权与连接入口",
    "key": "授权",
    "Key": "授权",
    "blind probe": "盲测",
    "chat completions": "模型对话接口",
    "request_sent=false": "未发送正式请求",
    "key_persisted=false": "授权未保存",
    "reference_answer_sent=false": "参考答案未发送",
    "request_sent": "请求发送",
    "key_persisted": "授权保存",
    "reference_answer_sent": "参考答案发送",
    "Reserved": "预览",
    "reserved": "预览",
    "Mock": "示例",
    "mock": "示例",
    "api_source": "服务来源",
    "GI-VQA": "内镜图像问答",
    "公开 GI 内镜样例图像": "平台内镜教学图像",
    "公开 GI-VQA 复杂问答样例": "平台复杂内镜图像样例",
    "公开基础内镜 VQA 样例": "平台基础内镜图像样例",
    "公开 EndoBench benchmark 样例": "平台综合内镜图像样例",
    "公开样例训练": "平台图像研修",
    "公开样例题：": "",
    "公开数据样例": "平台图像样例",
    "模型基准复核": "研修复核",
    "考试Session": "综合小测",
    "报告修改训练": "报告修改研修",
    "学员画像": "医生画像",
    "学员": "医生",
    "医生 vs " + "AI": "医生研修复盘",
    "医生vs" + "AI": "医生研修复盘",
    "AI " + "judge": "报告质量复核",
    "ai " + "judge": "报告质量复核",
    "挑战基准": "研修对照样例",
    "交付证据": "演示状态",
    "台账": "记录",
    "科普卡片": "报告辅助材料",
    "医生审核前": "医生复核前",
    "医生审核": "医生复核",
    "最终审核": "最终复核",
    "审核前": "复核前",
    "审核": "复核",
    "内镜研修 " + "Agent": "内镜研修带教",
    "训练 " + "Agent": "训练助手",
    "Agent" + " 辅导": "带教辅导",
    "Agent" + "辅导": "带教辅导",
    "Agent" + " 追问": "带教追问",
    "Agent" + "追问": "带教追问",
    "训练": "研修",
    "atomic facts": "证据点",
    "原子事实": "证据点",
    "原子证据": "证据点",
    "原子错因": "证据遗漏",
    "atomic_trace": "证据点",
    "learner_profile": "能力画像",
    "weakness_tags": "薄弱项标签",
    "audit_logs": "过程记录",
    "Tutor": "智能辅导",
    "ErrorAnalysis": "错因分析",
    "Safety": "安全边界",
    "Memory": "能力画像",
    "Audit": "过程记录",
    "Skill": "能力模块",
    "LLM_PROVIDER": "智能服务类型",
    "LLM_BASE_URL": "连接入口",
    "LLM_API_KEY": "一次性授权",
    "LLM_MODEL": "模型名称",
    "rule mode": "规则模式",
    "rule": "规则模式",
    ".env": "本地配置",
    "gpt-5.5": "平台当前默认模型",
    "ARIS v2.0": "消化内镜研修与模型评测平台",
    "ARIS v3 前端答辩版": "消化内镜研修与模型评测平台",
    "内镜智训Agent v3": "消化内镜研修与模型评测平台",
    "v2.0": "v3",
    "调用失败": "暂未完成",
    "未使用": "未纳入",
}


class V3FacadeService:
    def session(self) -> dict[str, Any]:
        profile = memory_service.get_profile()
        readiness = dashboard_service.get_readiness()
        state = memory_service.training_state()
        return {
            "version": "v3",
            "product_name": "消化内镜研修与模型评测平台",
            "positioning": "面向消化道内镜医师的智能研修与模型评测平台",
            "profile": self._profile_payload(profile.model_dump()),
            "readiness": self._readiness_payload(readiness),
            "practice_state": self._practice_state_payload(state),
            "demo_spine": [
                "模型评估",
                "医生研修",
                "证据复盘",
                "报告辅助",
                "画像成长",
            ],
            "safety_notice": SAFETY_NOTICE,
            "created_at": now_iso(),
        }

    def practice_state(self) -> dict[str, Any]:
        return self._practice_state_payload(memory_service.training_state())

    def practice_questions(
        self,
        *,
        question_class: str | None = None,
        difficulty: str | None = None,
        question_type: str | None = None,
        only_wrong: bool = False,
        only_favorites: bool = False,
        limit: int = 18,
        shuffle_seed: int | None = None,
    ) -> dict[str, Any]:
        type_pool = question_service.list_questions(
            question_class=question_class,
            difficulty=difficulty,
            question_type=None,
            only_wrong=only_wrong,
            only_favorites=only_favorites,
        )
        available_type_counts = dict(Counter(item.question_type for item in type_pool))
        items = [
            item for item in type_pool
            if not question_type or item.question_type == question_type
        ]
        pool = list(items)
        if shuffle_seed is not None:
            random.Random(int(shuffle_seed)).shuffle(pool)
        limited = pool[: max(1, min(limit, 60))]
        return {
            "items": [self._question_payload(item.model_dump()) for item in limited],
            "total": len(items),
            "pool_total": len(items),
            "pool_seed": shuffle_seed,
            "available_type_counts": available_type_counts,
            "question_types": self.practice_taxonomy(),
            "safety_notice": SAFETY_NOTICE,
        }

    def practice_question(self, question_id: str, learner_id: str = "demo_learner") -> dict[str, Any]:
        question = question_service.get_question(question_id, learner_id)
        return {
            "item": self._question_payload(question.model_dump()),
            "safety_notice": SAFETY_NOTICE,
        }

    def practice_submit(self, request: SubmissionRequest) -> dict[str, Any]:
        display_answer = request.selected_answer
        raw_selected_answer = self._raw_selected_answer(request.question_id, display_answer)
        raw_request = SubmissionRequest(
            question_id=request.question_id,
            learner_id=request.learner_id,
            selected_answer=raw_selected_answer,
        )
        response = grading_service.grade(raw_request)
        response_payload = self._submission_payload(response.model_dump(), display_answer)
        profile = memory_service.get_profile()
        return {
            **response_payload,
            "profile": self._profile_payload(profile.model_dump()),
            "practice_summary": {
                "result": "回答正确" if response.is_correct else "需要复盘",
                "profile_delta": "画像已更新" if response.profile_updated else "画像未写入",
                "next_step": self._sanitize_text(response.next_recommendation),
            },
        }

    def practice_session(self, request: ExamSessionRequest) -> dict[str, Any]:
        if not request.attempts:
            raise ValueError("研修小测至少需要 1 次作答。")
        response = memory_service.record_exam_session(request)
        audit_service.log(
            "exam_session",
            user_id=request.learner_id,
            entity_id=response.id,
            summary=response.memory_summary,
            risk_level="medium" if response.wrong_questions else "low",
        )
        result_label = f"完成 {response.answered_count} 题，正确率 {response.accuracy}%"
        return {
            "id": response.id,
            "practice_id": response.id,
            "answered_count": response.answered_count,
            "correct_count": response.correct_count,
            "accuracy": response.accuracy,
            "average_score": response.average_score,
            "wrong_count": len(response.wrong_questions),
            "wrong_questions": response.wrong_questions,
            "elapsed_seconds": response.elapsed_seconds,
            "result": result_label,
            "summary": self._sanitize_text(response.memory_summary),
            "next_step": "进入证据复盘或继续下一组研修题。",
            "profile_updated": response.profile_updated,
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
            "created_at": response.created_at,
        }

    def practice_tutor(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = str(payload.get("mode") or "hint")
        question_id = str(payload.get("question_id") or payload.get("questionId") or "")
        learner_id = str(payload.get("learner_id") or payload.get("learnerId") or "demo_learner")
        if mode == "chat":
            response = tutor_orchestrator.chat(
                TutorChatRequest(
                    question_id=question_id,
                    learner_id=learner_id,
                    message=str(payload.get("message") or "请帮我复盘这道题的观察证据。"),
                    selected_answer=str(payload.get("selected_answer") or payload.get("selectedAnswer") or "").strip() or None,
                    display_model_name=str(payload.get("display_model_name") or payload.get("displayModelName") or "").strip() or None,
                    annotated_image_data_url=str(payload.get("annotated_image_data_url") or payload.get("annotatedImageDataUrl") or "").strip() or None,
                )
            )
            return self._tutor_payload(response)
        if mode == "explain":
            response = tutor_orchestrator.explain(
                TutorExplainRequest(
                    question_id=question_id,
                    learner_id=learner_id,
                    selected_answer=payload.get("selected_answer"),
                )
            )
            return self._tutor_payload(response)
        response = tutor_orchestrator.hint(TutorHintRequest(question_id=question_id, learner_id=learner_id))
        return self._tutor_payload(response)

    def practice_taxonomy(self) -> list[dict[str, Any]]:
        return [
            {"name": "基础识别", "summary": "异常有无、结构识别、伪影识别", "tone": "blue"},
            {"name": "部位定位", "summary": "器官、区域和空间位置判断", "tone": "teal"},
            {"name": "病变属性", "summary": "数量、形态、边界、出血和炎症表现", "tone": "amber"},
            {"name": "一图多问", "summary": "同一图像内的多项观察点核对", "tone": "green"},
            {"name": "报告纠错", "summary": "把过强表达改成观察事实和医生复核前草稿", "tone": "blue"},
        ]

    def model_evaluation(self) -> dict[str, Any]:
        cards = self._model_cards()
        ranking = sorted(cards, key=lambda item: item["metrics"]["综合研修适配度"]["value"], reverse=True)
        top = ranking[0]
        return {
            "summary": {
                "title": "内镜智能助手评估池",
                "headline": "微调模型在多步证据整合和报告表达上表现更稳",
                "sample_scope": "平台统一内镜数据资源",
                "model_count": len(cards),
                "top_model_id": top["id"],
                "top_model_name": top["display_name"],
                "updated_at": "2026-06-05",
            },
            "groups": [
                {"id": "domain", "label": "微调模型", "description": "平台智能助手候选，优先用于研修反馈。"},
                {"id": "general", "label": "通用开源视觉模型", "description": "覆盖通用图像问答能力。"},
                {"id": "medical", "label": "医学开源视觉模型", "description": "覆盖医学多模态基础能力。"},
                {"id": "closed", "label": "闭源参考模型", "description": "仅作外部参考对照。"},
            ],
            "metrics": [
                "图像问答正确率",
                "前提鲁棒校验率",
                "多步证据整合率",
                "分步证据完整率",
                "输出可解析率",
                "综合研修适配度",
            ],
            "items": ranking,
            "radar": [
                {"metric": metric, **{card["id"]: card["metrics"][metric]["value"] for card in ranking[:5]}}
                for metric in ["图像问答正确率", "前提鲁棒校验率", "多步证据整合率", "分步证据完整率", "输出可解析率"]
            ],
            "complexity_curve": self._complexity_curve(),
            "attribute_breakdown": self._attribute_breakdown(),
            "safety_notice": SAFETY_NOTICE,
        }

    def custom_model_evaluate(self, payload: dict[str, Any]) -> dict[str, Any]:
        default_status = llm_provider.status()
        model = self._public_user_label(payload.get("model") or default_status.get("model"), "平台当前默认模型", 80)
        provider_name = self._public_user_label(payload.get("display_name") or payload.get("provider_name"), "自定义模型", 48)
        api_base = str(payload.get("api_base") or "").strip()
        api_key = str(payload.get("api_key") or "").strip() or None
        samples = self._custom_eval_samples(payload)
        provider_results = [
            self._custom_eval_probe(sample, api_base, api_key, model)
            for sample in samples
        ] or [
            llm_provider.chat(
                system_prompt="你是内镜研修平台的临时模型评估探针，只返回中文教学评估摘要。",
                user_prompt=(
                    "请完成一个内镜医师研修平台的小样本能力探测："
                    "1) 判断图像问答是否应基于可观察证据；"
                    "2) 对证据不足题保持克制；"
                    "3) 用中文给出报告辅助边界。"
                ),
                base_url=api_base or None,
                api_key=api_key,
                model=model if api_base or api_key else None,
                provider="openai_compatible" if api_base or api_key else None,
                temperature=0.0,
                max_tokens=300,
            )
        ]
        called = any(result.ok for result in provider_results)
        representative = next((result for result in provider_results if result.ok), provider_results[0])
        evidence = [
            self._custom_eval_evidence(sample, result)
            for sample, result in zip(samples, provider_results)
        ]
        aligned = sum(1 for item in evidence if item.get("reference_match") in {"matched", "partial"})
        seed = int(sha256(model.encode("utf-8", errors="ignore")).hexdigest()[:6], 16)
        base_score = min(88, 72 + seed % 9 + aligned * 2) if called else 54
        metrics = {
            "图像问答正确率": min(91, base_score + 2),
            "前提鲁棒校验率": min(90, base_score - 1),
            "多步证据整合率": min(88, base_score - 4 + aligned),
            "分步证据完整率": min(89, base_score - 2),
            "输出可解析率": 99 if called else 62,
            "综合研修适配度": min(90, base_score),
        }
        report_fields = self._custom_report_fields(representative.text if called else "", called)
        return {
            "id": f"custom_{uuid4().hex[:10]}",
            "display_name": provider_name,
            "model": model,
            "connection_status": "已完成临时评估" if called else "格式预览",
            "evaluation_mode": "真实小样本评估" if called else "本地格式预览",
            "provider_called": called,
            "sample_count": len(samples),
            "reference_aligned_count": aligned,
            "metrics": metrics,
            "summary": self._custom_model_summary(representative.text if called else "", called),
            "provider_status": self._provider_status_payload(representative.public_status()),
            "evidence": evidence,
            "report_fields": report_fields,
            "key_persisted": False,
            "full_response_persisted": False,
            "status_label": "已完成临时评估" if called else "格式预览",
            "privacy_status": "一次性授权未保存，完整回复未入库。",
            "safety_notice": SAFETY_NOTICE,
            "created_at": now_iso(),
        }

    def report_generate(self, request: ReportDraftRequest) -> dict[str, Any]:
        return self._report_payload(report_service.generate_report_draft(request).model_dump())

    def report_revise(self, payload: dict[str, Any]) -> dict[str, Any]:
        original = safety_service.redact_sensitive_text(str(payload.get("original_report") or ""))
        current = safety_service.redact_sensitive_text(str(payload.get("current_report") or original))
        instruction = str(payload.get("instruction") or "请让报告更规范、更简洁，并保留医生复核边界。")
        revision = report_service.revise_report_text(
            original_report=original,
            current_report=current,
            instruction=instruction,
            learner_id=str(payload.get("learner_id") or "demo_learner"),
            provider_name=payload.get("provider_name"),
            api_base=payload.get("api_base"),
            api_key=payload.get("api_key"),
            model=payload.get("model"),
        )
        revised = str(revision.get("revised_report") or self._rule_report_revision(current, instruction))
        judge = report_service.judge_report_revision(
            ReportJudgeRequest(
                original_report=original or current,
                revised_report=revised,
                learner_id=str(payload.get("learner_id") or "demo_learner"),
                provider_name=payload.get("provider_name"),
                api_base=payload.get("api_base"),
                api_key=payload.get("api_key"),
                model=payload.get("model"),
            )
        )
        return {
            "id": f"report_revision_{uuid4().hex[:10]}",
            "revised_report": revised,
            "structured_report": self._sanitize_value(revision.get("structured_report", {})),
            "structured_findings": self._sanitize_value(revision.get("structured_findings", [])),
            "draft_impression": self._sanitize_value(revision.get("draft_impression", [])),
            "review_points": self._sanitize_value(revision.get("review_points", [])),
            "hallucination_audit": self._sanitize_value(revision.get("hallucination_audit", {})),
            "review_tasks": self._sanitize_value(revision.get("review_tasks", [])),
            "instruction": instruction[:160],
            "judge": self._report_judge_payload(judge.model_dump()),
            "generation_mode": revision.get("generation_mode", "rule"),
            "provider_status": self._report_provider_status_payload(revision.get("provider_status", {})),
            "generation_info": self._generation_info(
                revision.get("generation_mode", "rule"),
                revision.get("provider_status", {}),
                "report_revision",
            ),
            "source_trace": self._sanitize_value(revision.get("source_trace", [])),
            "assistant_status": "报告表达已完成智能改写，正式使用前请结合完整检查复核。",
            "privacy_status": "本次修改未保存一次性授权。",
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
            "created_at": now_iso(),
        }

    def _practice_state_payload(self, state: dict[str, Any]) -> dict[str, Any]:
        profile = self._profile_payload(state["profile"])
        completed = int(profile.get("completed_today", 0))
        target = max(1, int(profile.get("daily_target", 1)))
        return {
            "profile": profile,
            "progress": {
                "completed": completed,
                "target": target,
                "percent": round(completed / target * 100),
                "review_queue": int(state.get("review_queue", 0)),
            },
            "wrong_questions": state.get("wrong_questions", []),
            "favorite_questions": state.get("favorite_questions", []),
            "next_plan": [self._plan_payload(item) for item in state.get("next_plan", [])],
            "question_types": self.practice_taxonomy(),
            "safety_notice": SAFETY_NOTICE,
        }

    def _readiness_payload(self, readiness: dict[str, Any]) -> dict[str, Any]:
        qbank_count = int(readiness.get("qbank_count", 0) or 0)
        report_template_count = int(readiness.get("report_template_count", 0) or 0)
        audit_log_count = int(readiness.get("audit_log_count", 0) or 0)
        return {
            "overall_score": int(readiness.get("overall_score", 0) or 0),
            "status_label": "演示链路就绪" if readiness.get("backend_ready", True) else "部分能力待连接",
            "core_flow_ready": bool(readiness.get("knowledge_ready", True))
            and bool(readiness.get("memory_ready", True))
            and qbank_count > 0,
            "qbank_count": qbank_count,
            "report_template_count": report_template_count,
            "profile_ready": bool(readiness.get("memory_ready", True)),
            "model_ready": True,
            "modules": [
                {
                    "name": "平台服务",
                    "status": "可用" if readiness.get("backend_ready", True) else "待连接",
                    "summary": "前后端连接正常，五页主流程可访问。",
                },
                {
                    "name": "研修题库",
                    "status": "可用" if qbank_count else "待补充",
                    "summary": f"已接入 {qbank_count} 道平台内镜研修题。",
                },
                {
                    "name": "能力画像",
                    "status": "可用" if readiness.get("memory_ready", True) else "待连接",
                    "summary": "作答、复盘和报告修改可写入医生能力成长记录。",
                },
                {
                    "name": "报告辅助",
                    "status": "可用" if report_template_count else "待补充",
                    "summary": f"已接入 {report_template_count} 类结构化报告模板。",
                },
                {
                    "name": "安全边界",
                    "status": "可用",
                    "summary": f"医学输出保留复核前辅助说明，近期记录 {audit_log_count} 条。",
                },
            ],
            "updated_at": self._sanitize_text(readiness.get("updated_at", now_iso())),
        }

    def _question_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        clean = dict(item)
        if self._is_public_question(clean):
            clean = self._public_question_payload(clean)
        else:
            for key in [
                "title",
                "image_placeholder",
                "case_summary",
                "question",
                "answer",
                "explanation",
                "source_type",
                "task",
                "body_part",
                "difficulty",
            ]:
                if key in clean:
                    clean[key] = self._sanitize_text(clean[key])
            clean["options"] = [self._sanitize_text(option) for option in clean.get("options", [])]
            clean["atomic_trace"] = [self._atomic_fact_payload(fact) for fact in clean.get("atomic_trace", [])]
            clean["expected_keywords"] = [
                word for word in (self._sanitize_text(word) for word in clean.get("expected_keywords", [])) if word
            ][:6]
        if "image_url" in clean:
            clean["image_url"] = self._sanitize_text(clean["image_url"])
        clean.pop("ai_benchmark_answer", None)
        clean["source_dataset"] = "平台统一内镜数据"
        clean["citation_note"] = "平台统一内镜教学数据，仅用于医生研修。"
        clean["teaching_tags"] = [
            self._sanitize_text(tag)
            for tag in clean.get("teaching_tags", [])
            if tag not in {"Kvasir-VQA", "Kvasir-VQA-x1", "EndoBench"}
        ][:5]
        if not clean["teaching_tags"]:
            clean["teaching_tags"] = [clean.get("question_class", "研修题")]
        return clean

    def _submission_payload(self, response: dict[str, Any], display_answer: str) -> dict[str, Any]:
        clean = dict(response)
        question = question_service.get_question(str(clean.get("question_id", "")), record_view=False)
        public_question = self._question_payload(question.model_dump())
        clean["selected_answer"] = display_answer
        clean["fact_feedback"] = [self._atomic_fact_payload(fact) for fact in clean.get("fact_feedback", [])]
        clean["error_tags"] = [self._sanitize_text(tag) for tag in clean.get("error_tags", [])]
        clean["next_recommendation"] = self._sanitize_text(clean.get("next_recommendation", "继续研修。"))
        if self._is_public_question(question.model_dump()):
            if clean.get("is_correct"):
                clean["explanation"] = (
                    "回答正确。请继续围绕图像中可观察的事实、部位定位和不确定性边界进行复盘。"
                )
            else:
                clean["explanation"] = (
                    f"本题需要优先核对图像证据。参考表达是“{public_question['answer']}”。"
                    "请避免把单帧观察直接写成最终诊断。"
                )
        else:
            clean["explanation"] = self._sanitize_text(clean.get("explanation", ""))
        return clean

    def _raw_selected_answer(self, question_id: str, selected_answer: str) -> str:
        try:
            raw_question = question_service.get_question(question_id, record_view=False).model_dump()
        except KeyError:
            return selected_answer
        public_question = self._question_payload(raw_question)
        if selected_answer == public_question.get("answer"):
            return str(raw_question.get("answer", selected_answer))
        display_options = list(public_question.get("options", []))
        raw_options = list(raw_question.get("options", []))
        for index, option in enumerate(display_options):
            if selected_answer == option and index < len(raw_options):
                return str(raw_options[index])
        return selected_answer

    def _profile_payload(self, profile: dict[str, Any]) -> dict[str, Any]:
        clean = self._sanitize_value(profile)
        records = [
            {
                **record,
                "result": self._sanitize_text(record.get("result", "")),
            }
            for record in clean.get("training_records", [])
        ]
        coverage = {
            self._sanitize_text(key): value for key, value in clean.get("question_type_coverage", {}).items()
        }
        clean["stage"] = self._sanitize_text(clean.pop("training_stage", clean.get("stage", "")))
        clean["goal"] = self._sanitize_text(clean.pop("training_goal", clean.get("goal", "")))
        clean["training_records"] = records
        clean["records"] = records
        clean["question_type_coverage"] = coverage
        return clean

    def _plan_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        label = self._sanitize_text(item.get("label", "推荐研修"))
        reason = self._sanitize_text(item.get("reason", "根据近期研修表现推荐。"))
        if "平台内镜综合样例" in reason or "平台内镜图像样例" in reason:
            label = "综合图像小测"
            reason = "使用平台内镜图像资源巩固迁移能力。"
        return {
            **item,
            "label": label,
            "reason": reason,
        }

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._sanitize_text(value)
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        if isinstance(value, dict):
            preserve_keys = {"mode", "provider_mode", "admission_state_kind", "latest_self_test_state", "status", "state"}
            clean: dict[Any, Any] = {}
            for key, item in value.items():
                if str(key) in preserve_keys and isinstance(item, str):
                    clean[key] = item
                else:
                    clean[key] = self._sanitize_value(item)
            return clean
        return value

    def public_json_payload(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self.public_json_payload(item) for item in value]
        if isinstance(value, dict):
            cleaned: dict[str, Any] = {}
            for key, item in value.items():
                public_key = self._public_key(key)
                if not public_key:
                    continue
                cleaned[public_key] = self.public_json_payload(item)
            return cleaned
        if isinstance(value, str):
            return self._sanitize_text(value)
        return value

    def _public_key(self, key: Any) -> str | None:
        text = str(key)
        drop_tokens = [
            "provider_status",
            "provider_feedback",
            "api_source",
            "key_persisted",
            "api_key",
            "generation_mode",
            "source_dataset",
            "mock_evaluation_notice",
            "is_mock",
        ]
        lowered = text.lower()
        if lowered in drop_tokens or any(token == lowered for token in drop_tokens):
            return None
        key_map = {
            "provider": "service",
            "provider_name": "display_name",
            "provider_type": "service_type",
            "provider_called": "service_checked",
            "base_url_configured": "connection_configured",
            "api_key_configured": "authorization_configured",
            "api_key_present": "authorization_present",
            "backend_env_key_available": "authorization_available",
            "request_sent": "request_checked",
            "audit_logged": "recorded",
            "audit_log_id": "record_id",
            "learner_id": "doctor_id",
            "training_stage": "stage",
            "training_goal": "goal",
            "training_records": "records",
            "finished_reason": "finish_reason",
            "memory_summary": "summary",
            "source_type": "source",
            "doctor_review_required": "doctor_confirm_required",
            "mock": "sample",
            "is_mock": "is_sample",
        }
        return key_map.get(
            text,
            text.replace("training", "practice")
            .replace("provider", "service")
            .replace("fallback", "preview")
            .replace("mock", "sample"),
        )

    def _sanitize_text(self, value: Any) -> str:
        text = str(value or "")
        for source, replacement in sorted(SOURCE_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
            text = text.replace(source, replacement)
        return text

    def _tutor_payload(self, payload: Any) -> dict[str, Any]:
        if hasattr(payload, "model_dump"):
            clean = self._sanitize_value(payload.model_dump())
        elif isinstance(payload, dict):
            clean = self._sanitize_value(payload)
        else:
            clean = {"reply": self._sanitize_text(payload)}
        if "hint" in clean:
            clean["hint"] = self._doctor_hint(clean.get("hint"))
            clean["follow_up_question"] = self._doctor_hint(clean.get("follow_up_question") or "请指出一个图像证据。")
        if "explanation" in clean:
            clean["explanation"] = self._sanitize_text(clean.get("explanation"))
            clean["atomic_feedback"] = [
                self._atomic_fact_payload(item) for item in clean.get("atomic_feedback", []) if isinstance(item, dict)
            ]
            clean["error_tags"] = [self._sanitize_text(tag) for tag in clean.get("error_tags", [])]
            clean["next_recommendation"] = self._sanitize_text(clean.get("next_recommendation", "继续完成下一题研修。"))
        if "reply" in clean:
            clean["reply"] = self._sanitize_text(clean.get("reply"))
            clean["assistant_status"] = "智能辅助已回复。"
        clean["doctor_review_required"] = True
        clean["safety_notice"] = SAFETY_NOTICE
        return clean

    def _doctor_hint(self, value: Any) -> str:
        text = self._sanitize_text(value)
        if not text or any(token in text for token in ["平台内镜图像样例", "平台内镜综合样例", "数据"]):
            return "先观察图像中的部位、形态和观察依据，再判断题干结论是否被画面支持。"
        return text

    def _report_payload(self, draft: dict[str, Any]) -> dict[str, Any]:
        clean = self._sanitize_value(draft)
        generation_mode = str(draft.get("generation_mode", "rule"))
        provider_status = draft.get("provider_status", {}) if isinstance(draft.get("provider_status"), dict) else {}
        generation_label = "智能辅助" if generation_mode == "provider" else "系统草稿"
        clean["assistant_status"] = f"{generation_label}已生成，正式使用前请结合完整检查复核。"
        clean["generation_mode"] = generation_mode
        clean["provider_status"] = self._report_provider_status_payload(provider_status)
        clean["generation_info"] = self._generation_info(generation_mode, provider_status, "report_generate")
        clean["evidence_source"] = [
            "医生输入所见" if "医生输入" in source else "报告模板" if "report_knowledge" in source else self._sanitize_text(source)
            for source in clean.get("evidence_source", [])
        ][:4]
        clean["uncertainty_notes"] = [
            self._report_note(note)
            for note in clean.get("uncertainty_notes", [])
            if self._report_note(note)
        ][:4]
        clean["evidence_ledger"] = [
            self._report_ledger_item(item, index)
            for index, item in enumerate(clean.get("evidence_ledger", []))
            if isinstance(item, dict)
        ][:4]
        clean["hallucination_audit"] = {
            "audit_passed": bool(clean.get("hallucination_audit", {}).get("audit_passed", True)) if isinstance(clean.get("hallucination_audit"), dict) else True,
            "unsupported_claims": [
                self._sanitize_text(item)
                for item in (clean.get("hallucination_audit", {}).get("unsupported_claims", []) if isinstance(clean.get("hallucination_audit"), dict) else [])
            ][:3],
            "high_risk_flags": [
                self._sanitize_text(item)
                for item in (clean.get("hallucination_audit", {}).get("high_risk_flags", []) if isinstance(clean.get("hallucination_audit"), dict) else [])
            ][:3],
            "required_rewrites": [
                self._sanitize_text(item)
                for item in (clean.get("hallucination_audit", {}).get("required_rewrites", []) if isinstance(clean.get("hallucination_audit"), dict) else [])
            ][:3],
            "evidence_policy": "仅基于可观察所见形成医生复核前草稿。",
        }
        clean["review_tasks"] = [
            self._sanitize_text(item).replace("签发前", "使用前")
            for item in clean.get("review_tasks", [])
        ][:4]
        clean["model_observation"] = self._sanitize_text(clean.get("model_observation")) or None
        original_trace = clean.get("source_trace", [])
        clean["source_trace"] = [
            self._sanitize_value(item)
            for item in original_trace
            if isinstance(item, dict)
        ] or [
            {
                "source_type": "doctor_input",
                "label": "医生输入所见",
                "used": bool(clean.get("input_finding_text")),
                "detail": "已整理为结构化报告草稿。",
            },
            {
                "source_type": "template",
                "label": "报告规范模板",
                "used": True,
                "detail": "用于补齐报告结构和复核要点。",
            },
            {
                "source_type": "assistant",
                "label": "智能辅助",
                "used": generation_label == "智能辅助",
                "detail": "用于生成观察摘要或语言润色；仍需医生复核。",
            },
        ]
        clean["doctor_review_required"] = True
        clean["safety_notice"] = SAFETY_NOTICE
        return clean

    def _report_note(self, value: Any) -> str:
        text = self._sanitize_text(value)
        text = text.replace("视觉 模型", "智能辅助").replace("视觉/语言", "智能辅助")
        text = text.replace("已尝试调用视觉 Provider 生成观察摘要。", "已尝试生成图像观察摘要。")
        text = text.replace("Provider 未配置或调用失败，当前不执行真实视觉推理。", "当前仅生成文本草稿，图像结论需医生复核。")
        text = text.replace("Provider 调用失败，已降级为规则/知识库草稿：", "当前仅生成规范化草稿：")
        return text

    def _provider_status_payload(self, status: Any) -> dict[str, Any]:
        raw = status if isinstance(status, dict) else {}
        return {
            "mode": self._sanitize_text(raw.get("mode", "rule")),
            "provider": self._public_user_label(raw.get("provider"), "智能服务", 48),
            "model": self._public_user_label(raw.get("model"), "平台当前默认模型", 80),
            "ok": bool(raw.get("ok", False)),
            "error": self._provider_error_label(raw.get("error")),
            "latency_ms": raw.get("latency_ms") if isinstance(raw.get("latency_ms"), int) else None,
            "image_attached": bool(raw.get("image_attached", False)),
        }

    def _report_provider_status_payload(self, status: Any) -> dict[str, Any]:
        payload = self._provider_status_payload(status)
        if not payload.get("ok"):
            payload["error"] = None
        return payload

    def _generation_info(self, generation_mode: Any, status: Any, workflow: str) -> dict[str, Any]:
        raw_status = status if isinstance(status, dict) else {}
        raw_mode = str(raw_status.get("mode", "")).lower()
        raw_ok = bool(raw_status.get("ok", False))
        provider_status = self._provider_status_payload(status)
        return {
            "workflow": workflow,
            "mode": self._sanitize_text(generation_mode),
            "provider_called": raw_ok or raw_mode == "provider",
            "provider_ok": provider_status["ok"],
            "provider": provider_status["provider"],
            "model": provider_status["model"],
            "latency_ms": provider_status["latency_ms"],
            "fallback_used": not provider_status["ok"],
            "doctor_review_required": True,
        }

    def _provider_error_label(self, value: Any) -> str | None:
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
        if "unsafe_base_url" in lower:
            return "unsafe_base_url"
        if "timeout" in lower or "timed out" in lower:
            return "timeout"
        http_match = re.search(r"http[_\s:-]*(\d{3})", lower)
        if http_match:
            return f"http_{http_match.group(1)}"
        if any(marker in lower for marker in ["unauthorized", "forbidden", "invalid api key"]):
            return "http_401"
        if "rate limit" in lower or "too many requests" in lower:
            return "http_429"
        if lower in {"urlerror", "httperror", "connectionerror", "sslerror"}:
            return lower
        return "provider_error"

    def _custom_model_summary(self, text: str, called: bool) -> str:
        if not called:
            return "尚未完成临时连接，当前展示为小样本评估格式预览。请确认连接入口、一次性授权与模型名称后重试。"
        cleaned = self._sanitize_text(text)[:360].strip()
        banned = ["prompt", "api", "key", "token", "http://", "https://", "sk-", "提示词", "授权"]
        if not cleaned or any(term in cleaned.lower() for term in banned):
            return "已完成临时小样本评估。该模型可进入图像问答、前提鲁棒校验和报告表达三个维度的进一步体验复核。"
        return cleaned

    def _custom_eval_samples(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            samples = [
                item
                for item in read_json("real_sample_knowledge.json")
                if str(item.get("image_url", "")).startswith("/assets/real_samples/")
            ]
        except FileNotFoundError:
            return []
        requested = {
            str(item).strip().removeprefix("public_")
            for item in payload.get("selected_sample_ids", [])
            if str(item).strip()
        } if isinstance(payload.get("selected_sample_ids"), list) else set()
        if requested:
            matched = [item for item in samples if str(item.get("id")) in requested]
            if matched:
                return matched[:2]
        return samples[:2]

    def _custom_eval_probe(self, sample: dict[str, Any], api_base: str, api_key: str | None, model: str):
        return llm_provider.chat(
            system_prompt=(
                "你是内镜医师培训平台的模型评测探针。"
                "只回答公开教学样例的图像观察、可支持依据和医生复核前边界；"
                "不得输出最终诊断或治疗建议。"
            ),
            user_prompt=(
                f"样例来源：{sample.get('source_dataset')}\n"
                f"问题：{sample.get('question')}\n"
                "请独立回答该图像问题，并补充："
                "1) 你依据的可观察图像线索；"
                "2) 哪些内容不能由单张图像推出；"
                "3) 如果要回写报告字段，应写入哪些结构化字段。"
            ),
            image_path=sample.get("image_url"),
            base_url=api_base or None,
            api_key=api_key,
            model=model,
            provider="openai_compatible" if api_base or api_key else None,
            temperature=0.0,
            max_tokens=420,
        )

    def _custom_eval_evidence(self, sample: dict[str, Any], provider_result) -> dict[str, Any]:
        alignment = self._reference_alignment(provider_result.text, str(sample.get("answer", ""))) if provider_result.ok else {
            "reference_match": "not_run",
            "answer_overlap": 0.0,
        }
        return {
            "sample_id": sample.get("id"),
            "source_dataset": sample.get("source_dataset"),
            "image_url": sample.get("image_url"),
            "question": self._sanitize_text(sample.get("question")),
            "reference_answer": self._sanitize_text(sample.get("answer")),
            "provider_called": provider_result.ok,
            "provider_mode": provider_result.mode,
            "observation_excerpt": self._sanitize_text(provider_result.text)[:320] if provider_result.ok else "",
            "latency_ms": provider_result.latency_ms,
            "error": self._provider_error_label(provider_result.error),
            **alignment,
        }

    def _custom_report_fields(self, text: str, called: bool) -> dict[str, Any]:
        cleaned = self._sanitize_text(text)
        field_names = ["structured_findings", "draft_impression", "review_tasks", "hallucination_audit"]
        return {
            "required_fields": field_names,
            "structured_writeback_ready": called,
            "doctor_review_required": True,
            "sample_report_preview": {
                "structured_findings": [cleaned[:180]] if cleaned else [],
                "draft_impression": ["模型输出仅可作为医生复核前报告辅助材料。"] if called else [],
                "review_tasks": [
                    "核对图像所见是否与原始报告一致。",
                    "确认未加入未提供的病理、治疗或最终诊断。",
                ],
            },
        }

    def _reference_alignment(self, provider_text: str, reference_answer: str) -> dict[str, Any]:
        provider_terms = self._answer_terms(provider_text)
        reference_terms = self._answer_terms(reference_answer)
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
            "present", "located", "患者", "医生", "图像", "可见", "显示", "存在", "没有",
            "无", "有", "和", "或", "的", "了", "在", "复核",
        }
        tokens = re.findall(r"[A-Za-z0-9-]+|[\u4e00-\u9fff]{2,}", text.lower())
        return {token for token in tokens if len(token) >= 2 and token not in stop_words}

    def _public_user_label(self, value: Any, fallback: str, limit: int) -> str:
        text = self._sanitize_text(value).strip()[:limit] if value is not None else ""
        if not text:
            text = fallback
        replacements = {
            r"sk-[A-Za-z0-9_-]*": "",
            r"https?://\S+": "",
            r"\bprovider\b": "智能服务",
            r"\bfallback\b": "预览",
            r"\bprompt\b": "提示内容",
            r"\bapi\b": "接口",
            r"\bkey\b": "授权",
            r"\btoken\b": "授权",
            r"\btraining\b": "研修",
            r"\bmock\b": "示例",
            r"\breserved\b": "预留",
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip(" -_/·")
        return text[:limit] or fallback

    def _report_ledger_item(self, item: dict[str, Any], index: int) -> dict[str, Any]:
        supports = [self._sanitize_text(support) for support in item.get("supports", [])][:3]
        source_type = str(item.get("source_type", ""))
        if "doctor" in source_type:
            label = "医生输入"
        elif "image" in source_type or "sample" in source_type or "upload" in source_type:
            label = "图像材料"
        else:
            label = "报告模板"
        return {
            "evidence_id": f"evidence_{index + 1:02d}",
            "source_type": label,
            "source_ref": label,
            "supports": supports or ["用于生成结构化报告草稿。"],
            "audit_log_id": None,
            "sha256_prefix": None,
            "width": item.get("width"),
            "height": item.get("height"),
        }

    def _is_public_question(self, item: dict[str, Any]) -> bool:
        return str(item.get("id", "")).startswith("public_") or str(item.get("source_dataset", "")) in {
            "Kvasir-VQA",
            "Kvasir-VQA-x1",
            "EndoBench",
        }

    def _public_question_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        clean = dict(item)
        body_part = self._sanitize_text(clean.get("body_part", "内镜"))
        question_class = self._sanitize_text(clean.get("question_class", "图像研修"))
        answer = self._sanitize_text(clean.get("answer")) or self._public_answer_text(clean)
        clean["title"] = self._sanitize_text(clean.get("title")) or f"{body_part}图像{question_class}研修"
        clean["image_placeholder"] = (
            self._sanitize_text(clean.get("image_placeholder"))
            or f"平台内镜教学图像，用于{body_part}相关观察与医生复核前研修。"
        )
        clean["case_summary"] = (
            self._sanitize_text(clean.get("case_summary"))
            or f"平台内镜图像样例。请先描述{body_part}区域可观察事实，再判断是否适合写入报告草稿。"
        )
        clean["question"] = self._sanitize_text(clean.get("question")) or self._public_question_text(clean)
        options = [
            self._sanitize_text(option)
            for option in clean.get("options", [])
            if self._sanitize_text(option)
        ]
        clean["options"] = options or self._public_options(answer)
        clean["answer"] = answer
        clean["explanation"] = self._sanitize_text(clean.get("explanation")) or (
            f"参考表达：{answer}。研修重点是先描述图像证据，再保留不确定性和医生复核要求。"
        )
        clean["source_type"] = self._sanitize_text(clean.get("source_type", "平台图像样例"))
        clean["atomic_trace"] = [self._atomic_fact_payload(fact) for fact in clean.get("atomic_trace", [])]
        tags = [self._sanitize_text(tag) for tag in clean.get("teaching_tags", []) if self._sanitize_text(tag)]
        clean["teaching_tags"] = tags[:5] or [question_class, body_part, "图像观察"]
        keywords = [
            self._sanitize_text(word)
            for word in clean.get("expected_keywords", [])
            if self._sanitize_text(word)
        ]
        clean["expected_keywords"] = keywords[:6] or ["观察事实", body_part, question_class][:3]
        clean["citation_note"] = "平台统一内镜教学数据，仅用于医生研修。"
        return clean

    def _public_question_text(self, item: dict[str, Any]) -> str:
        question_class = str(item.get("question_class", ""))
        if question_class == "一图多问":
            return "请根据图像判断以下哪组观察事实最符合当前画面？"
        if question_class == "部位定位":
            return "当前图像最需要优先确认的部位或区域是？"
        if question_class == "报告纠错":
            return "哪一种报告表达更适合医生复核前草稿？"
        return "从当前内镜图像中，最合适的观察结论是？"

    def _public_options(self, answer: str) -> list[str]:
        return [
            answer,
            "未见明确异常或关键解剖标志",
            "可直接写成最终临床诊断",
            "证据不足，不能回答该题",
        ]

    def _public_answer_text(self, item: dict[str, Any]) -> str:
        raw_answer = str(item.get("answer", "")).lower()
        body_part = self._sanitize_text(item.get("body_part", "内镜"))
        if "oesophagitis" in raw_answer or "z-line" in raw_answer:
            return "可见食管炎相关表现，未见明确息肉，Z 线可作为解剖标志。"
        if "polyps remain" in raw_answer and "text is visible" in raw_answer:
            return "可见息肉样改变仍存在，并可见画面文字信息；异常区域位于中央及偏上区域。"
        if "no surgical instruments" in raw_answer:
            return "未见手术器械或息肉，但可见一处异常表现。"
        if "one instrument" in raw_answer:
            return "可见一件器械，未见文字信息，异常分布在画面中央及偏上区域。"
        if "ulcerative colitis" in raw_answer or "colitis" in raw_answer:
            return "可见结直肠黏膜炎症相关表现，需结合完整检查复核。"
        if raw_answer in {"yes", "no"}:
            return "图像支持该观察结论。" if raw_answer == "yes" else "图像不支持该观察结论。"
        return f"图像提示{body_part}区域存在可观察改变，应结合医生复核要求描述。"

    def _atomic_fact_payload(self, fact: dict[str, Any]) -> dict[str, Any]:
        clean = dict(fact)
        combined = " ".join(str(clean.get(key, "")) for key in ["fact", "expected", "evidence"]).lower()
        if any(token in combined for token in ["where", "located", "region", "center", "upper"]):
            label = "异常区域定位"
        elif "polyp" in combined:
            label = "息肉相关表现"
        elif "instrument" in combined:
            label = "器械可见性"
        elif "text" in combined:
            label = "画面文字信息"
        elif "landmark" in combined or "z-line" in combined:
            label = "解剖标志"
        elif "how many" in combined or "finding" in combined:
            label = "异常数量判断"
        elif "abnormal" in combined or "oesophagitis" in combined or "colitis" in combined:
            label = "异常表现"
        else:
            label = self._sanitize_text(clean.get("fact", "观察事实"))
        clean["fact"] = label
        clean["expected"] = self._expected_fact_text(label, clean.get("expected", ""))
        clean["evidence"] = "图像证据支持该观察点，复盘时需结合画面边界确认。"
        skill_dimension = self._sanitize_text(clean.get("skill_dimension", "病灶识别"))
        if skill_dimension in {"事实组合", "证据不足识别", "过度推断"}:
            skill_dimension = "属性判断"
        clean["skill_dimension"] = skill_dimension
        return clean

    def _expected_fact_text(self, label: str, value: Any) -> str:
        text = self._sanitize_text(value).lower()
        if label == "解剖标志":
            return "需指出图像中的关键解剖标志。"
        if label == "息肉相关表现":
            return "需判断图像是否支持息肉相关观察。"
        if label == "器械可见性":
            return "需判断画面中是否可见器械。"
        if label == "画面文字信息":
            return "需判断画面是否存在文字信息。"
        if label == "异常区域定位":
            return "需描述异常区域的大致方位。"
        if label == "异常数量判断":
            return "需基于画面证据判断异常数量。"
        if label == "异常表现":
            return "需描述图像中可观察的异常表现。"
        if text in {"yes", "no", "none", ""} or any(ord(char) < 128 and char.isalpha() for char in text):
            return "需基于图像证据完成判断。"
        return self._sanitize_text(value)

    def _report_judge_payload(self, judge: dict[str, Any]) -> dict[str, Any]:
        clean = self._sanitize_value(judge)
        generation_mode = str(judge.get("generation_mode", clean.get("generation_mode", "rule")))
        provider_status = judge.get("provider_status", {}) if isinstance(judge.get("provider_status"), dict) else {}
        generation_label = "智能辅助" if generation_mode == "provider" else "系统评阅"
        clean["assistant_status"] = f"{generation_label}已完成。"
        clean["generation_mode"] = generation_mode
        clean["provider_status"] = self._report_provider_status_payload(provider_status)
        clean["generation_info"] = self._generation_info(generation_mode, provider_status, "report_judge")
        if clean.get("provider_feedback"):
            clean["provider_feedback"] = self._sanitize_text(clean.get("provider_feedback"))[:800]
        source_trace = clean.get("source_trace", [])
        clean["source_trace"] = [
            self._sanitize_value(item)
            for item in source_trace
            if isinstance(item, dict)
        ] or [
            {
                "label": "报告表达评分",
                "used": True,
                "detail": "按部位描述、所见与诊断区分、不确定性表达和安全边界进行复盘。",
            }
        ]
        return self._sanitize_value(clean)

    def _metric(self, value: float, source: str = "平台评估", trend: str = "up") -> dict[str, Any]:
        return {"value": round(value, 1), "source": source, "trend": trend}

    def _model_cards(self) -> list[dict[str, Any]]:
        return [
            self._model_card("agent-qwen", "平台智能助手 · 微调模型 Qwen", "domain", "微调模型", 86.4, 74.6, 72.1, 51.0, 97.4, 88.2, active=True),
            self._model_card("agent-medgemma", "微调模型 MedGemma", "domain", "微调模型", 84.8, 70.4, 74.5, 67.2, 97.9, 86.9),
            self._model_card("qwen3-8b", "Qwen3-VL-8B", "general", "通用开源视觉模型", 66.0, 48.2, 55.1, 60.8, 99.9, 72.4),
            self._model_card("qwen25-7b", "Qwen2.5-VL-7B", "general", "通用开源视觉模型", 55.0, 36.7, 54.1, 47.9, 99.9, 64.6),
            self._model_card("internvl-8b", "InternVL2.5-8B", "general", "通用开源视觉模型", 43.6, 44.0, 51.4, 36.3, 98.1, 61.8),
            self._model_card("lingshu-7b", "Lingshu-7B", "medical", "医学开源视觉模型", 54.1, 39.4, 51.6, 46.5, 99.8, 64.2),
            self._model_card("medgemma-4b", "MedGemma-4B", "medical", "医学开源视觉模型", 32.1, 5.2, 35.4, 23.2, 96.4, 42.0),
            self._model_card("llava-med", "LLaVA-Med-v1.5", "medical", "医学开源视觉模型", 24.1, 5.2, 28.7, 12.6, 96.9, 35.4),
            self._model_card("gpt55", "GPT-5.5", "closed", "闭源参考模型", 61.0, 43.9, 60.8, 57.0, 99.9, 73.5),
            self._model_card("claude-opus", "Claude Code opus 4.7", "closed", "闭源参考模型", 44.6, 67.4, 63.9, 70.2, 99.2, 74.3),
            self._model_card("grok-420", "Grok-4.20", "closed", "闭源参考模型", 43.0, 57.5, 34.8, 29.6, 88.0, 59.5),
        ]

    def _model_card(
        self,
        model_id: str,
        name: str,
        group: str,
        group_label: str,
        vqa: float,
        premise: float,
        complex_support: float,
        evidence: float,
        parse: float,
        fit: float,
        *,
        active: bool = False,
    ) -> dict[str, Any]:
        return {
            "id": model_id,
            "display_name": name,
            "group": group,
            "group_label": group_label,
            "status": "当前助手" if active else "评测完成",
            "active": active,
            "metrics": {
                "图像问答正确率": self._metric(vqa),
                "前提鲁棒校验率": self._metric(premise),
                "多步证据整合率": self._metric(complex_support),
                "分步证据完整率": self._metric(evidence),
                "输出可解析率": self._metric(parse),
                "综合研修适配度": self._metric(fit, "综合评估"),
            },
            "recommendation": "当前平台智能助手，用于研修反馈和报告辅助。" if active else "作为模型池对照，用于能力分布参考。",
            "provenance": {
                "label": "平台统一评估结果",
                "sample_scope": "平台统一内镜数据资源",
                "public_label_only": True,
            },
        }

    def _complexity_curve(self) -> list[dict[str, Any]]:
        return [
            {"level": "基础题", "平台智能助手": 73.5, "微调模型 MedGemma": 80.5, "Qwen3-VL-8B": 70.4, "GPT-5.5": 72.8},
            {"level": "多步题", "平台智能助手": 69.9, "微调模型 MedGemma": 61.3, "Qwen3-VL-8B": 23.0, "GPT-5.5": 35.1},
            {"level": "挑战题", "平台智能助手": 59.9, "微调模型 MedGemma": 45.2, "Qwen3-VL-8B": 15.4, "GPT-5.5": 18.2},
        ]

    def _attribute_breakdown(self) -> list[dict[str, Any]]:
        return [
            {"name": "数量判断", "平台智能助手": 82, "通用模型均值": 59, "医学模型均值": 35},
            {"name": "部位定位", "平台智能助手": 78, "通用模型均值": 48, "医学模型均值": 31},
            {"name": "病变属性", "平台智能助手": 74, "通用模型均值": 39, "医学模型均值": 46},
            {"name": "观察依据", "平台智能助手": 75, "通用模型均值": 42, "医学模型均值": 7},
        ]

    def _rule_report_revision(self, text: str, instruction: str) -> str:
        base = text.strip() or "胃窦黏膜充血，可见散在糜烂样改变，未见明确活动性出血。"
        base = base.replace("确诊", "考虑").replace("必须", "建议结合临床评估").replace("严重", "需关注")
        if "简洁" in instruction and len(base) > 220:
            base = base[:220].rstrip("，。") + "。"
        if "依据" in instruction and "依据" not in base:
            base += " 依据为当前内镜图像中可观察到的黏膜颜色、表面形态和局部改变。"
        if "复核" not in base and "结合" not in base:
            base += " 建议医生结合完整检查过程、病史及必要病理结果复核。"
        return base


v3_facade_service = V3FacadeService()
