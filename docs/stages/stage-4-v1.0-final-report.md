# Stage 4 — v1.0 Interview Ready final report

**Status:** local Release Gate complete; hosted CI is `external_pending`.

Stage 4 freezes the product as v1.0 Interview Ready. No Stage 5 memory or
personalization feature work is included.

## What was finalized

- Performed a learner-facing copy audit across overview, banks, practice/Tutor,
  Factory, and evaluation. Engineering/audit vocabulary remains in Developer
  Detail and evidence only; product copy uses learner-facing states.
- Restored and verified the complete Docker demo QBank bootstrap: CMExam 1,500,
  CMB-Exam 1,778, curated Kvasir-VQA 400, total 3,678.
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
| QBank bootstrap | PASS | Docker acceptance catalog presents the complete 3,678-question portfolio demo. |
| Backend regression | PASS | `python -m pytest -q`: 55 passed (local adapter mode). |
| OpenAPI drift | PASS | `npm run api:check`. |
| Frontend quality | PASS | lint, 10 unit tests, production build. |
| Playwright core flow | PASS | `Flow A: practice → continuous Tutor → submit → explain`. |
| Docker topology | PASS | `docker compose ... config --quiet`; local acceptance stack healthy. |
| Runtime secret/data scan | PASS | No secret, local provider URL, or large data was staged; `.env` stays ignored. |
| README / evidence / résumé / interview package | PASS | README, evidence matrix, screenshot index, résumé files, interview Q&A, and demo script synchronized. |
| Hosted GitHub Actions | EXTERNAL PENDING | No Git remote is configured in this checkout. |
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

Run the following after configuring the intended remote:

```powershell
git push origin refactor/v3-agent-learning-platform
```

Then confirm the **EndoTutor fast profile** workflow is green. The existing
`v1.0.0` tag points to an earlier commit and was not moved. Stage 4 should create
an annotated `v1.0.0-rc1` candidate locally; promote or retag `v1.0.0` only after
the hosted run is green and the existing-tag conflict is explicitly resolved.

## Known limitations

- Human review of the RAG relevance labels and Judge label set is intentionally
  deferred; no expert or clinical-validation claim is made.
- Provider acceptance is an engineering smoke, not a model-quality or clinical
  benchmark.
- The committed CI fast profile covers the core Tutor practice flow. The full
  Factory job is separately accepted on the real Docker backend/Redis/Qdrant/
  worker topology because it requires those services and the real embedding path.
- Desktop packaging dependencies still require a deliberate future security
  upgrade review before public installer distribution.

## Stop boundary

Stage 4 ends with this report. Do not enter Stage 5 automatically.
