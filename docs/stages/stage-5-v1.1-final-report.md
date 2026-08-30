# Stage 5 — v1.1 Memory & Personalization final report

## Release decision

**Stage 5 complete.** The release target is `v1.1.0`. This stage adds
evidence-backed learner memory without changing the existing adaptive loop or
introducing the deferred Stage 6 architecture work.

## Delivered boundary

The durable boundary is deliberately narrow:

```text
grade → immutable Attempt → mastery → FSRS ReviewCard → LearningMemoryItem
                                                      ├─ Tutor context (≤3 facts)
                                                      └─ deterministic session selection
```

- `LearningMemoryItem` is learner-scoped and lifecycle-managed
  (`active` / `resolved` / `superseded`); it records compact evidence references
  rather than raw chat, prompts, answer keys, secrets, or chain-of-thought.
- Three repeated incorrect attempts create/merge a fact; two correct follow-up
  attempts resolve it. A schema-validated explicit concept-confusion statement
  can add a Tutor-run-backed fact.
- `get_learning_memory` is a read-only Tutor tool. PostgreSQL relevance
  selection limits injection to three active current-topic/query matches and
  emits candidate/selected IDs, profile version, token count, and reason in the
  non-CoT trace projection.
- The session builder reads active memory as a deterministic priority after due
  review and before weak-topic/coverage selection.
- The Overview exposes only a concise “最近需要巩固” card and a clear action;
  clearing memory supersedes those facts while preserving Attempt and FSRS
  history.

The full architecture and non-goals are in
[`memory-personalization.md`](../architecture/memory-personalization.md).

## Gate results

| Release gate | Result | Evidence |
| --- | --- | --- |
| Session / Learning / Profile boundaries | PASS | Architecture document and durable model migration. |
| Existing Adaptive Loop | PASS | Full backend regression includes adaptive/FSRS tests. |
| Evidence, dedupe, resolution, learner isolation | PASS | `test_stage5_learning_memory.py` and two-learner artifact. |
| Relevant bounded Tutor memory | PASS | Trace records up to three selected items; pre-submit boundaries remain tested. |
| Deterministic session personalization | PASS | Before/after artifact switches `coverage` to `learning_memory`. |
| Same learner before/after | PASS | [`personalization-before-after-v1.json`](../../artifacts/memory/personalization-before-after-v1.json). |
| Two learner differentiation | PASS | [`two-learner-differentiation-v1.json`](../../artifacts/memory/two-learner-differentiation-v1.json). |
| Backend regression | PASS | Fresh isolated SQLite: `61 passed, 1 skipped`. |
| Frontend lint / unit / build | PASS | `npm run lint`; core page suite: `12 passed`; `npm run build`. |
| OpenAPI client generation | PASS | `npm run api:generate` regenerated `src/api/generated.ts`. |
| Playwright core flow | PASS | `core-flow.spec.ts`, Flow A: `1 passed`. |
| Docker clean start | PASS | Isolated Compose topology: PostgreSQL, Qdrant, Redis, backend, worker, frontend healthy; Alembic `a5b6c7d8e9f0`; `learning_memory_items` present; API reports `1.1.0`. |
| README / evidence matrix | PASS | README and `FINAL_EVIDENCE_MATRIX.md` updated. |

The Docker verification used a project-scoped temporary port override only
because the default local PostgreSQL port was already occupied by a separate
existing acceptance project. It did not alter that project or its volumes.

## Evidence index

- [`artifacts/memory/`](../../artifacts/memory/): reproducible same-learner and
  two-learner JSON artifacts.
- [`memory-personalization-acceptance.md`](../evals/memory-personalization-acceptance.md):
  acceptance criteria and reproduction command.
- [`stage-5-learning-profile.png`](../portfolio/evidence/stage-5-learning-profile.png):
  reviewed product surface screenshot.
- [`stage-5-current-memory-audit.md`](./stage-5-current-memory-audit.md):
  pre-implementation inventory.

## Known limits

- This is structured, evidence-backed personalization—not model-weight updates,
  unrestricted chat retention, autonomous diagnosis, or clinical validation.
- The compact teaching seed bounds the demo session size; locally authorized
  third-party QBank fixtures are not redistributed.
- Python/FastAPI deprecation warnings (`datetime.utcnow`, startup events) remain
  existing technical debt and are outside this narrowly scoped Stage 5 release.

## Stop condition

Stage 5 stops here. Stage 6 work (Hexagonal/Ports refactor, durable-job
abstractions, or agent-framework expansion) has not been started.
