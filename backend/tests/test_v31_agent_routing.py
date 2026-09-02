from __future__ import annotations

from app.services.agent_runtime import AgentContext, LocalPolicyModelGateway, _clean_user_facing_text, tutor_runner
from app.services.coach_agent_service import _review_queue, coach_agent_service, coach_runner


def _question_tools(message: str, *, phase: str = "pre_submit") -> list[str]:
    context = AgentContext(
        question_id="endo_text_esophagus_reflux_single", learner_id="routing-learner", user_message=message, phase=phase  # type: ignore[arg-type]
    )
    return LocalPolicyModelGateway().select_tools(context, tutor_runner.registry.allowed(phase))


def _coach_tools(message: str) -> list[str]:
    context = AgentContext(question_id="", learner_id="routing-learner", user_message=message, phase="coach", metadata={"agent_profile": "coach"})
    return LocalPolicyModelGateway().select_tools(context, coach_runner.registry.allowed("coach"))


def test_question_assistant_routes_only_when_extra_data_is_requested() -> None:
    assert _question_tools("黄体生成素是什么？") == []
    assert _question_tools("牛顿是谁？") == []
    assert _question_tools("为什么当前题的 B 不对？") == []
    assert _question_tools("根据我上传的资料解释黄体生成素") == ["retrieve_knowledge"]
    history_tools = _question_tools("我最近最容易错什么？")
    assert {"get_recent_mistakes", "get_learning_profile", "get_learning_memory"}.issubset(history_tools)


def test_pre_submit_source_request_does_not_gain_answer_tool_without_asking() -> None:
    assert _question_tools("根据资料解释当前题考点，并给出来源。") == ["retrieve_knowledge"]


def test_question_assistant_allows_zero_evidence_without_fake_citation() -> None:
    events = list(tutor_runner.stream(AgentContext(
        question_id="endo_text_esophagus_reflux_single", learner_id="routing-empty", user_message="根据知识库解释海洋章鱼的生活习性", phase="pre_submit"
    )))
    tool_names = [event.data.get("tool_name") for event in events if event.event == "tool_start"]
    citations = [event.data for event in events if event.event == "source"]
    assert tool_names == ["retrieve_knowledge"]
    # Test configuration disables external retrieval, so the truthful result is
    # no citation rather than a question-provenance fallback.
    assert citations == []


def test_question_assistant_output_guard_removes_pseudo_provenance_and_runtime_tail() -> None:
    rendered = _clean_user_facing_text(
        "### 当前题考点\n先比较药物功效。\n题目来源：CMExam，``，仅供教学研修。"
    )
    assert "###" not in rendered
    assert "题目来源" not in rendered
    assert "仅供教学" not in rendered
    assert "先比较药物功效" in rendered


def test_coach_routes_real_learning_state_and_persists_conversation() -> None:
    history_tools = _coach_tools("我最近最容易错什么？")
    assert {"get_recent_attempts", "get_learning_summary", "get_learning_memories"}.issubset(history_tools)
    plan_tools = _coach_tools("我今天应该先复习什么？")
    assert {"get_review_queue", "get_bank_progress", "get_learning_summary"}.issubset(plan_tools)
    assert _coach_tools("牛顿是谁？") == []
    assert _coach_tools("根据我的资料解释心力衰竭") == ["search_knowledge"]

    learner = "routing-coach-persist"
    conversation = coach_agent_service.create_conversation(learner)
    events = list(coach_agent_service.stream_message(
        conversation_id=str(conversation["id"]), learner_id=learner, message="牛顿是谁？"
    ))
    assert any(event.event == "agent_start" for event in events)
    assert not any(event.event == "tool_start" for event in events)
    saved = coach_agent_service.detail(str(conversation["id"]), learner)
    assert [item["role"] for item in saved["messages"]] == ["user", "assistant"]


def test_coach_review_queue_uses_public_question_summary(monkeypatch) -> None:
    class FakeRepository:
        def review_items(self, **_kwargs):
            return [{"question_id": "q1", "bank_name": "CMExam", "question_summary": "真实复习题干", "due_at": None}]

        def review_summary(self, _learner_id):
            return {"due_count": 1}

    class FakeSession:
        def __enter__(self): return self
        def __exit__(self, *_args): return None

    monkeypatch.setattr("app.services.coach_agent_service.SessionLocal", lambda: FakeSession())
    monkeypatch.setattr("app.services.coach_agent_service.Stage1Repository", lambda _session: FakeRepository())
    context = AgentContext(question_id="", learner_id="routing-learner", user_message="复习", phase="coach")
    assert _review_queue(context)["items"] == [{"question_id": "q1", "bank_name": "CMExam", "title": "真实复习题干", "due_at": None}]
