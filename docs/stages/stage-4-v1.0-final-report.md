# Stage 4 — v1.0 Interview Ready final report

**Status:** v1.0 promotion evidence recorded; hosted CI passed for the promoted
release baseline. The existing public `v1.0.0` tag remains immutable; v1.0.1
is the safe promotion version.

Stage 4 freezes the product as v1.0 Interview Ready. No Stage 5 memory or
personalization feature work is included.

## What was finalized

- Performed a learner-facing copy audit across overview, banks, practice/Tutor,
  Factory, and evaluation. Engineering/audit vocabulary remains in Developer
  Detail and evidence only; product copy uses learner-facing states.
- Reframed large third-party QBanks as optional, locally authorized
  import-validation fixtures. The public clean start uses a compact teaching
  seed; raw data remains ignored and is not a product-owned catalogue.
- Kept Dense as the frozen v1.0 Tutor retrieval default while retaining sparse,
  hybrid, and rerank implementations and benchmark evidence.
- Preserved the adaptive learning loop evidence: `Attempt → mastery → FSRS →
  weak-topic next session`.
- Fixed a real Tutor SSE protocol regression: every completed turn emits a
  typed source event after tool receipts and before the final response. A
  no-source lifecycle marker is hidden from learner source cards.
- Fixed a real Factory Docker handoff regression: backend and Dramatiq worker
  now share a named upload volume. Unreadable uploads become a persisted failed
  job instead of an unhandled retry loop.
- Updated release packaging, screenshot evidence, portfolio matrix, 90-second
  demo script, security notes, and README.

## Release Gate evidence

| Gate | Result | Evidence |
|---|---|---|
| Browser product smoke | PASS | Docker browser audit for `/`, `/banks`, `/practice`, `/eval`; screenshots in `docs/portfolio/evidence/stage-4/`. |
| Learner UI copy audit | PASS | Active routes do not expose backend, artifact, Dramatiq, schema, revision lineage, or pending-human-review copy. |
| Tutor protocol / permission | PASS | `tests/test_tutor_agent_v1.py`: 8 passed; full backend suite covers adversarial pre-submit isolation. |
| Adaptive learning loop | PASS | `artifacts/learning/adaptive-loop-demo-v1.json` proves a deliberate error produces `weak_topic` next-session selection. |
| Retrieval default documentation | PASS | README and evidence matrix accurately scope Dense as a frozen engineering decision, not universal superiority. |
| Factory durable job | PASS | Docker document upload reached `ready_for_review` after parse, Qdrant index, Generator, Judge, repair, and revision lineage. |
| QBank bootstrap | PASS | Docker clean start uses the compact teaching seed. Optional local QBank bootstrap remains explicitly opt-in for authorized adapter validation. |
| Backend regression | PASS | `python -m pytest -q`: 55 passed (local adapter mode). |
| OpenAPI drift | PASS | `npm run api:check`. |
| Frontend quality | PASS | lint, 10 unit tests, production build. |
| Playwright core flow | PASS | `Flow A: practice → continuous Tutor → submit → explain`. |
| Docker topology | PASS | `docker compose ... config --quiet`; local acceptance stack healthy. |
| Runtime secret/data scan | PASS | No secret, local provider URL, or large data was staged; `.env` stays ignored. |
| README / evidence / résumé / interview package | PASS | README, evidence matrix, screenshot index, résumé files, interview Q&A, and demo script synchronized. |
| Hosted GitHub Actions | PASS | [Run 33296518709](https://github.com/Luious-LYH/TiBan/actions/runs/33296518709) passed backend, frontend, and Playwright Flow A for `86fb139`. |
| Human RAG/Judge review | DEFERRED | Per Stage 4 scope; not a release blocker and not shown in learner UI. |

## Provider acceptance

The configured local OpenAI-compatible provider was verified through the host
adapter for tool selection and final response composition. Docker Desktop could
not reach the LAN gateway from the container network, so container-side provider
acceptance is intentionally not claimed. The product surfaces a genuine model
connection failure rather than a fake successful response.

## Security

`react-router-dom` was moved from `7.16.0` to `7.18.2`, removing the audited
runtime `react-router` finding. The remaining `npm audit` findings are in the
Electron/electron-builder development packaging chain and are documented in
[`SECURITY_NOTES.md`](../../SECURITY_NOTES.md); no forced upgrade was used.

## Hosted CI handoff and tag

The release branch is published to
[`Luious-LYH/TiBan`](https://github.com/Luious-LYH/TiBan). The **EndoTutor fast
profile** hosted run above is green. The existing public `v1.0.0` tag was not
moved. Promotion therefore creates an annotated `v1.0.1` tag without any force
push or historic-tag rewrite.

## Known limitations

- Human review of the RAG relevance labels and Judge label set is intentionally
  deferred; no expert or clinical-validation claim is made.
- Provider acceptance is an engineering smoke, not a model-quality or clinical
  benchmark.
- The committed CI fast profile covers the core Tutor practice flow. The full
  Factory job is separately accepted on the real Docker backend/Redis/Qdrant/
  worker topology because it requires those services and the real embedding path.
- Large external QBanks are intentionally not committed or required for the
  default Docker start. They are local, authorized fixtures only; future
  product use is governed user/organization-owned source intake.
- Desktop packaging dependencies still require a deliberate future security
  upgrade review before public installer distribution.

## Stop boundary

Stage 4 ends with this report. Do not enter Stage 5 automatically.
