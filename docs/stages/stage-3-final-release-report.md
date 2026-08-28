# Stage 3 final release report

**Status:** complete after the final local release gates listed below; no
Stage 4 work is authorized or started.

## What shipped

- Pre-release hardening retained and documented: Knowledge Corpus v1, RAG v2,
  real Provider-backed Factory acceptance, Judge v2, and PostgreSQL QBank scale
  acceptance.
- A real BYOK Model Evaluation workbench now lists frozen CMExam text and
  EndoBench VLM packs, tests a provider, runs bounded no-fallback evaluations,
  hides per-case Gold by default, and exposes an explicit reveal action.
- Generated OpenAPI client flow, CI fast profile, Docker core stack, technical
  architecture diagram, evidence matrix, résumé variants, interview Q&A and
  demo script are checked in.

## Final gates

| Gate | Result | Evidence |
|---|---|---|
| Study / Exam / Review | PASS | PostgreSQL-backed core Playwright Flow A and backend regression |
| Tutor real loop / SSE / permission | PASS | `docs/architecture/tutor-agent.md`, Tutor tests and prior provider artifact |
| Knowledge / RAG / citation / isolation | PASS | RAG v2, knowledge index and governance tests |
| Factory provider / Judge / lineage | PASS | Factory provider artifact and Judge v2 evaluation |
| Attempt / mastery / py-fsrs | PASS | learning tests and FSRS comparison |
| Text Model Evaluation | PASS | `evalrun_8ca3f74df1064f`, 5 cases, valid parse 1.0, fallback false |
| EndoBench VLM path | PASS | `evalrun_fcb3a57b3e934e`, real image attached; incorrect answer retained |
| Secret / fallback boundary | PASS | `test_model_evaluation.py`, no-fallback provider calls |
| API generation / frontend quality | PASS | repeated `api:generate` hash stable; `api:check`, lint, unit, build |
| Docker topology / CI definition | PASS | `docker compose config`, `.github/workflows/ci.yml` |
| Browser visual matrix | PASS | 20/20 route × viewport checks, no console/page errors; fresh Evaluation screenshots |
| Portfolio materials | PASS | `docs/portfolio/` final matrix, scripts and Stage 3 evidence index |

## Tests and acceptance

Run from the documented commands in `README.md`:

- Backend: full `python -m pytest -q` — **51 passed** on the PostgreSQL
  configured runtime.
- Frontend: `npm run api:check`, `npm run lint`, `npm test` — **8 passed** —
  and `npm run build`.
- Browser: `npx playwright test e2e/core-flow.spec.ts` — **2 passed** — plus
  20 route × viewport checks and Stage 3 Evaluation screenshots at
  375/768/1280/1440.
- Docker: compose configuration resolves the frontend, backend, PostgreSQL,
  Qdrant, Redis and worker topology without deleting or replacing existing
  local volumes.

## Real provider status

The configured local OpenAI-compatible provider completed the bounded text and
visual acceptance runs with `fallback=false`. The fresh browser text run
`evalrun_8ca3f74df1064f` returned 5 valid answers with accuracy 1.0; the
visual run attached one EndoBench image and returned a valid but incorrect
answer, which is intentionally recorded as an incorrect case. No new external
secret or paid authorization was required.

## Known limitations

- RAG and Judge fixtures are portfolio-sized; their final named human review
  status remains `pending`. They are not clinical effectiveness studies.
- Model acceptance is a small engineering run, not a leaderboard or clinical
  benchmark. Larger samples require an explicit evaluation budget.
- Langfuse and OpenTelemetry remain optional/deferred. Existing ToolReceipt,
  AgentEvent, artifact and audit paths are the canonical evidence surface.
- The Docker image build installs the full backend requirements and may take
  time on a clean machine; CI does not download large datasets or models.
- Hosted GitHub Actions was not dispatched from this local session; the checked
  in fast-profile workflow is covered by the same local backend/frontend
  commands plus the Playwright smoke command.
- The legacy `scripts/ui_smoke.mjs` has a DevTools URL-creation incompatibility
  with the installed Edge; its route results are not used for this release.

## Resume-safe claims

Use only the claims and exact numbers in
[`FINAL_EVIDENCE_MATRIX.md`](../portfolio/FINAL_EVIDENCE_MATRIX.md). Do not
claim autonomous diagnosis, Judge perfection, Multi-Agent architecture or
30万题 runtime validation.

## Stop boundary

Stage 3 ends here. No additional Feature work is started by this release.
