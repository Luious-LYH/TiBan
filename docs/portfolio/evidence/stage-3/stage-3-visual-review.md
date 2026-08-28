# Stage 3 visual review

The current frontend was checked in fresh Edge sessions at 375px, 768px,
1280px and 1440px. The route matrix covered `/`, `/banks`, both real QBank
practice entry points and `/eval` at all four widths: 20/20 checks passed with
HTTP 200, no console errors and no page errors. The core Playwright flow then
passed both the learning and Factory paths against the PostgreSQL-configured
backend and active Redis/Dramatiq worker.

- The configuration card remains the primary action surface.
- API key is a password input with a persistent request-scoped privacy note.
- EndoBench displays its Evaluation-only boundary and image requirement.
- Pending, provider error, completed-with-failures and explicit Gold reveal are
  represented by real query/mutation states; no timer-based fake progress is
  used.
- Long hashes, run IDs and provider model labels wrap inside the Developer
  Detail disclosure; the mobile case answer grid collapses to one column.
- The medical safety notice remains visible at the bottom of the workbench.

The repository's older `scripts/ui_smoke.mjs` was also retried. Its Edge
DevTools `/json/new` adapter created `/` for every requested route, so it is
not used as the acceptance signal here; Playwright navigation is the
authoritative browser check for this release.
