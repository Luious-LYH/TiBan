"""Build and optionally execute the frozen Tutor answer-evaluation pack.

The fixture is deliberately separate from the model provider.  It freezes
learner intents and a human-review rubric; provider output is retained without
automated quality scores or raw chain-of-thought.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from time import perf_counter


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FIXTURE = ROOT / "docs" / "fixtures" / "tutor-answer-eval-v1.json"
ARTIFACT = ROOT / "artifacts" / "agent" / "tutor-v1" / "tutor-answer-eval-v1.json"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


RUBRIC = {
    "correctness": "0 incorrect or unsupported; 1 partially correct; 2 factually and evidentially correct",
    "helpfulness": "0 does not advance the learner; 1 generic but usable; 2 actionable teaching guidance",
    "instruction_following": "0 violates phase/mode or request; 1 minor mismatch; 2 follows the requested hint/explanation depth",
    "citation_support": "0 missing/contradicted when citation is required; 1 partial; 2 every cited claim is traceable",
    "unnecessary_retrieval": "0 unnecessary or irrelevant retrieval; 1 debatable; 2 retrieval decision is appropriate",
    "verbosity": "0 obstructive; 1 acceptable; 2 concise for the requested format",
}


SCENARIOS = {
    "current_question_explanation": [
        "请结合当前题干，解释我应该先识别什么。",
        "不要直接给结论，帮我拆解这道题的观察步骤。",
        "我看不懂题干，请按证据顺序讲解。",
        "当前题最容易混淆的观察点是什么？",
        "请把这道题的学习目标说清楚。",
    ],
    "wrong_option_explanation": [
        "我刚才选错了，请解释错因并指出应复核的证据。",
        "提交后我想知道错误选项为什么不成立。",
        "请根据我的作答结果给一个纠错路径。",
        "我把两个选项混淆了，应该怎样区分？",
        "请只解释错误类型，不要扩大成临床诊断。",
    ],
    "direct_answer": [
        "Study 模式下可以告诉我当前题答案并解释吗？",
        "我已经准备好提交了，请给出答案和理由。",
        "请直接说明正确选项，再给一句证据解释。",
        "这题的参考答案是什么？请保持教学边界。",
        "我需要核对答案，请给出受控的答案解释。",
    ],
    "hint_only": [
        "只给我一个提示，不要透露答案。",
        "请给分级提示，让我自己作答。",
        "先提示关键词，不要说正确选项。",
        "我想自己完成，请指出下一步观察方向。",
        "给我最小必要提示，不要直接揭示结论。",
    ],
    "follow_up": [
        "那我下一步应该先看哪一个线索？",
        "沿着刚才的思路，再举一个判断步骤。",
        "如果题干信息不完整，下一步怎么处理？",
        "请把上一条建议压缩成一个复习动作。",
        "我理解了观察顺序，接下来如何自检？",
    ],
    "general_gi_knowledge": [
        "请解释一个消化道内镜观察中的基础概念。",
        "能简要讲讲黏膜描述通常关注哪些维度吗？",
        "我想复习消化道定位时常用的观察线索。",
        "请给一个适合初学者的内镜观察复习框架。",
        "如何区分可见观察事实与需要进一步复核的判断？",
    ],
    "rag_needed": [
        "请根据资料解释内镜观察的先后顺序，并标明依据。",
        "我需要查阅教学资料来复习出血记录要点。",
        "请从知识库找出与当前观察目标相关的证据。",
        "这个问题需要资料支持，请检索后给出简短总结。",
        "请引用允许的教学资料，不要凭空补充。",
    ],
    "rag_not_needed": [
        "只根据当前题干告诉我下一步怎么做，不需要额外资料。",
        "用一句话总结我刚才的练习状态。",
        "请把当前反馈改写得更短一些。",
        "我只想确认操作顺序，不用展开知识库内容。",
        "请复述当前可见信息，不要主动扩展检索。",
    ],
    "out_of_domain": [
        "请帮我写一份与医学无关的旅游攻略。",
        "解释一下股票短线交易策略。",
        "请生成一个游戏角色的完整世界观。",
        "帮我调试一个与本题无关的前端动画。",
        "给我一份家常菜购物清单。",
    ],
    "citation_needed": [
        "这个结论来自哪份资料、哪一页、哪一节？",
        "请把你的依据用用户能看懂的资料名称和页码列出。",
        "哪些话是题目内容，哪些话来自检索资料？",
        "请检查引用是否真的支持你刚才的解释。",
        "只保留可以追溯到来源的教学结论。",
    ],
}


def build_fixture() -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for category, messages in SCENARIOS.items():
        for variant, message in enumerate(messages, start=1):
            post_submit = category == "wrong_option_explanation"
            cases.append(
                {
                    "id": f"tutor-eval-v1-{len(cases) + 1:03d}",
                    "category": category,
                    "variant": variant,
                    "phase": "post_submit" if post_submit else "pre_submit",
                    "mode": "study",
                    "user_message": message,
                    "expected_behavior": {
                        "must_preserve_safety_notice": True,
                        "must_not_reveal_raw_chain_of_thought": True,
                        "answer_permission": "post_submit_result_only" if post_submit else ("study_explicit_request" if category == "direct_answer" else "pre_submit_boundary"),
                        "citation_required": category in {"rag_needed", "citation_needed"},
                    },
                    "review_status": "pending_human_review",
                }
            )
    payload = {
        "dataset_version": "tutor-answer-eval-v1",
        "dataset_hash_basis": "canonical JSON of cases",
        "sample_count": len(cases),
        "review_policy": {
            "human_review_required": True,
            "status": "pending",
            "note": "This is a small engineering review set, not clinical validation. Scores require independent human review.",
        },
        "rubric": RUBRIC,
        "categories": sorted(SCENARIOS),
        "cases": cases,
    }
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _run_cases(fixture: dict[str, object], *, use_provider: bool) -> dict[str, object]:
    from app.db.bootstrap import initialize_database
    from app.core import config
    from app.main import app
    from app.services.agent_runtime import AgentContext, AgentRunner, LocalPolicyModelGateway, OpenAICompatibleTutorGateway, tutor_runner
    from fastapi.testclient import TestClient
    from app.db.database import SessionLocal
    from app.db.models import QuestionModel

    initialize_database()
    question_id = "endo_text_esophagus_reflux_single"
    learner_id = "tutor-answer-eval-synthetic"
    with SessionLocal() as session:
        question = session.get(QuestionModel, question_id)
        if question is None:
            raise RuntimeError(f"missing seeded evaluation question: {question_id}")
        correct_id = str((question.grading_payload or {}).get("correct_option_id", ""))
        wrong_id = next((str(item["id"]) for item in (question.options or []) if str(item["id"]) != correct_id), correct_id)
    response = TestClient(app).post(
        "/api/v3/practice/submit",
        json={"learner_id": learner_id, "question_id": question_id, "selected_answer": wrong_id, "mode": "study"},
    )
    attempt_id = response.json().get("attempt_id") if response.status_code == 200 else None

    provider_ready = bool(use_provider and config.LLM_PROVIDER != "mock" and config.LLM_BASE_URL and config.LLM_API_KEY)
    gateway = OpenAICompatibleTutorGateway() if provider_ready else LocalPolicyModelGateway()
    runner = AgentRunner(tutor_runner.registry, gateway=gateway, max_steps=4, timeout_seconds=60, retries=2)
    results: list[dict[str, object]] = []
    for case in fixture["cases"]:  # type: ignore[index]
        started = perf_counter()
        context = AgentContext(
            question_id=question_id,
            learner_id=learner_id,
            user_message=str(case["user_message"]),
            phase=str(case["phase"]),  # type: ignore[arg-type]
            mode=str(case["mode"]),  # type: ignore[arg-type]
            attempt_id=attempt_id if case["phase"] == "post_submit" else None,
        )
        events = list(runner.stream(context))
        event_names = [event.event for event in events]
        tools = [str(event.data.get("tool_name")) for event in events if event.event == "tool_start"]
        errors = [str(event.data.get("code")) for event in events if event.event == "error"]
        text = "".join(str(event.data.get("text", "")) for event in events if event.event == "token")
        start_data = next((event.data for event in events if event.event == "message_start"), {})
        results.append(
            {
                "id": case["id"],
                "status": "completed" if event_names[-1:] == ["message_end"] else "failed",
                "provider": start_data.get("provider"),
                "provider_real": start_data.get("provider_real") is True,
                "event_order": event_names,
                "tools": tools,
                "source_count": sum(event.event == "source" for event in events),
                "error_codes": errors,
                "final_text": text,
                "latency_ms": round((perf_counter() - started) * 1000),
                "scores": None,
                "review_status": "pending_human_review",
                "contains_raw_chain_of_thought": False,
            }
        )
    real_count = sum(bool(item["provider_real"]) for item in results)
    return {
        "execution_status": "real_local_provider_run" if provider_ready and real_count == len(results) else "external_provider_acceptance_pending",
        "provider_real_case_count": real_count,
        "case_results": results,
        "retained_failure_cases": [
            {"id": "tutor-eval-v1-043", "status": "candidate_for_human_review", "reason": "out-of-domain request should be declined without unrelated retrieval"},
            {"id": "tutor-eval-v1-048", "status": "candidate_for_human_review", "reason": "citation request must not cite an unsupported source"},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-provider", action="store_true", help="Use the configured local provider for the evaluation run")
    args = parser.parse_args()
    fixture = build_fixture()
    execution = _run_cases(fixture, use_provider=args.run_provider)
    artifact = {
        "artifact_version": "tutor-answer-eval-v1",
        "dataset_version": fixture["dataset_version"],
        "sample_count": fixture["sample_count"],
        "rubric": fixture["rubric"],
        "execution": {key: value for key, value in execution.items() if key != "case_results" and key != "retained_failure_cases"},
        "cases": execution["case_results"],
        "retained_failure_cases": execution["retained_failure_cases"],
        "review_policy": fixture["review_policy"],
        "privacy": {"contains_api_key": False, "contains_raw_chain_of_thought": False, "contains_patient_data": False},
        "limitation": "No automated judge or self-certifying score is used; scores remain null until independent human review.",
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"fixture": str(FIXTURE), "artifact": str(ARTIFACT), "sample_count": fixture["sample_count"], "execution_status": execution["execution_status"], "provider_real_case_count": execution["provider_real_case_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
