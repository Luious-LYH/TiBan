# v1.2 Pragmatic Modular Monolith

TiBan remains one FastAPI deployment and one relational learning transaction.
Stage 6 adds code-level dependency direction only where it reduces an observed
maintenance risk.

```text
React → generated OpenAPI client → FastAPI transport
                                ↓
                      application use cases / Tutor runtime
                                ↓
                  deterministic learning rules + owned ports
                                ↓
 adapters: PostgreSQL · Qdrant · OpenAI-compatible provider · Redis/Dramatiq
```

The three changed slices are Practice/Learning, Tutor and Question Factory.
Routes map transport and invoke use cases; they do not grade, mutate FSRS or
memory, query Qdrant, or coordinate long-job state.  The existing atomic
`grade → Attempt → mastery → FSRS → memory` workflow remains synchronous and
contains no network I/O.

Deliberately not adopted: microservices, a DI container, repository-per-table,
a new agent framework, or a second job queue.
