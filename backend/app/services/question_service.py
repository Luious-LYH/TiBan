from app.core.config import SAFETY_NOTICE
from app.schemas import AtomicFact, Question
from app.services.audit_service import audit_service
from app.services.data_store import read_json
from app.services.memory_service import memory_service


class QuestionService:
    def list_questions(
        self,
        question_class: str | None = None,
        difficulty: str | None = None,
        false_premise: bool | None = None,
        body_part: str | None = None,
        task: str | None = None,
        question_type: str | None = None,
        source_dataset: str | None = None,
        only_favorites: bool = False,
        only_wrong: bool = False,
    ) -> list[Question]:
        profile = memory_service.get_profile()
        items = [self._with_training_state(Question(**item), profile) for item in read_json("questions.json")]
        items.extend(self._real_sample_questions(profile))
        if question_class:
            items = [q for q in items if q.question_class == question_class]
        if difficulty:
            items = [q for q in items if q.difficulty == difficulty]
        if false_premise is not None:
            items = [q for q in items if q.false_premise_flag is false_premise]
        if body_part:
            items = [q for q in items if q.body_part == body_part]
        if task:
            items = [q for q in items if q.task == task]
        if question_type:
            items = [q for q in items if q.question_type == question_type]
        if source_dataset:
            items = [q for q in items if q.source_dataset == source_dataset]
        if only_favorites:
            items = [q for q in items if q.is_favorited]
        if only_wrong:
            items = [q for q in items if q.review_status == "待复盘"]
        return self._public_first(items)

    def get_question(self, question_id: str, user_id: str = "demo_learner", *, record_view: bool = True) -> Question:
        for question in self.list_questions():
            if question.id == question_id:
                if record_view:
                    audit_service.log(
                        "question_view",
                        user_id=user_id,
                        entity_id=question_id,
                        summary=f"查看题目：{question.title}",
                    )
                return question
        raise KeyError(f"Question not found: {question_id}")

    def _with_training_state(self, question: Question, profile) -> Question:
        question.is_favorited = question.id in profile.favorite_questions
        if question.is_favorited:
            question.review_status = "收藏中"
        elif question.id in profile.wrong_questions or question.id in profile.recent_errors:
            question.review_status = "待复盘"
        return question

    def _real_sample_questions(self, profile) -> list[Question]:
        try:
            samples = read_json("real_sample_knowledge.json")
        except FileNotFoundError:
            return []
        return [self._with_training_state(self._sample_to_question(item), profile) for item in samples]

    def _public_first(self, items: list[Question]) -> list[Question]:
        public_datasets = {"Kvasir-VQA-x1", "Kvasir-VQA", "EndoBench"}
        return sorted(items, key=lambda question: 0 if question.source_dataset in public_datasets else 1)

    def _sample_to_question(self, item: dict) -> Question:
        answer = str(item.get("answer", "证据不足，需医生复核"))
        options = item.get("options") or self._options_for_answer(answer)
        source_dataset = str(item.get("source_dataset", "公开样例"))
        sample_use = str(item.get("use", "atomic_qbank"))
        question_class = "复杂组合" if sample_use == "complex_qbank" else "部位定位" if sample_use == "exam_mode" else "基础识别"
        source_type = "公开复杂问答" if sample_use == "complex_qbank" else "公开综合基准" if sample_use == "exam_mode" else "公开基础问答"
        body_part = self._body_part(item)
        task = "复杂问答拆解" if sample_use == "complex_qbank" else "考试模式识别" if sample_use == "exam_mode" else "公开题库刷题"
        atomic_trace = self._atomic_trace(item, answer)
        return Question(
            id=f"public_{item['id']}",
            title=f"{source_dataset} 公开样例训练",
            image_url=item.get("image_url"),
            image_placeholder=f"{source_dataset} 脱敏公开样例图像，用于医师训练题库与模型准入演示。",
            case_summary=f"{item.get('citation_note', '公开数据样例，仅用于教学训练演示。')} 当前题用于训练 {body_part} 相关观察与证据边界。",
            question=f"公开样例题：{item.get('question', '请根据图像完成训练问题。')}",
            options=options,
            answer=answer,
            explanation=f"参考公开样例答案：{answer}。训练重点是先描述图像证据，再说明不确定性和医生复核边界。",
            complexity=int(item.get("complexity", 2)),
            question_class=question_class,
            source_type=source_type,
            atomic_trace=atomic_trace,
            false_premise_flag=False,
            teaching_tags=[source_dataset, "公开数据样例", "证据边界"],
            difficulty="挑战" if int(item.get("complexity", 2)) >= 3 else "进阶",
            doctor_review_required=True,
            safety_notice=SAFETY_NOTICE,
            body_part=body_part,
            task=task,
            question_type="单选",
            source_dataset=source_dataset,
            citation_note=item.get("citation_note", "公开数据样例，仅用于教学训练演示。"),
            ai_benchmark_answer=answer,
            expected_keywords=[token for token in answer.replace(";", " ").replace(",", " ").split()[:6]],
        )

    def _options_for_answer(self, answer: str) -> list[str]:
        if answer.lower() in {"yes", "no"}:
            distractors = ["no" if answer.lower() == "yes" else "yes", "证据不足", "不适用"]
            return [answer, *distractors]
        return [
            answer,
            "未见异常或关键解剖标志",
            "可直接给出最终临床诊断",
            "证据不足，不能回答该题",
        ]

    def _body_part(self, item: dict) -> str:
        answer = str(item.get("answer", "")).lower()
        classes = " ".join(item.get("question_class", [])).lower()
        scene = str(item.get("scene", "")).lower()
        if "oesophagitis" in answer or "z-line" in answer:
            return "食管"
        if "small intestine" in answer or "capsule" in scene:
            return "小肠"
        if "colitis" in answer or "colitis" in classes:
            return "结直肠"
        return "胃"

    def _atomic_trace(self, item: dict, answer: str) -> list[AtomicFact]:
        original = item.get("original_atomic") or []
        if original:
            return [
                AtomicFact(
                    id=f"{item['id']}_f{idx + 1}",
                    fact=str(piece.get("q", "公开样例原子问题")),
                    expected=str(piece.get("a", "")),
                    supported=True,
                    evidence=f"公开样例标注：{piece.get('a', '')}",
                    skill_dimension="事实组合",
                )
                for idx, piece in enumerate(original[:4])
            ]
        return [
            AtomicFact(
                id=f"{item['id']}_f1",
                fact="公开样例给出参考答案",
                expected=answer,
                supported=True,
                evidence=f"参考答案：{answer}",
                skill_dimension="部位定位" if "organ" in str(item.get("question", "")).lower() else "病灶识别",
            )
        ]


question_service = QuestionService()
