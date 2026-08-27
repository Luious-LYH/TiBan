# Stage 1 PostgreSQL Persistence Runtime Evidence

Date: 2026-08-28
Scope: final Stage 1 persistence Gate only; no Stage 2 code or schema was introduced.

## Runtime

Docker Desktop ran `postgres:16-alpine` from [`compose.stage1-postgres.yml`](../../compose.stage1-postgres.yml). The Compose profile publishes PostgreSQL only on `127.0.0.1:55432` and uses a named development volume. The container reached `healthy` state before the application checks began.

The application process was configured through `ENDO_DATABASE_URL` with the SQLAlchemy dialect `postgresql+psycopg`; password output was redacted in command results.

## Fresh migration and idempotent seed

From `code/backend`, against the new local PostgreSQL volume:

```powershell
$env:ENDO_DATABASE_URL = 'postgresql+psycopg://…@127.0.0.1:55432/endotutor_stage1'
$env:PYTHONPATH = '.'
alembic upgrade head
python -c "from app.db.bootstrap import initialize_database; print(initialize_database())"
python -c "from app.db.bootstrap import initialize_database; print(initialize_database())"
```

Results:

| Check | Result |
|---|---|
| Alembic dialect | `PostgresqlImpl` with transactional DDL |
| Revision | `0001_stage1_core` applied |
| First seed | `58` inserted questions |
| Repeat seed | `0` inserted questions |
| Tables | `alembic_version`, `question_banks`, `questions`, `practice_sessions`, `attempts`, `review_cards`, `source_documents` |
| Catalog counts | `5` banks, `58` questions |

## API submit and restart persistence

1. Started `uvicorn app.main:app --host 127.0.0.1 --port 8001` with the PostgreSQL URL above.
2. Called the real public question endpoint, selected a returned single-choice option ID, then posted to `/api/v3/practice/submit` for learner `stage1-postgres-runtime-proof`.
3. Received HTTP 200 with a generated `attempt_b35f856ab2d5`, the selected question ID, and `doctor_review_required=True`.
4. Stopped only that Uvicorn process, restarted the same command against the same Docker database, and called `/api/v3/overview?learner_id=stage1-postgres-runtime-proof` successfully (`api_source=backend`).
5. In a fresh Python process, queried the relational database directly:

```text
restart_engine postgresql+psycopg://endotutor_dev:***@127.0.0.1:55432/endotutor_stage1
persisted_attempts 1
persisted_review_cards 1
```

This proves the Stage 1 deterministic submit chain writes the append-only `Attempt` and its `ReviewCard` projection to PostgreSQL, rather than to a transient process store.

## PostgreSQL suite

```powershell
$env:ENDO_DATABASE_URL = 'postgresql+psycopg://…@127.0.0.1:55432/endotutor_stage1'
$env:PYTHONPATH = '.'
pytest -q
```

Result: **23 passed**. The suite includes public answer isolation, the four discriminated question variants, typed submission, persistence side effects, bank separation, and serializable overview contracts.

## Operational note

The Docker named volume was intentionally retained after verification, so no data-destructive Compose operation was used. The compose profile is local development evidence only; it does not contain production deployment or secret-management configuration.
