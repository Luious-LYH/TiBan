# Stage 6 TechSpar lessons applied selectively

Source reviewed: [AnnaSuSu/TechSpar architecture guide](https://github.com/AnnaSuSu/TechSpar/blob/main/docs/typescript-backend-architecture.md), its `packages/core`, `packages/contracts`, `packages/providers`, and `apps/api` route composition (reviewed for Stage 6; not copied).

1. **Why Core does not depend on Hono/Drizzle:** HTTP and ORM types make rules
   difficult to test or reuse. TiBan therefore keeps FastAPI and SQLAlchemy at
   transport/adapters while deterministic practice and Tutor orchestration use
   internal request/result shapes.
2. **Why ports belong to the user:** the Tutor and Factory define only the
   operations they need. Their adapters implement those small contracts; no
   global `interfaces/` catalogue is introduced.
3. **Why routes only map transport:** routes validate/map HTTP and invoke a
   use case. They do not grade answers, mutate FSRS/memory, inspect Qdrant, or
   dispatch business flow.
4. **Why jobs persist state:** Redis/Dramatiq confirms delivery, not business
   completion. PostgreSQL is the Factory job source of truth for status,
   progress, inputs, results, retry/recovery and cancellation.
5. **Why not microservices:** this product has one deployment, a shared
   PostgreSQL transaction for learning facts, and no demonstrated independent
   scaling boundary. Code-level boundaries reduce coupling without distributed
   failure modes.
6. **Why hexagonal is not many classes:** a port exists only for a real
   external dependency or a useful fake test seam. Pure grading and FSRS rules
   stay functions.
7. **Applicable ideas:** explicit request/correlation context, dependency
   direction, adapter conversion to internal types, durable job state, and
   import guards.
8. **Not adopted:** TypeScript/Bun/Hono/Drizzle migration, shared Zod package,
   Electron sidecar assumptions, a global DI container, and per-module
   repository proliferation. FastAPI OpenAPI → generated TypeScript remains
   TiBan's canonical contract workflow.
