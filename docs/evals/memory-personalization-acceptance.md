# Memory & Personalization acceptance — v1

## Scope

This is an engineering acceptance, not a clinical-effectiveness study. It uses
the compact clean-start teaching seed and deterministic grading so that no local
third-party QBank or provider secret is required.

| Check | Evidence | Result |
| --- | --- | --- |
| Strong write threshold | Three graded incorrect attempts create a compact repeated-mistake fact. | PASS |
| Dedupe and resolve | Same-topic evidence merges; two later correct attempts resolve the active fact. | PASS |
| Learner isolation | Learner A's selected memory IDs cannot be retrieved for Learner B. | PASS |
| Prompt budget | Structured relevance matching injects no more than three active facts. | PASS |
| Tutor read-back | Trace shows `candidate_memory_ids`, `selected_memory_ids`, version, token count and reason. | PASS |
| Adaptive use | With due cards deferred, active memory is a deterministic session-selection tier. | PASS |
| Clear action | Only learning-memory rows are superseded; Attempt and ReviewCard history stays intact. | PASS |

## Reproducible artifacts

- [`personalization-before-after-v1.json`](../../artifacts/memory/personalization-before-after-v1.json)
  proves empty read-back before evidence, then a different Tutor context and a
  `learning_memory` session-selection reason after three deterministic errors.
- [`two-learner-differentiation-v1.json`](../../artifacts/memory/two-learner-differentiation-v1.json)
  proves different relevant memory and selection evidence for two learners
  receiving the same next-session request.

The artifact generator is
[`run_memory_personalization_evidence.py`](../../backend/scripts/run_memory_personalization_evidence.py).
It initializes its database, so the result does not rely on a developer's
accumulated local QBank data.

## Test surface

`backend/tests/test_stage5_learning_memory.py` covers lifecycle, dedupe,
resolution, explicit chat candidate validation, learner isolation, Tutor trace,
post-submit tool priority, adaptive selection and clear-history preservation.
The existing Tutor adversarial tests continue to prove pre-submit answer
isolation. The Overview interaction is covered in
`frontend/src/test/core-pages.test.tsx`.
