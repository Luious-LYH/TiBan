"""Run the Stage 7 Docker acceptance against an already-started compose stack.

This is an acceptance probe, not a fixture generator.  It records only stable
IDs, lifecycle states, event names and metrics; question text, uploaded source
content and credentials are intentionally excluded from the artifact.
"""

from __future__ import annotations

import argparse
import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc


def get_json(base_url: str, path: str, query: dict[str, str] | None = None) -> dict[str, Any]:
    suffix = f"?{urlencode(query)}" if query else ""
    return request_json(base_url, "GET", f"{path}{suffix}")


def tutor_event_types(base_url: str, question_id: str, learner_id: str, *, attempt_id: str | None = None) -> dict[str, Any]:
    request_body: dict[str, Any] = {
        "question_id": question_id,
        "learner_id": learner_id,
        "message": "请解释当前题目的概念与依据。" if attempt_id is None else "请根据公开反馈帮助我复盘。",
        "mode": "study",
    }
    if attempt_id:
        request_body["attempt_id"] = attempt_id
    body = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/api/v3/tutor/stream",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    events: list[str] = []
    raw_frames: list[dict[str, Any]] = []
    with urlopen(request, timeout=180) as response:
        for line in response:
            decoded = line.decode("utf-8", errors="replace").strip()
            if decoded.startswith("event: "):
                events.append(decoded[7:])
            elif decoded.startswith("data: "):
                try:
                    value = json.loads(decoded[6:])
                except json.JSONDecodeError:
                    value = {}
                if isinstance(value, dict):
                    raw_frames.append(value)
    return {
        "event_types": events,
        "has_message_start": "message_start" in events,
        "has_message_end": "message_end" in events,
        "has_source": "source" in events,
        "has_error": "error" in events,
        "frame_count": len(raw_frames),
        "provider_real": next((frame.get("provider_real") for frame in raw_frames if "provider_real" in frame), False),
    }


def select_answer(question: dict[str, Any]) -> str | bool | list[str]:
    question_type = question.get("question_type")
    if question_type == "true_false":
        return False
    options = question.get("options") or []
    if question_type == "multiple_choice":
        return [str(options[0]["id"])] if options else []
    if options:
        return str(options[0]["id"])
    return "依据题干给出的条件进行判断。"


def practice_flow(base_url: str, domain_id: str, bank_id: str) -> dict[str, Any]:
    learner_id = f"stage7-docker-{domain_id}"
    session = request_json(base_url, "POST", "/api/v3/practice/sessions", {
        "learner_id": learner_id,
        "bank_id": bank_id,
        "mode": "study",
        "question_count": 1,
        "shuffle_seed": 20260831,
    })
    questions = get_json(base_url, "/api/v3/practice/questions", {"session_id": session["session_id"]})
    question = questions["items"][0]
    pre_tutor = tutor_event_types(base_url, question["id"], learner_id)
    submitted = request_json(base_url, "POST", "/api/v3/practice/submit", {
        "learner_id": learner_id,
        "question_id": question["id"],
        "session_id": session["session_id"],
        "selected_answer": select_answer(question),
        "mode": "study",
    })
    reviewed = request_json(base_url, "POST", "/api/v3/learning/review", {
        "learner_id": learner_id,
        "question_id": question["id"],
        "rating": "Good",
    })
    post_tutor = tutor_event_types(base_url, question["id"], learner_id, attempt_id=submitted["attempt_id"])
    memory = get_json(base_url, "/api/v3/learning/memory", {"learner_id": learner_id, "domain_id": domain_id})
    mentor = get_json(base_url, "/api/v3/learning/mentor", {"learner_id": learner_id, "domain_id": domain_id})
    return {
        "domain_id": domain_id,
        "bank_id": bank_id,
        "session_id": session["session_id"],
        "question_id": question["id"],
        "question_type": question["question_type"],
        "tutor_pre_submit": pre_tutor,
        "attempt_id": submitted["attempt_id"],
        "profile_updated": submitted["profile_updated"],
        "tutor_post_submit": post_tutor,
        "review_card": {
            "question_id": reviewed["item"]["question_id"],
            "domain_id": reviewed["item"]["domain_id"],
            "state": reviewed["item"]["state"],
            "review_count": reviewed["item"]["review_count"],
            "has_fsrs_difficulty": reviewed["item"]["difficulty"] is not None,
            "has_fsrs_stability": reviewed["item"]["stability"] is not None,
            "has_fsrs_retrievability": reviewed["item"]["retrievability"] is not None,
            "due_at": reviewed["item"]["due_at"],
        },
        "memory_item_count": len(memory.get("items", [])),
        "mentor_step_count": len(mentor.get("plan", {}).get("steps", [])),
    }


def factory_flow(base_url: str) -> dict[str, Any]:
    content = "# Acceptance teaching note\n\n## Observation boundary\n\nUse the supplied evidence and preserve uncertainty in a teaching review."
    document = request_json(base_url, "POST", "/api/v3/factory/documents", {
        "filename": "stage7-docker-acceptance.md",
        "content_base64": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "content_type": "text/markdown",
        "domain_id": "endoscopy",
    })["document"]
    queued = request_json(base_url, "POST", "/api/v3/factory/jobs", {"document_id": document["document_id"]})["item"]
    job: dict[str, Any] = {}
    for _ in range(90):
        job = get_json(base_url, f"/api/v3/factory/jobs/{queued['job_id']}")["item"]
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(1)
    published: dict[str, Any] | None = None
    if job.get("status") == "succeeded" and job.get("revisions"):
        revision_id = job["result_ref"]
        published = request_json(base_url, "POST", f"/api/v3/factory/jobs/{queued['job_id']}/publish", {"revision_id": revision_id})["item"]
        job = get_json(base_url, f"/api/v3/factory/jobs/{queued['job_id']}")["item"]
    return {
        "document_id": document["document_id"],
        "job_id": queued["job_id"],
        "terminal_status": job.get("status"),
        "terminal_stage": job.get("stage"),
        "attempt": job.get("attempt"),
        "event_statuses": [event.get("status") for event in job.get("detail", {}).get("events", [])],
        "revision_count": len(job.get("revisions", [])),
        "published": published is not None,
        "published_question_id": published.get("question_id") if published else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8005")
    parser.add_argument("--output", default="../artifacts/platform/docker-acceptance-v2.json")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    domains = get_json(base_url, "/api/v3/domains")["items"]
    banks_by_domain = {
        domain["domain_id"]: get_json(base_url, "/api/v3/question-banks", {"domain_id": domain["domain_id"]})["items"]
        for domain in domains
    }
    medical_bank = next(item for item in banks_by_domain["endoscopy"] if item["question_count"] > 0)
    general_bank = next(item for item in banks_by_domain["general_science"] if item["question_count"] > 0)
    datasets = get_json(base_url, "/api/v3/evaluation/datasets")["items"]
    medical_flow = practice_flow(base_url, "endoscopy", medical_bank["bank_id"])
    general_flow = practice_flow(base_url, "general_science", general_bank["bank_id"])
    factory_result = factory_flow(base_url)
    artifact = {
        "artifact": "stage7-docker-acceptance-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "health": get_json(base_url, "/api/health"),
        "domains": [{"domain_id": item["domain_id"], "supported_question_types": item["supported_question_types"]} for item in domains],
        "bank_inventory": {
            domain_id: [{"bank_id": item["bank_id"], "question_count": item["question_count"]} for item in banks]
            for domain_id, banks in banks_by_domain.items()
        },
        "practice_flows": [medical_flow, general_flow],
        "factory_flow": factory_result,
        "evaluation_catalog": [
            {"dataset_id": item["dataset_id"], "domain_id": item["domain_id"], "tutor_indexed": item["tutor_indexed"]}
            for item in datasets
        ],
        "acceptance": {
            "medical_flow": medical_flow["profile_updated"] and medical_flow["review_card"]["has_fsrs_stability"],
            "general_flow": general_flow["profile_updated"] and general_flow["review_card"]["has_fsrs_stability"],
            "factory_flow": factory_result["terminal_status"] == "succeeded" and factory_result["published"],
            "evaluation_catalog": {"endoscopy", "general_science"}.issubset({item["domain_id"] for item in datasets}),
        },
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "acceptance": artifact["acceptance"]}, ensure_ascii=False))
    if not all(artifact["acceptance"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
