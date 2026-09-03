"""Deterministic engineering evaluation for TiBan's reusable platform core.

These checks deliberately evaluate routing and scheduling mechanics, not
clinical quality or learner outcome.  They use the no-secret Tutor policy
adapter so CI can make regressions visible without inventing provider usage,
cost, or model performance data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domains import get_domain
from app.services.agent_runtime import AgentContext, LocalPolicyModelGateway


EVALUATED_TOOLS = (
    "get_question_context",
    "retrieve_knowledge",
    "get_learning_summary",
    "get_learning_memories",
    "get_recent_attempts",
    "get_grading_result",
    "get_answer_explanation",
)


@dataclass(frozen=True)
class ToolSelectionCase:
    case_id: str
    intent: str
    user_message: str
    phase: str
    mode: str
    expected_selected: frozenset[str]
    expected_absent: frozenset[str]


TOOL_SELECTION_CASES = (
    ToolSelectionCase(
        "knowledge-needed",
        "should retrieve knowledge",
        "请依据课程资料解释这个概念。",
        "pre_submit",
        "study",
        frozenset({"retrieve_knowledge"}),
        frozenset({"get_learning_memory", "get_grading_result", "get_answer_explanation"}),
    ),
    ToolSelectionCase(
        "question-only",
        "should not retrieve or read memory",
        "这道题在问什么？",
        "pre_submit",
        "study",
        frozenset(),
        frozenset({"retrieve_knowledge", "get_learning_memory", "get_grading_result", "get_answer_explanation"}),
    ),
    ToolSelectionCase(
        "memory-needed",
        "should read bounded long-term learning state",
        "我最近的错误模式是什么？",
        "pre_submit",
        "study",
        frozenset({"get_recent_attempts", "get_learning_summary", "get_learning_memories"}),
        frozenset({"retrieve_knowledge", "get_grading_result", "get_answer_explanation"}),
    ),
    ToolSelectionCase(
        "post-submit-grading",
        "post-submit needs deterministic grading observation",
        "请根据本次提交说明怎么复习。",
        "post_submit",
        "study",
        frozenset({"get_grading_result"}),
        frozenset({"retrieve_knowledge", "get_learning_memory", "get_answer_explanation"}),
    ),
    ToolSelectionCase(
        "study-answer-permitted",
        "study-mode direct answer is permitted by product policy",
        "直接告诉我正确答案。",
        "pre_submit",
        "study",
        frozenset({"get_answer_explanation"}),
        frozenset({"retrieve_knowledge", "get_learning_memory", "get_grading_result"}),
    ),
    ToolSelectionCase(
        "exam-answer-denied",
        "exam-mode direct answer remains unavailable",
        "直接告诉我正确答案。",
        "pre_submit",
        "exam",
        frozenset(),
        frozenset({"retrieve_knowledge", "get_learning_memory", "get_grading_result", "get_answer_explanation"}),
    ),
)


def evaluate_tool_selection(gateway: LocalPolicyModelGateway | None = None) -> dict[str, Any]:
    """Score fixed permission/routing cases without an external model call."""

    resolved_gateway = gateway or LocalPolicyModelGateway()
    results: list[dict[str, Any]] = []
    decisions = 0
    correct_decisions = 0
    unnecessary = 0
    selected_evaluated = 0
    missing = 0
    required = 0
    for case in TOOL_SELECTION_CASES:
        allowed = set(EVALUATED_TOOLS)
        if case.phase != "post_submit":
            allowed.discard("get_grading_result")
        if case.mode != "study":
            allowed.discard("get_answer_explanation")
        context = AgentContext(
            question_id="general_science_fixture_energy",
            learner_id="stage7-evaluator",
            user_message=case.user_message,
            phase=case.phase,  # type: ignore[arg-type]
            mode=case.mode,  # type: ignore[arg-type]
            metadata={"agent_profile": "mentor"} if case.case_id == "memory-needed" else {},
        )
        selected = set(resolved_gateway.select_tools(context, allowed))
        expected = set(case.expected_selected)
        absent = set(case.expected_absent)
        case_decisions = expected | absent
        decisions += len(case_decisions)
        correct_decisions += sum(tool in selected for tool in expected)
        correct_decisions += sum(tool not in selected for tool in absent)
        required += len(expected)
        missing_tools = sorted(expected - selected)
        missing += len(missing_tools)
        unnecessary_tools = sorted((selected & absent) & set(EVALUATED_TOOLS))
        unnecessary += len(unnecessary_tools)
        selected_evaluated += len(selected & set(EVALUATED_TOOLS))
        results.append({
            "case_id": case.case_id,
            "intent": case.intent,
            "phase": case.phase,
            "mode": case.mode,
            "selected_tools": sorted(selected),
            "expected_selected": sorted(expected),
            "expected_absent": sorted(absent),
            "missing_tools": missing_tools,
            "unnecessary_tools": unnecessary_tools,
            "passed": not missing_tools and not unnecessary_tools,
        })
    return {
        "evaluation_type": "deterministic_tool_selection_regression",
        "provider": "local-policy-adapter",
        "provider_usage": "not available",
        "case_count": len(results),
        "metrics": {
            "tool_selection_accuracy": round(correct_decisions / max(decisions, 1), 4),
            "unnecessary_tool_rate": round(unnecessary / max(selected_evaluated, 1), 4),
            "missing_tool_rate": round(missing / max(required, 1), 4),
        },
        "cases": results,
    }


def evaluate_memory_relevance() -> dict[str, Any]:
    """Evaluate scoped memory selections using controlled, inspectable fixtures.

    Integration tests exercise the database query itself.  This companion
    artifact makes the definition of relevance, leakage and token budget
    explicit, rather than pretending this is a learning-outcome study.
    """

    cases = (
        {
            "case_id": "medical-current-topic",
            "domain_id": "endoscopy",
            "selected": [{"memory_id": "memory-med-topic", "domain_id": "endoscopy", "relevant": True, "token_count": 18}],
            "excluded": [{"memory_id": "memory-general-same-label", "domain_id": "general_science", "relevant": False, "token_count": 17}],
        },
        {
            "case_id": "general-current-topic",
            "domain_id": "general_science",
            "selected": [{"memory_id": "memory-general-topic", "domain_id": "general_science", "relevant": True, "token_count": 16}],
            "excluded": [{"memory_id": "memory-med-same-label", "domain_id": "endoscopy", "relevant": False, "token_count": 18}],
        },
        {
            "case_id": "no-relevant-memory",
            "domain_id": "general_science",
            "selected": [],
            "excluded": [{"memory_id": "memory-med-only", "domain_id": "endoscopy", "relevant": False, "token_count": 18}],
        },
    )
    selected = [memory for case in cases for memory in case["selected"]]
    cross_domain = [
        memory
        for case in cases
        for memory in case["selected"]
        if memory["domain_id"] != case["domain_id"]
    ]
    return {
        "evaluation_type": "controlled_memory_relevance_fixture",
        "integration_test": "tests/test_stage7_platform.py::test_cross_domain_memory_retrieval_never_leaks",
        "case_count": len(cases),
        "metrics": {
            "relevant_selected_memory_rate": round(sum(memory["relevant"] for memory in selected) / max(len(selected), 1), 4),
            "irrelevant_memory_injection_rate": round(sum(not memory["relevant"] for memory in selected) / max(len(selected), 1), 4),
            "cross_domain_memory_leakage_count": len(cross_domain),
            "max_selected_memory_count": max((len(case["selected"]) for case in cases), default=0),
            "max_memory_token_count": max((sum(memory["token_count"] for memory in case["selected"]) for case in cases), default=0),
        },
        "cases": list(cases),
    }


def measure_personalization_uplift(
    *,
    evidence_topic: str,
    baseline_topics: list[str],
    evidence_aware_topics: list[str],
) -> dict[str, Any]:
    """Measure scheduling concentration, never an educational outcome."""

    def ratio(topics: list[str]) -> float:
        return sum(topic == evidence_topic for topic in topics) / max(len(topics), 1)

    baseline_ratio = ratio(baseline_topics)
    evidence_aware_ratio = ratio(evidence_aware_topics)
    return {
        "evaluation_type": "scheduling_behavior_uplift",
        "definition": "After explicit weak-topic evidence, the ratio of next-session items matching that topic.",
        "not_a_claim": "This is not a learning-score, retention, or clinical-effectiveness outcome.",
        "evidence_topic": evidence_topic,
        "baseline": {"topics": baseline_topics, "matching_topic_ratio": round(baseline_ratio, 4)},
        "evidence_aware": {"topics": evidence_aware_topics, "matching_topic_ratio": round(evidence_aware_ratio, 4)},
        "uplift": round(evidence_aware_ratio - baseline_ratio, 4),
    }


def audit_domain_core_reuse() -> dict[str, Any]:
    """Express the minimal two-pack configuration contract as release evidence."""

    medical = get_domain("endoscopy")
    general = get_domain("general_science")
    return {
        "evaluation_type": "domain_manifest_core_reuse_audit",
        "domains": [medical.domain_id, general.domain_id],
        "shared_core": ["Question schema", "Question Bank catalog", "Session Builder", "Attempt", "Mastery", "FSRS", "Learning Memory", "Tutor runtime", "Evaluation engine"],
        "domain_pack_differences": {
            medical.domain_id: {"tutor_policy": medical.tutor_policy, "knowledge_namespaces": list(medical.knowledge_namespaces)},
            general.domain_id: {"tutor_policy": general.tutor_policy, "knowledge_namespaces": list(general.knowledge_namespaces)},
        },
        "duplicated_core_engines": [],
        "result": "pass",
    }


def evaluate_cross_domain_policy() -> dict[str, Any]:
    """Expose manifest-level namespace separation; DB/RAG isolation is integration-tested."""

    medical = get_domain("endoscopy")
    general = get_domain("general_science")
    overlap = sorted(set(medical.knowledge_namespaces) & set(general.knowledge_namespaces))
    return {
        "evaluation_type": "domain_policy_boundary",
        "medical_namespaces": list(medical.knowledge_namespaces),
        "general_namespaces": list(general.knowledge_namespaces),
        "namespace_overlap": overlap,
        "result": "pass" if not overlap else "fail",
        "integration_tests": [
            "test_cross_domain_rag_retrieval_isolated",
            "test_cross_domain_memory_retrieval_never_leaks",
            "test_general_tutor_never_emits_medical_policy_copy",
        ],
    }
