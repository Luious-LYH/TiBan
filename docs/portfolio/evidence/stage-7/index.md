# Stage 7 / v2.0.0 Evidence Index

All captures below are local Docker acceptance evidence from the same clean
stack used by `artifacts/platform/docker-acceptance-v2.json`.  They show the
shared learner UI and domain switch; no secrets, raw third-party datasets,
vector IDs or internal scores are included.

## Browser captures

- [`docker-banks-medical.png`](docker-banks-medical.png) — Medical / Endoscopy
  domain catalog.
- [`docker-banks-general.png`](docker-banks-general.png) — General Science
  catalog filtered through the same Banks page.
- [`docker-medical-practice.png`](docker-medical-practice.png) — Medical
  practice workspace with the persistent right-side Tutor.
- [`docker-general-practice.png`](docker-general-practice.png) — General
  practice workspace using the shared question/session layout.
- [`docker-general-tutor.png`](docker-general-tutor.png) — General Tutor SSE
  transcript/source state on the right side.
- [`docker-general-feedback.png`](docker-general-feedback.png) — General
  deterministic submission feedback after an Attempt.

## Machine-readable artifacts

- [`domain-core-reuse-v2.json`](../../../../artifacts/platform/domain-core-reuse-v2.json)
- [`cross-domain-isolation-v2.json`](../../../../artifacts/platform/cross-domain-isolation-v2.json)
- [`general-domain-flow-v2.json`](../../../../artifacts/platform/general-domain-flow-v2.json)
- [`agent-tool-selection-v2.json`](../../../../artifacts/platform/agent-tool-selection-v2.json)
- [`memory-relevance-v2.json`](../../../../artifacts/platform/memory-relevance-v2.json)
- [`personalization-uplift-v2.json`](../../../../artifacts/platform/personalization-uplift-v2.json)
- [`docker-acceptance-v2.json`](../../../../artifacts/platform/docker-acceptance-v2.json)

## Verification commands

```text
backend: python -m pytest -q                         → 76 passed
backend: python -m pytest -q tests/test_stage7_platform.py → 8 passed
backend: python scripts/check_architecture_guard.py  → PASS
frontend: npm run api:check                          → PASS
frontend: npm run lint                               → PASS
frontend: npm test -- --run                          → 12 passed
frontend: npm run build                              → PASS
Playwright: Flow A + Flow C                         → 2 passed
Docker: python scripts/run_stage7_docker_acceptance.py → all acceptance flags true
Hosted Actions: run 33362264760                      → success
```
