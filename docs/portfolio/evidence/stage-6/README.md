# Stage 6 evidence index

## Browser evidence

- [Docker Practice + Tutor workspace](./practice-tutor-docker.png) — captured from the isolated Stage 6 frontend at `127.0.0.1:5176` after the validation CORS allowlist was corrected.
- [Stage 4 product screenshot index](../stage-4/README.md) — retained baseline product evidence; Stage 6 intentionally does not redesign the UI.

## Engineering evidence

- [Route/use-case boundary](../../../../artifacts/engineering/route-usecase-boundary-v1.json)
- [Fake provider adapter](../../../../artifacts/engineering/provider-fake-adapter-v1.json)
- [Durable job recovery](../../../../artifacts/engineering/durable-job-recovery-v1.json)
- [Architecture guard](../../../../artifacts/engineering/architecture-guard-v1.json)
- [Docker acceptance](../../../../artifacts/engineering/docker-factory-acceptance-v1.json)
- [Stage 5 memory smoke](../../../../artifacts/engineering/real-qbank-memory-smoke-v1.json)

The Stage 6 browser gate is a smoke artifact, not a visual redesign claim. The
authoritative behavior evidence remains the backend regression suite,
OpenAPI drift guard, frontend tests/build, Docker acceptance, and hosted CI.
