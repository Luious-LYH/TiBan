# Stage 6 — v1.2 Agent Engineering report

## Current release decision

**Release blocked pending real dense-embedding acceptance.** Stage 6 has not
been marked completed, `v1.2.0` has not been tagged, and Stage 7 has not been
started. This is an environment acceptance block, not a product fallback:
the real Qdrant Factory path cannot complete while the configured
`BAAI/bge-small-zh-v1.5` FastEmbed files in the worker image have a size
mismatch. Hash, random, or checksum vectors were not introduced.

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
| Docker PostgreSQL/Qdrant/Redis/backend/worker/frontend startup | PASS with isolated validation override |
| Docker Practice submit + Tutor SSE | PASS |
| Docker real Factory parse/index/generate/judge path | **PENDING** — dense model cache mismatch |
| Hosted GitHub Actions | NOT RUN — release commit is intentionally not created while a required acceptance gate is blocked |
| `v1.2.0` tag | NOT CREATED |

Evidence files are under `artifacts/engineering/`; the failed real Docker
Factory result is recorded in `docker-factory-acceptance-v1.json`.

## Minimal recovery command

After making the complete FastEmbed model available to the Docker worker's
`ENDO_EMBEDDING_CACHE` (or allowing the worker to finish a valid download),
run:

```powershell
docker compose -p tibanstage6 -f docker-compose.yml -f compose.stage6-validation.override.yml build backend worker
docker compose -p tibanstage6 -f docker-compose.yml -f compose.stage6-validation.override.yml up -d backend worker frontend
```

Then submit one allowed Markdown document through
`POST http://127.0.0.1:8004/api/v3/factory/documents`, create its Factory job,
and verify `status=succeeded`, `stage=ready_for_review`, `progress=100`, and a
non-empty revision list. No secret is required for the deterministic Factory
adapter, but a valid real embedding model is required by the approved RAG
architecture.

## Deliberately not changed

No Stage 5 learning thresholds, adaptive-selection semantics, Tutor permission
boundary, raw QBank source files, UI redesign, second queue, microservices,
generic agent framework, or Stage 7 capability was introduced.
