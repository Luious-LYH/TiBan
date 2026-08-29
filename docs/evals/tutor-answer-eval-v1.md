# Tutor answer evaluation v1

## Scope

`tutor-answer-eval-v1` freezes 50 synthetic, learner-style cases across ten
categories: current-question explanation, wrong-option explanation,
explicit Study answer, hint-only, follow-up, general GI knowledge,
RAG-needed, RAG-not-needed, out-of-domain and citation-needed. The fixture is
[`docs/fixtures/tutor-answer-eval-v1.json`](../fixtures/tutor-answer-eval-v1.json).

The run uses the same bounded Tutor runtime as the product. It records event
ordering, selected tools, source count, error codes and user-facing text, but
never records tool observations, API keys or raw chain-of-thought.

## Rubric

Each case is intended for independent human review on a 0–2 scale:

| Dimension | Review question |
|---|---|
| Correctness | Is the teaching response factually and evidentially correct? |
| Helpfulness | Does it advance the learner with an actionable next step? |
| Instruction following | Does it honor hint/answer/phase/mode constraints? |
| Citation support | Do cited source name/page/section details support the claims? |
| Unnecessary retrieval | Was retrieval appropriate, relevant and needed? |
| Verbosity | Is the response concise for the requested format? |

## Current execution

The checked-in artifact contains 50/50 protocol executions using the explicit
no-secret local policy adapter. This proves the frozen cases can traverse the
same event and permission path, not model answer quality. A provider-backed
quality run remains **EXTERNAL PROVIDER ACCEPTANCE PENDING** because the
configured local provider exhibited long-tail behavior during the full run;
the process was stopped before it could produce a complete provider result.
All 50 `scores` remain `null` and `review_status` is
`pending_human_review`. No accuracy, precision or clinical effectiveness
claim is made.

Two failure candidates are retained for review rather than hidden:

- out-of-domain requests must not trigger unrelated retrieval;
- citation requests must not cite unsupported sources.

The existing real local-provider Tutor acceptance artifact remains separate at
[`artifacts/agent/tutor-v1/provider-acceptance-v1.json`](../../artifacts/agent/tutor-v1/provider-acceptance-v1.json).

## Reproduction

From the repository root:

```powershell
python scripts/evals/build_tutor_answer_eval_v1.py
```

To opt into the configured local provider for a deliberate run, use
`--run-provider`. The script does not print or persist the provider endpoint or
credential; failures remain failures and never fall back into a quality score.

This is an engineering evaluation pack, not clinical validation.
