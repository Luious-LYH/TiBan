import base64
import re
from uuid import uuid4

from app.core.config import SAFETY_NOTICE, UPLOAD_DIR
from app.schemas import ChallengeBenchmarkRequest, ChallengeBenchmarkResponse, SubmissionRequest, TutorChatRequest, TutorChatResponse, TutorExplainRequest, TutorHintRequest
from app.services.audit_service import now_iso
from app.services.audit_service import audit_service
from app.services.grading_service import grading_service
from app.services.llm_provider import llm_provider
from app.services.memory_service import memory_service
from app.services.question_service import question_service
from app.services.safety_service import safety_service


class TutorOrchestrator:
    def hint(self, request: TutorHintRequest) -> dict[str, object]:
        question = question_service.get_question(request.question_id, request.learner_id)
        first_tag = question.teaching_tags[0] if question.teaching_tags else "图像证据"
        hint = (
            f"先不要急着选答案。请围绕“{first_tag}”观察："
            "这个选项是否有图像证据支持？有没有把观察事实过度升级为诊断？"
        )
        if question.false_premise_flag:
            hint = "这题可能有题干前提陷阱：先判断题干假设是否真的被图像支持，再决定是否作答。"
        audit_service.log(
            "tutor_reply",
            user_id=request.learner_id,
            entity_id=question.id,
            summary="智能辅导生成提示，未泄露标准答案。",
        )
        return {
            "hint": hint,
            "follow_up_question": "请指出你选择该答案时依赖的一个图像证据，或说明为什么证据不足。",
            "leak_answer": False,
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
        }

    def explain(self, request: TutorExplainRequest) -> dict[str, object]:
        question = question_service.get_question(request.question_id, request.learner_id)
        selected = request.selected_answer or question.answer
        grade = grading_service.grade(
            SubmissionRequest(question_id=question.id, learner_id=request.learner_id, selected_answer=selected),
            record=False,
        )
        audit_service.log(
            "tutor_reply",
            user_id=request.learner_id,
            entity_id=question.id,
            summary="智能辅导生成答案讲解和 atomic feedback。",
            risk_level="medium",
        )
        return {
            "explanation": grade.explanation,
            "error_tags": grade.error_tags,
            "atomic_feedback": [fact.model_dump() for fact in grade.fact_feedback],
            "next_recommendation": grade.next_recommendation,
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
        }

    def chat(self, request: TutorChatRequest) -> dict[str, object]:
        question = question_service.get_question(request.question_id, request.learner_id)
        review = safety_service.review_text(request.message)
        display_model_name = self._display_model_name(request.display_model_name)
        user_intent = self._chat_intent(request.message)
        annotated_image_path = self._store_annotated_image(request.annotated_image_data_url)
        if not review["passed"]:
            reply = "这个问题可能涉及真实诊疗或敏感信息。我只能围绕当前教学题的图像证据、答案依据和复核点进行解释。"
            risk = "high"
            provider_result = None
        else:
            provider_result = llm_provider.chat(
                system_prompt=(
                    "你是消化内镜医师研修平台右侧的实时带教助手。"
                    f"对外展示名称固定为「{display_model_name}」，不要自称 Codex、ChatGPT、GPT 或任何底层供应商模型。"
                    "先回答用户这一次真正问的问题，再决定是否自然带回当前研修题。"
                    "如果用户问“你是什么模型/你是谁/你能做什么/可以辅导我吗”或只是打招呼，"
                    "必须像真人带教一样直接、简短回答，不要套用固定观察模板，不要一上来追问图像证据。"
                    "如果用户询问题目、选项、图像、答案依据或报告表达，再围绕当前公开教学题做引导。"
                    "如果提供了圈画后的标注图片，请优先结合标注区域解释，不要忽略用户圈出的重点。"
                    "辅导时可以提示观察路径，但不要泄露最终答案；不要输出诊断结论、治疗建议或真实患者判断。"
                    "全程使用自然中文，避免机械套话。"
                ),
                user_prompt=self._chat_user_prompt(question, request.message, display_model_name, user_intent, bool(annotated_image_path)),
                image_path=annotated_image_path or (question.image_url if user_intent == "question_context" else None),
                temperature=0.35,
                max_tokens=460,
            )
            if provider_result.ok:
                reply = self._clean_chat_reply(provider_result.text, request.message, display_model_name)
            else:
                reply = self._fallback_chat_reply(question.title, question.teaching_tags, request.message, display_model_name)
            risk = "low"
        provider_status = provider_result.public_status() if provider_result else llm_provider.status()
        generation_mode = "provider" if provider_result and provider_result.ok else "fallback" if provider_result and provider_result.error != "provider_not_configured" else "rule"
        interaction_tags, memory_summary = memory_service.record_tutor_interaction(
            question,
            generation_mode=generation_mode,
            safety_passed=bool(review["passed"]),
        )
        audit_service.log(
            "tutor_reply",
            user_id=request.learner_id,
            entity_id=question.id,
            summary=f"带教辅导完成；模式 {generation_mode}；已回灌画像；未保存医师追问原文。",
            risk_level=risk,
        )
        return TutorChatResponse(
            reply=reply,
            scope="current_question_only",
            generation_mode=generation_mode,
            provider_status=provider_status,
            interaction_tags=interaction_tags,
            profile_updated=True,
            memory_summary=memory_summary,
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
        ).model_dump()

    def _display_model_name(self, value: str | None) -> str:
        text = str(value or "").strip()
        if not text or len(text) > 80:
            return "平台当前研修模型"
        blocked = ["http://", "https://", "sk-", "key", "token", "secret"]
        lowered = text.lower()
        if any(token in lowered for token in blocked):
            return "平台当前研修模型"
        return text

    def _chat_intent(self, message: str) -> str:
        text = message.strip().lower()
        if not text:
            return "empty"
        identity_terms = ["你是谁", "你是什么", "什么模型", "模型", "你叫", "是谁"]
        capability_terms = ["能做什么", "可以干什么", "你可以干什么", "能干什么", "能不能辅导", "可以辅导"]
        greeting_terms = {"hi", "hello", "你好", "您好", "哈喽", "在吗"}
        if any(term in text for term in identity_terms):
            return "identity"
        if any(term in text for term in capability_terms):
            return "capability"
        if text in greeting_terms or len(text) <= 4 and any(term in text for term in greeting_terms):
            return "greeting"
        return "question_context"

    def _chat_user_prompt(self, question, message: str, display_model_name: str, user_intent: str, has_annotation: bool) -> str:
        if user_intent in {"identity", "capability", "greeting"}:
            return (
                f"前端当前显示的研修模型：{display_model_name}\n"
                f"用户意图判断：{user_intent}\n"
                f"当前研修题：{question.title}\n"
                f"医师追问：{message}\n"
                f"图像状态：{'已包含圈画标注图' if has_annotation else '未包含标注'}\n"
                "请直接回答用户原话。不要分析图像，不要追问证据，不要展开题目模板。"
                "回答 1-3 句自然中文；如果合适，最后一句邀请用户继续说卡在哪一步。"
            )
        return (
            f"前端当前显示的研修模型：{display_model_name}\n"
            f"用户意图判断：{user_intent}\n"
            f"题目标题：{question.title}\n"
            f"病例摘要：{question.case_summary}\n"
            f"题干：{question.question}\n"
            f"题型：{question.question_type}\n"
            f"教学标签：{', '.join(question.teaching_tags)}\n"
            f"图像状态：{'已包含圈画标注图' if has_annotation else '未包含标注'}\n"
            f"可审计原子事实：{'; '.join(f'{fact.fact} -> {fact.evidence}' for fact in question.atomic_trace)}\n"
            f"医师追问：{message}\n"
            "请给出 2-4 句中文辅导，聚焦观察依据和下一步，不直接说出标准答案。"
        )

    def _store_annotated_image(self, data_url: str | None) -> str | None:
        text = str(data_url or "").strip()
        if not text:
            return None
        if len(text) > 3_500_000:
            return None
        match = re.match(r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$", text, re.DOTALL)
        if not match:
            return None
        mime, encoded = match.groups()
        try:
            payload = base64.b64decode(encoded, validate=True)
        except Exception:
            return None
        if not payload or len(payload) > 2_500_000:
            return None
        suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp"}[mime]
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"annotated_{uuid4().hex[:12]}{suffix}"
        path = UPLOAD_DIR / filename
        try:
            path.write_bytes(payload)
            return f"uploads/{filename}"
        except Exception:
            return None

    def _clean_chat_reply(self, reply: str, message: str, display_model_name: str) -> str:
        cleaned = reply.strip()
        intent = self._chat_intent(message)
        cleaned = cleaned.replace("**", "")
        cleaned = cleaned.replace("Hi，我在", "你好，我在").replace("hi，我在", "你好，我在")
        cleaned = cleaned.replace("先别急着选，", "").replace("这题先别急着选，", "")
        replacements = {
            "我是 Codex": f"我是{display_model_name}",
            "我是 ChatGPT": f"我是{display_model_name}",
            "我是GPT": f"我是{display_model_name}",
            "我是 GPT": f"我是{display_model_name}",
            "作为 Codex": f"作为{display_model_name}",
            "作为 ChatGPT": f"作为{display_model_name}",
        }
        for source, target in replacements.items():
            cleaned = cleaned.replace(source, target)
        if intent in {"identity", "capability", "greeting"} and self._looks_like_question_template(cleaned):
            return self._fallback_chat_reply("", [], message, display_model_name)
        if intent == "identity" and display_model_name not in cleaned[:120]:
            cleaned = f"我在当前研修界面中显示为「{display_model_name}」，由平台后端智能服务实时生成回复。{cleaned}"
        if intent == "question_context":
            cleaned = self._remove_leading_identity(cleaned, display_model_name)
        return cleaned[:1200]

    def _remove_leading_identity(self, reply: str, display_model_name: str) -> str:
        text = reply.strip()
        identity_prefixes = [
            f"我是「{display_model_name}」。",
            f"我是「{display_model_name}」。",
            f"我是{display_model_name}。",
            f"我是「{display_model_name}」，",
            f"我是{display_model_name}，",
        ]
        for prefix in identity_prefixes:
            if text.startswith(prefix):
                return text[len(prefix):].lstrip()
        return text

    def _looks_like_question_template(self, reply: str) -> bool:
        text = reply.strip()
        if not text:
            return True
        template_markers = [
            "图中哪些",
            "这张图",
            "图像证据",
            "管腔形态",
            "黏膜颜色",
            "皱襞",
            "部位定位依据",
            "先别急着选",
            "作答多选题",
            "标准答案",
        ]
        return any(marker in text for marker in template_markers)

    def _fallback_chat_reply(self, title: str, tags: list[str], message: str, display_model_name: str) -> str:
        intent = self._chat_intent(message)
        if intent == "identity":
            return f"我在当前研修界面中显示为「{display_model_name}」，用于陪你做内镜研修题、整理观察依据和复盘报告表达。"
        if intent == "capability":
            return "可以。我能陪你读当前内镜图像、梳理多选题的逐项依据、复盘错因，也能把你的观察整理成更稳妥的报告表达。"
        if intent == "greeting":
            return "你好，我在。你可以直接说你卡在部位、病变形态、选项排除，还是报告表述上。"
        return (
            f"围绕当前题“{title}”，建议你先拆成两步："
            f"找到可观察事实，再判断这些事实是否足以支持题干结论。"
            f"本题的关键训练标签是：{', '.join(tags)}。"
        )

    def challenge_benchmark(self, request: ChallengeBenchmarkRequest) -> dict[str, object]:
        question = question_service.get_question(request.question_id, request.learner_id, record_view=False)
        provider_result = llm_provider.chat(
            system_prompt=(
                "你是内镜医师训练平台的研修对照助手。"
                "只在题目给定选项中选择一个答案，并用一句话解释观察依据与限制。"
                "不要输出诊断、治疗建议或患者身份信息。"
            ),
            user_prompt=(
                f"题目标题：{question.title}\n"
                f"题干：{question.question}\n"
                f"可选答案：{' | '.join(question.options)}\n"
                "不要使用公开标注、标准答案或训练反馈；只根据题干、选项和随请求提供的图像判断。\n"
                "请严格按格式回答：答案=<从可选答案中原样复制一个>; 理由=<一句中文观察依据说明>。"
            ),
            image_path=question.image_url,
            temperature=0.0,
            max_tokens=180,
        )
        generation_mode = "public_annotation"
        benchmark_answer = question.ai_benchmark_answer or question.answer
        rationale = "当前未调用独立模型，使用公开标注作为挑战基准。"
        benchmark_name = "研修对照样例（公开标注预览）"
        if provider_result.ok:
            parsed_answer = self._parse_provider_choice(provider_result.text, question.options)
            if parsed_answer:
                generation_mode = "provider"
                benchmark_answer = parsed_answer
                benchmark_name = "智能服务研修对照"
                rationale = provider_result.text[:220]
            else:
                rationale = f"智能服务已返回但未能严格映射到题目选项，已回到公开标注预览：{provider_result.text[:160]}"
                benchmark_name = "研修对照样例（智能服务未能映射，公开标注预览）"
        elif provider_result.error and provider_result.error != "provider_not_configured":
            rationale = "智能服务研修对照暂未完成，已回到公开标注预览。"
        response = ChallengeBenchmarkResponse(
            id=f"challenge_{uuid4().hex[:12]}",
            question_id=question.id,
            benchmark_name=benchmark_name,
            benchmark_answer=benchmark_answer,
            benchmark_correct=benchmark_answer == question.answer,
            doctor_selected_answer=request.selected_answer,
            same_as_doctor=benchmark_answer == request.selected_answer,
            generation_mode=generation_mode,
            provider_status=provider_result.public_status(),
            rationale=rationale,
            audit_logged=True,
            profile_updated=False,
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            created_at=now_iso(),
        )
        audit_service.log(
            "challenge_benchmark",
            user_id=request.learner_id,
            entity_id=question.id,
            summary=f"挑战基准完成；模式 {generation_mode}；不回灌医师画像。",
            risk_level="medium",
        )
        return response.model_dump()

    def _parse_provider_choice(self, text: str, options: list[str]) -> str | None:
        for option in options:
            if option in text:
                return option
        return None


tutor_orchestrator = TutorOrchestrator()
