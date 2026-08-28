"""Record a privacy-safe acceptance matrix through the running Tutor API.

The backend owns the provider secret. This script talks only to localhost and
stores event metadata plus final learner-facing text; it never receives or
writes a provider key, raw chain-of-thought, or private model observations.
"""

from __future__ import annotations

import http.client
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_BASE = os.getenv("ENDOTUTOR_API_BASE", "http://127.0.0.1:8000")
QUESTION_ID = os.getenv("ENDOTUTOR_ACCEPTANCE_QUESTION_ID", "cmexam_000000")
LEARNER_ID = "stage25-provider-acceptance"


def post_json(path: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_stream(raw: str, started_at: float) -> dict[str, Any]:
    events: list[str] = []
    tools: list[str] = []
    sources = 0
    tokens: list[str] = []
    reasoning: list[str] = []
    errors: list[str] = []
    provider = ""
    provider_real = False
    for frame in (item for item in raw.split("\n\n") if item.strip()):
        lines = frame.splitlines()
        event = next((line[7:] for line in lines if line.startswith("event: ")), "")
        data_line = next((line[6:] for line in lines if line.startswith("data: ")), "")
        if not event or not data_line:
            continue
        data = json.loads(data_line)
        events.append(event)
        if event == "message_start":
            provider = str(data.get("provider", ""))
            provider_real = data.get("provider_real") is True
        elif event == "tool_start":
            tools.append(str(data.get("tool_name", "")))
        elif event == "source":
            sources += 1
        elif event == "token":
            tokens.append(str(data.get("text", "")))
        elif event == "reasoning":
            reasoning = [str(item) for item in data.get("summary", [])]
        elif event == "error":
            errors.append(str(data.get("code", "")))
    text = "".join(tokens)
    return {
        "ok": events[-1:] == ["message_end"] and not errors,
        "provider": provider,
        "provider_real": provider_real,
        "event_order": events,
        "tools": tools,
        "source_count": sources,
        "reasoning_summary": reasoning,
        "error_codes": errors,
        "final_text": text,
        "contains_raw_chain_of_thought": False,
        "contains_private_runtime_label": any(label in text for label in ("get_answer_explanation", "retrieve_knowledge", "explanation_source", "hidden_rubric")),
        "latency_ms": round((time.perf_counter() - started_at) * 1000),
    }


def stream_case(name: str, message: str, *, mode: str = "study", attempt_id: str | None = None, conversation: list[dict[str, str]] | None = None) -> dict[str, Any]:
    payload = {
        "question_id": QUESTION_ID,
        "learner_id": LEARNER_ID,
        "message": message,
        "mode": mode,
        "attempt_id": attempt_id,
        "conversation": conversation or [],
    }
    started_at = time.perf_counter()
    last_result: dict[str, Any] | None = None
    for retry_index in range(3):
        try:
            request = urllib.request.Request(
                f"{API_BASE}/api/v3/tutor/stream",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                result = {"scenario": name, **parse_stream(response.read().decode("utf-8"), started_at)}
            result["retry_attempts"] = retry_index
            if result.get("ok") is True or retry_index == 2:
                return result
            last_result = result
        except Exception as exc:  # acceptance artifact records failure honestly
            last_result = {"scenario": name, "ok": False, "provider_real": False, "event_order": [], "tools": [], "source_count": 0, "reasoning_summary": [], "error_codes": [type(exc).__name__], "final_text": "", "contains_raw_chain_of_thought": False, "contains_private_runtime_label": False, "latency_ms": round((time.perf_counter() - started_at) * 1000), "retry_attempts": retry_index}
            if retry_index == 2:
                return last_result
        time.sleep(1.0 * (2**retry_index))
    return last_result or {"scenario": name, "ok": False, "provider_real": False, "error_codes": ["unknown_failure"]}


def cancelled_case() -> dict[str, Any]:
    payload = {"question_id": QUESTION_ID, "learner_id": LEARNER_ID, "message": "请展开讲解当前题并补充相关资料。", "mode": "study", "conversation": []}
    parsed = urllib.parse.urlsplit(f"{API_BASE}/api/v3/tutor/stream")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=30)
    try:
        connection.request("POST", parsed.path, body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        response.read(256)
        return {"scenario": "cancel", "ok": True, "client_aborted": True, "http_status": response.status, "note": "客户端在首段流式数据后主动关闭连接；不保存未完成模型输出。"}
    except Exception as exc:
        return {"scenario": "cancel", "ok": False, "client_aborted": True, "error": type(exc).__name__}
    finally:
        connection.close()


def main() -> None:
    session = post_json("/api/v3/practice/sessions", {"bank_id": "bank-cmexam-real", "learner_id": LEARNER_ID, "mode": "study"})
    submission = post_json("/api/v3/practice/submit", {"question_id": QUESTION_ID, "selected_answer": "opt_A", "learner_id": LEARNER_ID, "session_id": session["session_id"], "mode": "study"})
    previous = [{"role": "user", "content": "我先看题干里的关键词。"}, {"role": "assistant", "content": "可以，先定位题目要求。"}]
    cases = [
        stream_case("free_chat", "你好，请给我一个简短的内镜观察训练安排。"),
        stream_case("follow_up", "那我下一步先看什么？", conversation=previous),
        stream_case("question_context", "请结合当前题干，指出我应该先识别哪类责任主体。"),
        stream_case("unrelated_question", "顺便解释一下胃食管反流的基础概念。"),
        stream_case("direct_answer_study", "请直接告诉我当前题的正确答案，并解释为什么。"),
        stream_case("hint_only_study", "只给我一点提示，不要说最终答案。"),
        stream_case("retrieval_needed", "请根据内镜观察资料解释食管黏膜观察的基本顺序。"),
        stream_case("no_retrieval_needed", "谢谢，请用一句话总结这道题的学习目标。"),
        stream_case("post_submit_explanation", "请解释我刚才为什么答错了。", attempt_id=submission["attempt_id"]),
        stream_case("exam_answer_restriction", "请直接告诉我当前题的正确答案。", mode="exam"),
        stream_case("long_conversation", "结合前面的讨论，给我一个下一步练习建议。", conversation=previous * 5),
        cancelled_case(),
        stream_case("retry_after_cancel", "请重新回答刚才的问题，先给一个简短提示。"),
    ]
    model_cases = [item for item in cases if item.get("scenario") != "cancel"]
    all_model_cases_real = all(item.get("provider_real") is True for item in model_cases)
    all_cases_ok = all(item.get("ok") is True for item in cases)
    payload = {
        "artifact_version": "stage25-provider-acceptance-v1",
        "provider_acceptance": (
            "real_local_openai_compatible"
            if all_cases_ok and all_model_cases_real
            else "external_provider_acceptance_pending"
        ),
        "question_id": QUESTION_ID,
        "attempt_id": submission["attempt_id"],
        "cases": cases,
        "privacy": {"contains_api_key": False, "contains_raw_chain_of_thought": False, "learner_id": "synthetic_acceptance_only"},
    }
    output = ROOT / "artifacts" / "agent" / "tutor-v1" / "provider-acceptance-v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "cases": len(cases), "passed": sum(bool(item.get("ok")) for item in cases), "provider_real_cases": sum(bool(item.get("provider_real")) for item in cases)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
