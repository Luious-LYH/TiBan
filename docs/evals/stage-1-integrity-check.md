# Stage 1 Integrity Check for Stage 2

Date: 2026-08-28

## OpenAPI client

Result: **PASS after remediation**.

The previous `frontend/src/api/generated.ts` was a hand-maintained contract mirror. Stage 2 replaced it with a deterministic generation chain:

```text
FastAPI app.openapi()
  -> backend/scripts/export_openapi.py
  -> frontend/.generated/openapi.json (ignored)
  -> openapi-typescript
  -> frontend/src/api/generated.ts
```

Commands:

```powershell
cd frontend
npm run api:generate
npm run api:check
```

`generated.ts` now starts with the generator banner and is not manually maintained. `api:check` regenerates it and fails if the tracked output drifts. `src/api/client.ts` is the only canonical client; it uses `openapi-fetch` parameter and response types derived from that generated schema. Small view-model projections in that file only normalize optional OpenAPI defaults for rendering; they do not define independent API response schemas.

## Lint isolation

Result: **PASS after remediation**.

The old global ignores `src/lib/**/*` and `src/pages/*.tsx` were replaced by explicit quarantined legacy file names. The active route tree remains linted:

```text
src/app/router.tsx
  -> pages/overview/OverviewPage.tsx
  -> pages/banks/BanksPage.tsx
  -> pages/practice/PracticePage.tsx
  -> pages/evaluation/EvaluationPage.tsx
  -> api/client.ts -> api/generated.ts
```

Caller/import search found no active-route import of `src/lib/api.ts`, `src/lib/v3Api.ts`, `src/lib/adapters.v2.2.2.ts`, or top-level legacy pages. The legacy files remain untouched and are quarantined solely to avoid rewriting historical portfolio routes outside the canonical product bundle.

Validation completed:

```text
npm run build  PASS
npm run lint   PASS
```

## Database acceptance baseline

Stage 2 integration acceptance uses the existing healthy Docker PostgreSQL 16 runtime at `127.0.0.1:55432`, configured through `ENDO_DATABASE_URL=postgresql+psycopg://…`. SQLite remains limited to isolated unit/developer fallback use and is not the Stage 2 integration authority.
