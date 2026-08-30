"""OpenAI-compatible Tutor provider adapter."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import SAFETY_NOTICE
from app.application.errors import normalize_provider_error
from app.services.agent_runtime import AgentContext
from app.services.llm_provider import llm_provider


class OpenAICompatibleTutorGateway:
    """Opt-in adapter over the internal OpenAI-compatible provider client."""

    name = "openai-compatible-tutor"

    def select_tools(self, context: AgentContext, available_tools: set[str]) -> list[str]:
        result = llm_provider.chat(
            system_prompt=(
                "You are a medical education tutor tool planner. Return JSON only: "
                '{"tools":[...]} . Select only names in the allowed list. '
                "Never request hidden rubrics, diagnosis, or write actions. "
                "get_learning_memory is read-only and current-learner-only. "
                "get_answer_explanation is permitted only for explicit Study-mode, pre-submit answer requests."
            ),
            user_prompt=json.dumps({"user_message": context.user_message, "phase": context.phase, "mode": context.mode, "allowed_tools": sorted(available_tools)}, ensure_ascii=False),
            temperature=0,
            max_tokens=120,
        )
        if not result.ok:
            raise normalize_provider_error(result.error)
        try:
            names = json.loads(result.text).get("tools", [])
        except (json.JSONDecodeError, AttributeError) as exc:
            raise RuntimeError("provider_tool_plan_not_json") from exc
        return [str(name) for name in names if str(name) in available_tools]

    def compose(self, context: AgentContext, observations: dict[str, Any]) -> str:
        result = llm_provider.chat(
            system_prompt=(
                "You are a safe Chinese medical education tutor. Use only supplied observations. "
                "Never reveal answers in Exam mode, hidden rubrics, or hidden reasoning. "
                "Do not provide diagnosis or treatment. Give concise evidence-based teaching with supplied source labels. "
                f"Include this boundary: {SAFETY_NOTICE}"
            ),
            user_prompt=json.dumps({"user_message": context.user_message, "phase": context.phase, "mode": context.mode, "observations": observations, "recent_conversation": context.metadata.get("conversation", [])[-12:]}, ensure_ascii=False),
            temperature=0.2,
            max_tokens=420,
        )
        if not result.ok:
            raise normalize_provider_error(result.error)
        return result.text
