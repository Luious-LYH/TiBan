# Question Judge evaluation v1

This is a small, manually reviewed fixture of 30 QuestionDrafts: 10 pass examples and 20 labelled failures across answer consistency, citation, groundedness, safety-boundary and distractor issues. The labels and issue categories are fixed before running the rule/Judge comparison. It is a workflow test, not a claim about general LLM-Judge accuracy.

| Pipeline | TP | FP | FN | TN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Deterministic gate only | 10 | 10 | 0 | 10 | 0.500 | 1.000 |
| Gate + separate Judge | 10 | 0 | 0 | 20 | 1.000 | 1.000 |

The result answers the relevant implementation question: on this manually inspected set, Judge catches the ten semantic/safety/distractor failures that structural gates accept. The checked-in evidence is [`artifacts/factory/question-judge-eval-v1.json`](../../artifacts/factory/question-judge-eval-v1.json); re-run with `python backend/scripts/run_question_judge_eval.py`.
