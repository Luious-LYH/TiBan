from app.schemas import Question
from app.services.audit_service import audit_service
from app.services.data_store import read_json


class QuestionService:
    def list_questions(
        self,
        question_class: str | None = None,
        difficulty: str | None = None,
        false_premise: bool | None = None,
    ) -> list[Question]:
        items = [Question(**item) for item in read_json("questions.json")]
        if question_class:
            items = [q for q in items if q.question_class == question_class]
        if difficulty:
            items = [q for q in items if q.difficulty == difficulty]
        if false_premise is not None:
            items = [q for q in items if q.false_premise_flag is false_premise]
        return items

    def get_question(self, question_id: str, user_id: str = "demo_learner") -> Question:
        for question in self.list_questions():
            if question.id == question_id:
                audit_service.log(
                    "question_view",
                    user_id=user_id,
                    entity_id=question_id,
                    summary=f"查看题目：{question.title}",
                )
                return question
        raise KeyError(f"Question not found: {question_id}")


question_service = QuestionService()

