# Stage 6 — v1.2 Agent Engineering report

## Current release decision

**Release candidate accepted pending final release commit and tag.** Stage 6
has not entered Stage 7. The initial Docker smoke failed because its
PowerShell test payload contained a literal backtick-n and produced zero
chunks; the corrected real multiline document completed the actual
Qdrant/embedding path, generated two revisions, and published the repaired
revision. Real 512-dimensional FastEmbed vectors were used; no hash, random,
or checksum vectors were introduced.

## Implemented

- Current architecture audit and selective TechSpar lessons.
- Practice route → `PracticeUseCases` → `PracticeWorkflowPort` → existing
  Stage 5 transactional service adapter. The deterministic sequence remains
  `grade → Attempt → mastery → FSRS → learning memory`.
- Tutor dependency boundary. SQLAlchemy, retrieval, recent-mistake and memory
  adapters are outside the runtime; fake model/retrieval tests exercise the
  real AgentEvent/tool/source lifecycle without external services.
- Provider error taxonomy for auth, rate-limit and timeout classes.
- PostgreSQL durable Factory job columns and migration, state transitions,
  idempotency, retry of failed/cancelled input, cancellation request,
  heartbeat/stale recovery, durable error fields and stage event ledger.
- OpenAPI client regeneration and the small Factory UI adjustment to display
  durable lifecycle/stage/progress.

## Evidence

| Gate | Result |
| --- | --- |
| Current architecture audit | PASS — `stage-6-current-architecture-audit.md` |
| Real-QBank bootstrap | PASS — CMExam 1,500 + CMB-Exam 1,778 + Kvasir curated 400 = 3,678 in isolated local smoke |
| Practice/Tutor focused tests | PASS |
| Factory idempotency/stale recovery/architecture guard | PASS in isolated test database |
| Frontend build | PASS |
| Docker PostgreSQL/Qdrant/Redis/backend/worker/frontend startup | PASS with isolated validation override; validation frontend CORS corrected for `5176` |
| Docker Practice submit + Tutor SSE | PASS — PostgreSQL canonical state + local test adapter event stream |
| Docker Memory personalization flow | PASS — PostgreSQL-backed before/after and two-learner differentiation assertions |
| Docker real Factory parse/index/generate/judge/repair/publish path | PASS — `factory_8d2c76c9b99e`, `result_ref=revision_d30e522b7074`, 2 revisions, published repaired revision |
| Host local OpenAI-compatible Tutor smoke | PASS — 3/3 complete event streams; Docker keeps local adapter default for reproducibility |
| Hosted GitHub Actions | PASS — run `33319291801`, commit `23a643a` |
| `v1.2.0` tag | Pending final release commit/tag operation |

Evidence files are under `artifacts/engineering/` and the [Stage 6 evidence
index](../portfolio/evidence/stage-6/README.md). The initial smoke-script
failure boundary and corrected acceptance result are recorded in
`docker-factory-acceptance-v1.json`.

## Minimal recovery command

If the worker image is rebuilt on another machine, run:

```powershell
docker compose -p tibanstage6 -f docker-compose.yml -f compose.stage6-validation.override.yml build backend worker
docker compose -p tibanstage6 -f docker-compose.yml -f compose.stage6-validation.override.yml up -d backend worker frontend
```

Then submit one allowed Markdown document through
`POST http://127.0.0.1:8004/api/v3/factory/documents`, create its Factory job,
and verify `status=succeeded`, `stage=ready_for_review`, `progress=100`, and a
non-empty revision list. No secret is required for the deterministic Factory
adapter, but a valid real embedding model is required by the approved RAG
architecture. For the user-owned local Provider, run Tutor on the host or set
an explicit private-network runtime override; the checked-in Docker topology
does not embed a gateway address or credential.

## Deliberately not changed

No Stage 5 learning thresholds, adaptive-selection semantics, Tutor permission
boundary, raw QBank source files, UI redesign, second queue, microservices,
generic agent framework, or Stage 7 capability was introduced.
