"""Produce a deterministic, isolated proof of the Stage 1 adaptive loop.

The demo uses the canonical Attempt -> mastery -> ReviewCard projection and
the same Stage1Repository session builder as the application.  It uses an
in-memory SQLite database so the evidence run cannot mutate a developer's
runtime database or require Docker.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.database import Base  # noqa: E402
from app.db.models import AttemptModel, LearnerMasteryModel, QuestionBankModel, QuestionModel, ReviewCardModel  # noqa: E402
from app.db.repositories import Stage1Repository  # noqa: E402


LEARNER_ID = "adaptive-demo-learner"
BANK_ID = "adaptive-demo-bank"
FOCUS_ID = "adaptive-demo-topic-a-1"
SIBLING_ID = "adaptive-demo-topic-a-2"
COVERAGE_ID = "adaptive-demo-topic-b-1"


def _question(question_id: str, title: str, tags: list[str]) -> QuestionModel:
    return QuestionModel(
        question_id=question_id,
        bank_id=BANK_ID,
        domain_id="endoscopy",
        question_type="single_choice",
        modality="text",
        title=title,
        stem=f"{title} 的观察练习",
        case_summary="Stage 1 自适应闭环演示用的合成教学摘要。",
        image_url=None,
        image_alt=None,
        difficulty="easy",
        complexity=1,
        question_class="基础识别",
        task="观察训练",
        body_part="胃",
        source_type="synthetic_demo",
        source_dataset="stage1-adaptive-demo",
        citation_note="合成演示来源，不代表临床数据。",
        options=[{"id": "wrong", "text": "错误选项"}, {"id": "right", "text": "正确选项"}],
        grading_payload={"correct_option_id": "right"},
        explanation="演示题解析。",
        teaching_tags=tags,
        expected_keywords=[],
        false_premise=False,
        doctor_review_required=True,
        safety_notice="仅供教学研修或医生复核前辅助，不作为独立诊断依据。",
        business_usage="user_ready",
        answer_source="dataset_gold",
        explanation_source="none",
        official_explanation_available=False,
    )


def _state(session: Session) -> dict[str, object]:
    attempts = list(session.scalars(select(AttemptModel).where(AttemptModel.learner_id == LEARNER_ID).order_by(AttemptModel.created_at)))
    mastery = list(session.scalars(select(LearnerMasteryModel).where(LearnerMasteryModel.learner_id == LEARNER_ID).order_by(LearnerMasteryModel.knowledge_point)))
    cards = list(session.scalars(select(ReviewCardModel).where(ReviewCardModel.learner_id == LEARNER_ID).order_by(ReviewCardModel.question_id)))
    return {
        "attempts": [
            {"question_id": item.question_id, "correct": item.correct, "score": item.score, "error_tags": item.error_tags}
            for item in attempts
        ],
        "mastery": [
            {
                "knowledge_point": item.knowledge_point,
                "attempt_count": item.attempt_count,
                "mastery_score": item.mastery_score,
                "common_errors": item.common_errors,
            }
            for item in mastery
        ],
        "review_cards": [
            {
                "question_id": item.question_id,
                "due_at": item.due_at.isoformat(),
                "difficulty": item.difficulty,
                "stability": item.stability,
                "retrievability": item.retrievability,
                "state": item.fsrs_state,
            }
            for item in cards
        ],
    }


def main() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with SessionLocal() as session:
        session.add(
            QuestionBankModel(
                bank_id=BANK_ID,
                domain_id="endoscopy",
                name="Stage 1 自适应闭环演示题库",
                description="合成数据，仅用于工程证据。",
                version="stage1-demo-v1",
                status="published",
                question_count=3,
                question_type_counts={"single_choice": 3},
                modality_counts={"text": 3},
                body_parts=["胃"],
            )
        )
        session.add_all(
            [
                _question(FOCUS_ID, "Topic A 初始题", ["Topic A"]),
                _question(SIBLING_ID, "Topic A 巩固题", ["Topic A"]),
                _question(COVERAGE_ID, "Topic B 覆盖题", ["Topic B"]),
            ]
        )
        session.commit()
        repository = Stage1Repository(session)

        before_session, before_selection = repository.create_session(
            LEARNER_ID, BANK_ID, mode="study", question_count=2, shuffle_seed=20260829
        )
        before = _state(session)

        focus = session.get(QuestionModel, FOCUS_ID)
        assert focus is not None
        repository.record_attempt(
            session=before_session,
            question=focus,
            selected_answer="wrong",
            score=0,
            correct=False,
            error_tags=["答案与当前评分规则不一致"],
        )
        after = _state(session)

        next_session, next_selection = repository.create_session(
            LEARNER_ID, BANK_ID, mode="study", question_count=2, shuffle_seed=20260829
        )
        next_items = repository.session_items(next_session.session_id)

    artifact = {
        "artifact_version": "adaptive-loop-demo-v1",
        "scenario": {
            "learner_id": "synthetic_demo_only",
            "bank_id": BANK_ID,
            "steps": [
                "initial session built from unseen coverage",
                "one deliberate wrong answer on Topic A",
                "deterministic submit projection updates Attempt, mastery and FSRS ReviewCard",
                "next session reads those existing records and prioritizes Topic A",
            ],
        },
        "before_state": before,
        "initial_selection": {
            "session_id": before_session.session_id,
            "question_ids": [item["question_id"] for item in repository.session_items(before_session.session_id)],
            **before_selection,
        },
        "after_state": after,
        "next_session_selection": {
            "session_id": next_session.session_id,
            "question_ids": [item["question_id"] for item in next_items],
            "items": next_items,
            **next_selection,
        },
        "assertions": {
            "attempt_written": len(after["attempts"]) == 1,
            "weak_topic_mastery_written": any(item["knowledge_point"] == "Topic A" and item["mastery_score"] < 80 for item in after["mastery"]),
            "fsrs_review_card_written": len(after["review_cards"]) == 1 and after["review_cards"][0]["difficulty"] is not None,
            "next_session_reads_state": next_selection["selection_strategy"] == "weak_topic" and next_items[0]["question_id"] in {FOCUS_ID, SIBLING_ID},
            "recommendation_reason_present": bool(next_selection["selection_reason"] and next_selection["selection_evidence"]),
        },
        "privacy": {"synthetic_data_only": True, "contains_patient_data": False, "contains_secret": False},
    }
    if not all(artifact["assertions"].values()):
        raise RuntimeError(f"adaptive loop assertions failed: {artifact['assertions']}")

    output = ROOT / "artifacts" / "learning" / "adaptive-loop-demo-v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": output.as_posix(), "strategy": next_selection["selection_strategy"], "question_ids": [item["question_id"] for item in next_items]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
