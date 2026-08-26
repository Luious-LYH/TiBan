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
        items = self._real_sample_questions(profile)
        if not items:
            items = self._legacy_real_questions(profile)
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
        curated = self._curated_teaching_questions(profile)
        try:
            samples = read_json("real_sample_knowledge.json")
        except FileNotFoundError:
            samples = []
        questions: list[Question] = []
        for item in samples:
            questions.extend(self._sample_to_questions(item))
        visual_questions = [self._with_training_state(question, profile) for question in questions]
        return [*curated, *visual_questions]

    def _curated_teaching_questions(self, profile) -> list[Question]:
        try:
            raw_items = read_json("curated_teaching_questions.json")
        except FileNotFoundError:
            return []
        questions: list[Question] = []
        for item in raw_items:
            try:
                clean = dict(item)
                clean.setdefault("safety_notice", SAFETY_NOTICE)
                questions.append(self._with_training_state(Question(**clean), profile))
            except Exception:
                continue
        return questions

    def _legacy_real_questions(self, profile) -> list[Question]:
        try:
            raw_items = read_json("questions.json")
        except FileNotFoundError:
            return []
        questions: list[Question] = []
        for item in raw_items:
            if self._is_real_sample_url(item.get("image_url")):
                questions.append(self._with_training_state(Question(**item), profile))
        return questions

    def _public_first(self, items: list[Question]) -> list[Question]:
        public_datasets = {"Kvasir-VQA-x1", "Kvasir-VQA", "EndoBench"}
        curated_datasets = {"内镜研修人工整理题库", "题库导入演示样例"}
        return sorted(
            items,
            key=lambda question: (
                0 if question.source_dataset in curated_datasets else 1 if question.source_dataset in public_datasets else 2,
                question.body_part,
                question.question_type,
                question.id,
            ),
        )

    def _sample_to_questions(self, item: dict) -> list[Question]:
        image_url = self._real_image_url(item)
        if not image_url:
            return []
        source_dataset = str(item.get("source_dataset", "公开样例"))
        body_part = self._body_part(item)
        answer = self._answer_text(item)
        facts = self._atomic_trace(item, answer)
        fact_answer = self._fact_answer(facts, answer)
        multi_correct_options = self._multi_correct_options(facts, answer, body_part)
        multi_answer = "；".join(multi_correct_options)
        report_answer = self._report_revision(answer, body_part)
        base_class = self._base_question_class(item, answer)
        complexity = self._complexity(item)
        base = {
            "image_url": image_url,
            "image_placeholder": f"{source_dataset} 真实内镜样例图像，仅用于医生研修和模型评测复核。",
            "case_summary": (
                f"公开真实内镜样例。当前题用于训练{body_part}图像观察、部位/属性描述和报告表达；"
                "不包含真实患者身份信息。"
            ),
            "source_type": self._source_type(item),
            "source_dataset": source_dataset,
            "citation_note": "公开真实内镜图像样例，仅用于教学研修和医生复核前辅助。",
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
            "body_part": body_part,
            "ai_benchmark_answer": answer,
        }
        variants = [
            {
                "suffix": "single",
                "title": f"{body_part}真实图像基础识别",
                "question": "从这张真实内镜样例中，最合适的观察结论是？",
                "options": self._single_options(answer, body_part),
                "answer": answer,
                "explanation": f"参考表达：{answer} 该题训练先描述可观察图像事实，再保留医生复核要求。",
                "question_class": base_class,
                "question_type": "单选",
                "task": "真实图像基础识别",
                "false_premise_flag": False,
                "teaching_tags": [base_class, body_part, "真实图片"],
                "atomic_trace": facts,
                "expected_keywords": self._keywords(answer, body_part, base_class),
            },
            {
                "suffix": "multi",
                "title": f"{body_part}一图多问观察整合",
                "question": "多选研修：这张图作答时需要同时核对哪些要点？请选择所有有图像或安全依据的选项。",
                "options": self._multi_options(multi_correct_options, facts, body_part),
                "answer": multi_answer,
                "explanation": "一图多问题应把部位、数量、属性或画面信息拆开核对，避免只抓一个局部线索。",
                "question_class": "一图多问",
                "question_type": "多选",
                "task": "多项观察整合",
                "false_premise_flag": False,
                "teaching_tags": ["一图多问", body_part, "真实图片"],
                "atomic_trace": facts,
                "expected_keywords": self._keywords(fact_answer, body_part, "一图多问"),
            },
            {
                "suffix": "judge",
                "title": f"{body_part}报告安全判断",
                "question": "判断题：仅凭这一张内镜图像，可以直接形成最终临床诊断并给出治疗方案。",
                "options": ["正确", "错误"],
                "answer": "错误",
                "explanation": "单帧图像只能支持谨慎的观察性描述，正式报告和处理意见必须由医生结合完整检查、病史及必要病理复核。",
                "question_class": "报告纠错",
                "question_type": "判断",
                "task": "报告表达安全判断",
                "false_premise_flag": True,
                "teaching_tags": ["报告纠错", body_part, "医生复核"],
                "atomic_trace": [*facts[:2], self._overclaim_fact(item)],
                "expected_keywords": ["错误", "单帧图像", "医生复核"],
            },
            {
                "suffix": "qa",
                "title": f"{body_part}开放问答评分",
                "question": "问答评分：请用一句话写出适合放入研修记录的图像观察描述。",
                "options": self._qa_options(answer, body_part),
                "answer": f"应描述为：{answer} 同时注明需结合完整检查和医生复核。",
                "explanation": "开放问答评分关注描述是否覆盖可观察事实、部位/属性要点，以及是否避免越界诊断。",
                "question_class": "病变属性" if base_class != "部位定位" else "部位定位",
                "question_type": "问答评分",
                "task": "开放描述评分",
                "false_premise_flag": False,
                "teaching_tags": ["问答评分", body_part, "观察描述"],
                "atomic_trace": facts,
                "expected_keywords": self._keywords(answer, body_part, "问答评分"),
            },
            {
                "suffix": "report",
                "title": f"{body_part}报告纠错改写",
                "question": f"报告修改题：原句“{self._unsafe_report_sentence(answer, body_part)}”应如何改写更适合医生复核前草稿？",
                "options": self._report_options(report_answer, answer, body_part),
                "answer": report_answer,
                "explanation": "报告修改题训练把最终诊断或治疗承诺降级为观察所见，并保留完整检查和医生复核要求。",
                "question_class": "报告纠错",
                "question_type": "报告修改",
                "task": "报告纠错改写",
                "false_premise_flag": True,
                "teaching_tags": ["报告纠错", body_part, "结构化报告"],
                "atomic_trace": [*facts[:2], self._overclaim_fact(item)],
                "expected_keywords": ["所见", body_part, "复核"],
            },
        ]
        return [
            self._build_question(item, base, variant, complexity)
            for variant in variants
        ]

    def _build_question(self, item: dict, base: dict, variant: dict, complexity: int) -> Question:
        return Question(
            id=f"public_{item.get('id', 'sample')}_{variant['suffix']}",
            title=variant["title"],
            image_url=base["image_url"],
            image_placeholder=base["image_placeholder"],
            case_summary=base["case_summary"],
            question=variant["question"],
            options=self._dedupe_options(variant["options"]),
            answer=variant["answer"],
            explanation=variant["explanation"],
            complexity=complexity,
            question_class=variant["question_class"],
            source_type=base["source_type"],
            atomic_trace=variant["atomic_trace"],
            false_premise_flag=variant["false_premise_flag"],
            teaching_tags=variant["teaching_tags"],
            difficulty=self._difficulty(complexity),
            doctor_review_required=base["doctor_review_required"],
            safety_notice=base["safety_notice"],
            body_part=base["body_part"],
            task=variant["task"],
            question_type=variant["question_type"],
            source_dataset=base["source_dataset"],
            citation_note=base["citation_note"],
            ai_benchmark_answer=base["ai_benchmark_answer"],
            expected_keywords=variant["expected_keywords"],
        )

    def _real_image_url(self, item: dict) -> str:
        image_url = str(item.get("image_url") or "").strip()
        return image_url if self._is_real_sample_url(image_url) else ""

    def _is_real_sample_url(self, value: object) -> bool:
        image_url = str(value or "").strip()
        return image_url.startswith("/assets/real_samples/") and ".svg" not in image_url.lower()

    def _source_type(self, item: dict) -> str:
        sample_use = str(item.get("use", "atomic_qbank"))
        if sample_use == "atomic_qbank":
            return "公开基础问答"
        return "公开综合基准"

    def _complexity(self, item: dict) -> int:
        try:
            value = int(item.get("complexity", 2))
        except (TypeError, ValueError):
            value = 2
        return max(1, min(value, 3))

    def _difficulty(self, complexity: int) -> str:
        if complexity <= 1:
            return "入门"
        if complexity == 2:
            return "进阶"
        return "挑战"

    def _base_question_class(self, item: dict, answer: str) -> str:
        sample_use = str(item.get("use", "atomic_qbank"))
        question = str(item.get("question", "")).lower()
        if sample_use == "exam_mode" or "organ" in question or "segment" in question:
            return "部位定位"
        if sample_use == "complex_qbank" or item.get("original_atomic"):
            return "一图多问"
        if any(token in answer for token in ["炎症", "息肉", "异常", "糜烂", "器械"]):
            return "病变属性"
        return "基础识别"

    def _single_options(self, answer: str, body_part: str) -> list[str]:
        return [
            answer,
            f"未见需要记录的{body_part}相关观察线索",
            "可直接形成最终临床诊断并给出处理方案",
            "仅凭该图无法确认任何解剖部位或黏膜表现",
        ]

    def _multi_options(self, correct_options: list[str], facts: list[AtomicFact], body_part: str) -> list[str]:
        partial = facts[0].fact if facts else "只记录单一观察点"
        return [
            *correct_options,
            f"只记录：{partial}",
            "同时记录最终诊断、治疗方案和病理结果",
            "跳过图像观察，直接要求患者随访即可",
            f"只填写{body_part}部位，不核对形态、数量或证据边界",
        ]

    def _qa_options(self, answer: str, body_part: str) -> list[str]:
        return [
            f"应描述为：{answer} 同时注明需结合完整检查和医生复核。",
            f"{body_part}图像可直接确诊并立即处理。",
            "图像完全正常，无需记录任何观察。",
            "只描述患者症状，不描述内镜画面。",
        ]

    def _report_options(self, report_answer: str, answer: str, body_part: str) -> list[str]:
        return [
            report_answer,
            self._unsafe_report_sentence(answer, body_part),
            "图像完全正常，可省略内镜所见。",
            "建议直接给出治疗方案，无需结合完整检查。",
        ]

    def _dedupe_options(self, options: list[str]) -> list[str]:
        cleaned: list[str] = []
        for option in options:
            text = str(option).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        while len(cleaned) < 2:
            cleaned.append("需结合图像证据和医生复核。")
        return cleaned[:4]

    def _fact_answer(self, facts: list[AtomicFact], fallback: str) -> str:
        labels = [f"{fact.fact}：{fact.expected}" for fact in facts[:3]]
        return "；".join(labels) if labels else fallback

    def _multi_correct_options(self, facts: list[AtomicFact], fallback: str, body_part: str) -> list[str]:
        labels = [f"{fact.fact}：{fact.expected}" for fact in facts[:3]]
        if not labels:
            labels.append(f"图像观察结论：{fallback}")
        if len(labels) < 2:
            labels.append("复核边界：单帧图像只作观察性描述并保留医生复核")
        if len(labels) < 3:
            labels.append(f"报告表达：先描述{body_part}可观察事实并避免最终诊断承诺")
        return list(dict.fromkeys(labels))[:3]

    def _unsafe_report_sentence(self, answer: str, body_part: str) -> str:
        return f"{body_part}图像提示{answer}，可直接确诊并给出治疗方案。"

    def _report_revision(self, answer: str, body_part: str) -> str:
        return (
            f"内镜所见：{body_part}区域{answer} "
            "上述为单帧/样例图像观察描述，需由医生结合完整检查、病史及必要病理结果复核。"
        )

    def _keywords(self, answer: str, body_part: str, question_class: str) -> list[str]:
        keywords = [body_part, question_class, "可见" if "可见" in answer else "观察", "复核"]
        return list(dict.fromkeys([keyword for keyword in keywords if keyword]))[:6]

    def _answer_text(self, item: dict) -> str:
        raw_answer = str(item.get("answer", "")).lower()
        question = str(item.get("question", "")).lower()
        body_part = self._body_part(item)
        if "small intestine" in raw_answer:
            return "图像显示小肠黏膜视野。"
        if "oesophagitis" in raw_answer or "z-line" in raw_answer:
            return "可见食管炎相关表现，未见明确息肉，Z 线可作为解剖标志。"
        if "polyps remain" in raw_answer and "text is visible" in raw_answer:
            return "可见息肉样改变仍存在，并可见画面文字信息；异常区域位于中央及偏上区域。"
        if "no surgical instruments" in raw_answer:
            return "未见手术器械或息肉，但可见一处异常表现。"
        if "one instrument" in raw_answer:
            return "可见一件器械，未见文字信息，异常分布在画面中央及偏上区域。"
        if "ulcerative colitis" in raw_answer or "colitis" in raw_answer:
            return "可见结直肠黏膜炎症相关表现，需结合完整检查复核。"
        if raw_answer in {"yes", "no"}:
            if "text" in question:
                return "画面可见文字信息。" if raw_answer == "yes" else "画面未见明确文字信息。"
            return "图像支持该观察结论。" if raw_answer == "yes" else "图像不支持该观察结论。"
        if raw_answer:
            return f"图像提示{body_part}区域存在可观察改变：{item.get('answer')}。"
        return f"图像提示{body_part}区域存在可观察改变，需医生复核。"

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
            return [self._atomic_fact_from_piece(item, piece, idx) for idx, piece in enumerate(original[:4])]
        question = str(item.get("question", "")).lower()
        if "organ" in question or "segment" in question:
            return [
                AtomicFact(
                    id=f"{item['id']}_f1",
                    fact="消化道部位定位",
                    expected=self._expected_text(item.get("answer", answer)),
                    supported=True,
                    evidence="真实样例标注支持该部位判断，仍需医生结合完整检查复核。",
                    skill_dimension="部位定位",
                )
            ]
        if "text" in question:
            return [
                AtomicFact(
                    id=f"{item['id']}_f1",
                    fact="画面文字信息",
                    expected=self._expected_text(item.get("answer", answer)),
                    supported=True,
                    evidence="真实样例标注支持该画面信息判断。",
                    skill_dimension="属性判断",
                )
            ]
        return [
            AtomicFact(
                id=f"{item['id']}_f1",
                fact="黏膜异常表现",
                expected=answer,
                supported=True,
                evidence="真实样例标注支持该观察方向，正式表达需由医生复核。",
                skill_dimension="病灶识别",
            )
        ]

    def _atomic_fact_from_piece(self, item: dict, piece: dict, index: int) -> AtomicFact:
        question = str(piece.get("q", "")).lower()
        raw_expected = str(piece.get("a", ""))
        fact = "观察事实"
        dimension = "病灶识别"
        if "where" in question or "located" in question or "region" in question:
            fact = "异常区域定位"
            dimension = "部位定位"
        elif "how many" in question or "count" in question:
            fact = "数量判断"
            dimension = "数量判断"
        elif "instrument" in question:
            fact = "器械可见性"
            dimension = "属性判断"
        elif "text" in question:
            fact = "画面文字信息"
            dimension = "属性判断"
        elif "polyp" in question:
            fact = "息肉相关表现"
            dimension = "病灶识别"
        elif "landmark" in question or "z-line" in raw_expected.lower():
            fact = "解剖标志"
            dimension = "部位定位"
        elif "abnormal" in question or "finding" in question:
            fact = "异常表现"
            dimension = "病灶识别"
        return AtomicFact(
            id=f"{item['id']}_f{index + 1}",
            fact=fact,
            expected=self._expected_text(raw_expected),
            supported=True,
            evidence="真实样例标注支持该观察点，研修时仍需回到图像核对。",
            skill_dimension=dimension,
        )

    def _overclaim_fact(self, item: dict) -> AtomicFact:
        return AtomicFact(
            id=f"{item.get('id', 'sample')}_safety",
            fact="最终诊断或治疗方案不能由单帧样例直接推出",
            expected="应改写为观察所见，并保留医生复核要求。",
            supported=False,
            evidence="样例未提供完整检查范围、病史、病理或治疗上下文。",
            skill_dimension="属性判断",
        )

    def _expected_text(self, value: object) -> str:
        text = str(value or "").strip()
        lower = text.lower()
        if lower == "yes":
            return "可见/支持"
        if lower == "no":
            return "未见/不支持"
        if lower in {"none", "0"}:
            return "未见明确目标"
        if lower == "1":
            return "可见 1 处/1 件"
        if "small intestine" in lower:
            return "小肠"
        if "center" in lower or "upper" in lower:
            return "中央及偏上区域"
        if "oesophagitis" in lower:
            return "食管炎相关表现"
        if "z-line" in lower:
            return "Z 线"
        if "colitis" in lower:
            return "结直肠黏膜炎症相关表现"
        return text or "需结合图像观察判断"


question_service = QuestionService()
