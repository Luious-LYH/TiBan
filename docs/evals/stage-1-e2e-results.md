# Stage 1 E2E and Screenshot Evidence

## Commands

```powershell
cd code/frontend
npm run test
npm run lint
npm run build
npm run test:e2e
```

## Results

| Check | Result |
|---|---|
| Vitest + React Testing Library | PASS — 6 tests |
| ESLint | PASS — zero errors/warnings in active Stage 1 source |
| TypeScript + Vite build | PASS |
| Playwright core flow | PASS — Overview → Banks → Practice → Submit → Feedback → Next |
| Responsive capture flow | PASS — 16 page screenshots + mobile Tutor sheet |
| PostgreSQL runtime | PASS — Docker PostgreSQL 16 health, migration, seed/idempotency, submit/review-card and restart persistence |

## Core-flow artifact

[core-flow.spec.ts](../../frontend/e2e/core-flow.spec.ts) starts the real FastAPI and Vite servers and exercises the main user journey with the seeded backend. It does not mock production API responses.

## Responsive evidence

All four pages were launched against the real local services at widths `375`, `768`, `1280`, and `1440`. Representative evidence also includes `practice-tutor-375.png`, captured after opening the mobile Tutor bottom sheet.

See [stage-1 evidence](../portfolio/evidence/stage-1/).

## PostgreSQL runtime evidence

The final database Gate used the local Docker Desktop `postgres:16-alpine` profile in [`compose.stage1-postgres.yml`](../../compose.stage1-postgres.yml), exposed only at `127.0.0.1:55432`. It was started from a fresh named volume. The application connected using `ENDO_DATABASE_URL=postgresql+psycopg://…@127.0.0.1:55432/endotutor_stage1`.

Detailed commands and results are captured in [stage-1-postgres-persistence.md](stage-1-postgres-persistence.md). SQLite is still supported only as the no-Docker development fallback; it is not used as evidence for the PostgreSQL Gate.
