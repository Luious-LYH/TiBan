# TiBan v2.0 product screenshots

These captures show one shared learning workspace across the Medical /
Endoscopy and General Science domain packs.

## Browser captures

- [`docker-banks-medical.png`](docker-banks-medical.png) — Medical / Endoscopy
  question bank catalog.
- [`docker-banks-general.png`](docker-banks-general.png) — General Science
  catalog using the same Banks page.
- [`docker-medical-practice.png`](docker-medical-practice.png) — Medical
  Practice workspace with the persistent right-side Tutor.
- [`docker-general-practice.png`](docker-general-practice.png) — General
  Practice workspace using the shared question and session layout.
- [`docker-general-tutor.png`](docker-general-tutor.png) — General Tutor chat
  with streamed response and source state.
- [`docker-general-feedback.png`](docker-general-feedback.png) — General
  deterministic submission feedback after an Attempt.

## Implementation artifacts

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
