# Security notes — Stage 4 v1.0

Audit date: 2026-08-29. This is an engineering dependency review, not a claim
that the application has completed a security certification.

## Resolved runtime dependency

`react-router-dom` was upgraded from `7.16.0` to `7.18.2`. The earlier direct
runtime dependency pulled in vulnerable `react-router` ranges, including the
reported redirect, XSS, DoS, and RSC-mode CSRF advisories. This is a same-major
release update with a published fix; API drift, lint, unit, build, and browser
Flow A are re-run as the release gate.

## Remaining audit result

After the routing update, `npm audit --omit=dev` reports no production runtime
vulnerabilities. Full `npm audit` still reports development/desktop packaging
transitives: 13 high and 1 critical. The affected chains are rooted in Electron
and `electron-builder` packaging dependencies (`tar`, `app-builder-lib`,
`dmg-builder`, `builder-util`, `electron-publish`, `form-data`, `nanoid`,
`postcss`, `undici`, and related transitive packages).

| Scope | Direct dependency? | Action in v1.0 |
|---|---|---|
| `react-router-dom` browser runtime | Yes | Upgraded to `7.18.2`; verified by release checks. |
| Electron / electron-builder packaging graph | Electron and electron-builder are direct dev dependencies; vulnerable nodes are transitive | Deferred: automatic remediation requests Electron 44 major changes and/or a broad build-chain rewrite. |

No `npm audit fix --force` was used. A forced Electron or packaging-tool update
could change desktop packaging behavior outside the Stage 4 freeze. Reassess the
remaining development-only findings before producing a public desktop installer.

## Secret and data handling

- Local provider settings live only in ignored `.env`; no API key, LAN endpoint,
  or provider credential is committed.
- BYOK evaluation keys are request-scoped and excluded from persisted results.
- Raw large data, normalized datasets, and local model caches remain ignored.
- Docker development credentials are local-only and must not be reused outside
  the supplied local Compose setup.
