"""Create reproducible Stage 5 personalization artifacts on an isolated DB."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.bootstrap import initialize_database
from app.db.models import QuestionModel, ReviewCardModel
from app.schemas import PracticeSubmitRequest
from app.services.agent_runtime import AgentContext, tutor_runner
from app.services.learning_memory_service import learning_memory_service, topic_keys_for_question
from app.services.stage1_service import stage1_service


def _events(learner_id: str, question_id: str) -> dict[str, Any]:
    events = list(tutor_runner.stream(AgentContext(
        question_id=question_id,
        learner_id=learner_id,
        user_message="请解释这个知识点，并给我一个复习提示。",
        phase="pre_submit",
    )))
    end = next(event for event in events if event.event == "message_end")
    return {
        "tool_names": [str(event.data["tool_name"]) for event in events if event.event == "tool_start"],
        "trace": end.data.get("trace", {}),
        "response_preview": "".join(str(event.data.get("text", "")) for event in events if event.event == "token")[:300],
    }


def _submit_wrong(learner_id: str, question_id: str) -> None:
    stage1_service.submit(PracticeSubmitRequest(
        learner_id=learner_id,
        question_id=question_id,
        selected_answer="__evidence_wrong__",
        mode="study",
    ))


def _defer_cards(learner_id: str) -> None:
    with SessionLocal() as session:
        for card in session.scalars(select(ReviewCardModel).where(ReviewCardModel.learner_id == learner_id)):
            card.due_at = datetime.utcnow() + timedelta(days=7)
        session.commit()


def _memory(learner_id: str, question_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        return learning_memory_service.retrieve_relevant(
            session,
            learner_id=learner_id,
            question_id=question_id,
            user_message="请解释这个知识点，并给我一个复习提示。",
        )


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value)) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="../artifacts/memory")
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    learner_before_after = "evidence_same_learner"
    learner_a = "evidence_learner_a"
    learner_b = "evidence_learner_b"

    # The artifact must run from a fresh local database, not rely on a
    # developer's accumulated experimental QBank or learner state.
    initialize_database()

    with SessionLocal() as session:
        questions = list(session.scalars(select(QuestionModel).where(QuestionModel.business_usage == "user_ready").order_by(QuestionModel.question_id)))
        if len(questions) < 2:
            raise RuntimeError("The compact teaching seed must include at least two learner-ready questions.")
        first = questions[0]
        first_keys = {item.casefold() for item in topic_keys_for_question(first)}
        second = next(
            (item for item in questions[1:] if not (first_keys & {key.casefold() for key in topic_keys_for_question(item)})),
            questions[1],
        )

    before = {
        "memory": _memory(learner_before_after, first.question_id),
        "tutor": _events(learner_before_after, first.question_id),
        "next_session": stage1_service.create_session(learner_before_after, first.bank_id, question_count=2, shuffle_seed=11),
    }
    for _ in range(3):
        _submit_wrong(learner_before_after, first.question_id)
    _defer_cards(learner_before_after)
    after = {
        "memory": _memory(learner_before_after, first.question_id),
        "tutor": _events(learner_before_after, first.question_id),
        "next_session": stage1_service.create_session(learner_before_after, first.bank_id, question_count=2, shuffle_seed=11),
    }
    before_after_assertions = {
        "memory_changed": not before["memory"]["selected_memory_ids"] and bool(after["memory"]["selected_memory_ids"]),
        "tutor_context_changed": before["tutor"]["trace"]["selected_memory_ids"] != after["tutor"]["trace"]["selected_memory_ids"],
        "session_selection_changed": before["next_session"]["selection_strategy"] != after["next_session"]["selection_strategy"],
    }
    _write(output_dir / "personalization-before-after-v1.json", {
        "artifact": "personalization-before-after-v1",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "learner_id": learner_before_after,
        "question_id": first.question_id,
        "before": before,
        "after": after,
        "assertions": before_after_assertions,
        "raw_chain_of_thought_stored": False,
    })

    for _ in range(3):
        _submit_wrong(learner_a, first.question_id)
        _submit_wrong(learner_b, second.question_id)
    _defer_cards(learner_a)
    _defer_cards(learner_b)
    plan_a = stage1_service.create_session(learner_a, first.bank_id, question_count=2, shuffle_seed=17)
    plan_b = stage1_service.create_session(learner_b, second.bank_id, question_count=2, shuffle_seed=17)
    differentiation_assertions = {
        "learner_isolation": not set(_memory(learner_a, first.question_id)["selected_memory_ids"]) & set(_memory(learner_b, second.question_id)["selected_memory_ids"]),
        "different_memory_focus": _memory(learner_a, first.question_id)["items"] != _memory(learner_b, second.question_id)["items"],
        "different_selection_reason": plan_a["selection_evidence"] != plan_b["selection_evidence"],
    }
    _write(output_dir / "two-learner-differentiation-v1.json", {
        "artifact": "two-learner-differentiation-v1",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "request": "安排下一轮 20 题（实际受 compact seed 可用题量限制）",
        "learner_a": {
            "focus_question_id": first.question_id,
            "memory": _memory(learner_a, first.question_id),
            "next_session": plan_a,
        },
        "learner_b": {
            "focus_question_id": second.question_id,
            "memory": _memory(learner_b, second.question_id),
            "next_session": plan_b,
        },
        "assertions": differentiation_assertions,
    })
    if not all(before_after_assertions.values()) or not all(differentiation_assertions.values()):
        raise SystemExit("Memory personalization evidence assertions failed")


if __name__ == "__main__":
    main()
