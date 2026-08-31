# Stage 7 — v2.0.0 Learning Platform Final Report

**Status:** Release Gate complete pending the final hosted workflow result.  The
release is limited to the two approved v2.0 directions: **Domain-extensible
Learning Platform** and **Advanced Evaluation**.  No Stage 8 work was started.

**Branch:** `refactor/v3-agent-learning-platform`
**Stage baseline:** `47d8bab`
**Previous release preserved:** annotated `v1.2.0` → `8014374`

## 1. Scope delivered

TiBan now exposes one reusable platform core behind a small validated
`DomainManifest` registry.  The checked-in packs are:

- `endoscopy` — the existing governed Medical / Endoscopy product path;
- `general_science` — an independent eight-question project-authored proof
  pack used to validate cross-domain reuse.

Both packs use the same QBank catalog, Study/Exam/Review session builder,
deterministic grading workflow, immutable Attempt, mastery, single py-fsrs
scheduler, Learning Memory, Tutor runtime, Qdrant retrieval boundary, Factory
job pipeline and Evaluation engine.  `domain_id` is explicit in the public
contract and persistence projections.

The implementation does not introduce a plugin framework, a second Tutor
runtime, a second FSRS scheduler, a second vector database, Multi-Agent,
VLM-Tutor productization, Public SaaS, Kubernetes/Terraform, GraphRAG or model
training.

## 2. Release Gate evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Working-tree inventory and Stage 6 wording calibration | PASS | [`stage-7-worktree-inventory.md`](stage-7-worktree-inventory.md) |
| Domain coupling audit | PASS | [`stage-7-domain-coupling-audit.md`](stage-7-domain-coupling-audit.md) |
| Minimal DomainManifest and catalog filtering | PASS | `backend/app/domains.py`, `backend/tests/test_stage7_platform.py` |
| Medical regression | PASS | `backend/tests/test_stage7_platform.py` and full backend suite |
| General Domain Study/Exam/Review/Tutor/Attempt/Mastery/FSRS/Memory | PASS | `artifacts/platform/general-domain-flow-v2.json` |
| Shared core reuse; no duplicated engines | PASS | `artifacts/platform/domain-core-reuse-v2.json` |
| Medical/General RAG and Memory isolation | PASS | `artifacts/platform/cross-domain-isolation-v2.json`, isolation tests |
| Domain-aware Tutor policy | PASS | `backend/app/adapters/tutor_gateway.py`, General regression |
| General Evaluation pack | PASS | `artifacts/platform/general-domain-flow-v2.json`, Evaluation catalog |
| Agent tool-selection evaluation | PASS | 6 cases; accuracy 1.0000, unnecessary-tool rate 0.0000, missing-tool rate 0.0000 |
| Personalization evaluation | PASS | scheduling match 0.25 → 0.75; uplift +0.50; no learning-outcome claim |
| Factory regression | PASS | Docker job reached `published` with two revision records |
| Backend regression | PASS | `76 passed` |
| Frontend lint / unit / build | PASS | lint; 12 unit tests; production build |
| OpenAPI drift | PASS after release commit | `npm run api:generate` / `npm run api:check`; generated client is not manually maintained |
| Architecture guard | PASS | `7 application modules; domains=['endoscopy', 'general_science']` |
| Playwright medical + general smoke | PASS | Flow A and General Flow C; 2 passed |
| Docker clean-start | PASS | [`docker-acceptance-v2.json`](../../artifacts/platform/docker-acceptance-v2.json) |
| Hosted GitHub Actions | PENDING final push | Recorded below after the release commit is pushed |
| README / Evidence Matrix / resume synchronization | PASS | `README.md`, `docs/portfolio/FINAL_EVIDENCE_MATRIX.md`, resume docs |

The full backend run initially exposed persistent local test rows crowding the
first catalog page; the repository ordering now keeps explicitly marked
`source_dataset=test` rows out of the learner-facing first page.  The rerun is
the reported `76 passed` result.  Docker clean-start also exposed Qdrant's
short first-collection request timeout; the client now uses a 30-second
bounded timeout, and a fresh-volume rerun passed on its first Factory job.

One historical test remains intentionally skippable when the optional local
3,678-question acceptance database is absent:
`test_kvasir_curated_bank_has_lineage_and_legacy_vqa_is_quarantined`.  This is
documented in the inventory because raw third-party samples are not
redistributed by the repository; policy and EndoBench exclusion remain covered
by checked-in fixtures and tests.

## 3. Docker Acceptance

The stack was rebuilt from clean, acceptance-owned volumes using PostgreSQL,
Qdrant, Redis, Dramatiq, the FastAPI backend and the Nginx frontend.  The
probe exercised:

```text
Medical: bank → Study → Tutor SSE → Attempt → Memory/FSRS
General: bank → Study → Tutor SSE → Attempt → Memory/FSRS
Factory: upload → queued → parsing → indexing → generating → judging
         → repairing → ready_for_review → published
Evaluation: Medical and General dataset catalog
```

The final probe recorded `medical_flow=true`, `general_flow=true`,
`factory_flow=true`, and `evaluation_catalog=true`.  Tutor SSE included
`message_start`, tool receipt boundaries, `source`, `reasoning`, token frames
and `message_end` for both domains.  Review cards returned non-null FSRS
difficulty, stability, retrievability and due values in both flows.

The Docker frontend evidence is indexed in
[`stage-7 evidence`](../portfolio/evidence/stage-7/index.md).

## 4. Advanced Evaluation interpretation

The Agent evaluation measures the bounded local policy adapter's routing and
permission regression, not general model intelligence.  Pre-submit adversarial
requests cannot obtain grading or hidden answer fields because the tools are
absent from the pre-submit registry.  The deterministic artifact records six
cases with zero unnecessary and missing tool selections.

The personalization artifact measures scheduling behavior only: an explicit
weak-topic signal changes the next bounded schedule's topic match from 25% to
75%, an uplift of 50 percentage points.  It is not evidence of improved scores,
retention, clinical performance or educational outcomes.  Memory relevance
records selected relevant memory rate 1.0, irrelevant injection rate 0.0 and
cross-domain leakage count 0 on the controlled fixture.

## 5. Data and provider boundaries

- EndoBench remains `Evaluation-only`; it is not eligible for Tutor retrieval,
  Question Factory ingestion or learner-facing QBank inventory.
- CMExam, CMB-Exam, Kvasir-VQA and Kvasir-VQA-x1 remain local governed
  acceptance/import material.  Raw third-party data is not committed.
- General Domain Docker/CI content is the small project-authored fixture; ARC
  Easy is local-only import validation and is blocked from AI ingestion.
- Docker and hosted tests use the no-secret local policy adapter.  No external
  model credential is stored or claimed as verified.  Real provider acceptance
  remains an explicit provider-configured smoke path.
- Raw chain-of-thought is neither persisted nor exposed.  The UI may show a
  short user-facing reasoning summary from the typed event contract.

## 6. Known limitations

- The General Domain proof pack is intentionally small and demonstrates
  platform compatibility, not broad curriculum coverage.
- Human RAG ground-truth review and human Question Judge review remain
  deferred per the approved v1.0/Stage 4 decision; the current artifacts are
  engineering evaluations.
- The local clean-start uses compact checked-in teaching seed content.  A
  user-owned full QBank is still an explicit governed import, not a bundled
  public dataset catalogue.
- Hosted CI does not run the large local QBank or external-provider smoke.

## 7. Post-v2.0 backlog (not implemented)

Multi-Agent orchestration, VLM Tutor productization, public multi-tenancy/auth
redesign, deployment infrastructure, GraphRAG, additional vector stores or
queues, online model training and generic plugin discovery are explicitly
outside this release.

## 8. Release record

To be filled from the actual release operation:

- Release commit: `PENDING`
- Annotated tag: `v2.0.0`
- Hosted Actions run: `PENDING`

Stage 7 stops after the `v2.0.0` release and does not create a Stage 8.
