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
| PostgreSQL runtime | NOT VERIFIED — no local PostgreSQL/Docker runtime available |

## Core-flow artifact

[core-flow.spec.ts](../../frontend/e2e/core-flow.spec.ts) starts the real FastAPI and Vite servers and exercises the main user journey with the seeded backend. It does not mock production API responses.

## Responsive evidence

All four pages were launched against the real local services at widths `375`, `768`, `1280`, and `1440`. Representative evidence also includes `practice-tutor-375.png`, captured after opening the mobile Tutor bottom sheet.

See [stage-1 evidence](../portfolio/evidence/stage-1/).

## Known environment limitation

The current machine has no `postgres`, `pg_ctl`, `psql`, Docker, Podman, or usable WSL distribution. Alembic migration and seed were nevertheless verified from zero against a fresh SQLite database, and the application remains PostgreSQL-configurable through `ENDO_DATABASE_URL`.
