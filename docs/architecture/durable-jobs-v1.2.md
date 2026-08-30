# v1.2 Durable Question Factory Jobs

`factory_jobs` is the durable source of truth. Redis/Dramatiq is delivery and
execution only. A job stores its type, lifecycle status, human-readable stage,
progress, input summary, result reference, normalized error, attempt count,
idempotency key, heartbeat and timestamps.

Lifecycle: `queued → running → succeeded | failed | cancelled`; `retrying`
is only a recovery bridge. Workflow stages (`parsing`, `indexing`,
`generating`, `judging`, `repairing`, `ready_for_review`, `published`) are
persisted events, not fake UI timers.

Duplicate document-version/prompt-config submissions reuse an active durable
job. Worker checkpoints honour cancellation. A stale running heartbeat is
recorded as `worker_stale`, transitioned through `retrying`, and returned to
`queued` for explicit re-dispatch. Provider or index failures become a failed
job with a durable error code; no local generator is substituted for a failed
configured provider.
