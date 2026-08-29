# Demo QBank Bootstrap Regression — v1.0

## Decision

The v1.0 Docker Demo must expose the approved Portfolio QBank on the learner
catalog after a clean start. The required learner-ready inventory is:

| Bank | Required count |
|---|---:|
| CMExam | 1,500 |
| CMB-Exam | 1,778 |
| curated Kvasir-VQA | 400 |
| **Portfolio total** | **3,678** |

The application may retain legacy, Factory, evaluation and research rows in the
same PostgreSQL database for audit or compatibility, but only `user_ready` rows
are learner-facing. EndoBench remains evaluation-only.

The Docker Compose profile and the standard Windows `Start-Web-Demo.ps1` /
Electron launcher both enable this bootstrap by default. Tests and deliberately
lightweight development can opt out with `ENDO_DEMO_QBANK_BOOTSTRAP=false`.

## Root cause fixed

The release image previously ran only the small legacy `seed_database()` path.
The Docker backend image also had no access to the repository `data/` directory
or the local VQA directory, so the real importers could not run after a clean
start. The bootstrap now runs after schema/legacy initialization only when
`ENDO_DEMO_QBANK_BOOTSTRAP=true`, fills missing stable-ID rows through the
existing governed importers, and fails loudly if a required local source is
missing.

## Runtime evidence

Acceptance stack: `refactor/v3-agent-learning-platform`, Docker Compose clean
start override, PostgreSQL on `127.0.0.1:55433`, API on `127.0.0.1:8003`.

| Check | Result |
|---|---|
| PostgreSQL priority bank counts | CMExam 1,500; CMB-Exam 1,778; Kvasir-VQA 400 |
| `/api/v3/question-banks` priority total | 3,678 |
| 0-question banks in learner catalog | 0 |
| zero bank detail endpoint | 404 |
| zero bank session creation | 404 |
| backend regression | 54 passed |
| generated API drift check | PASS |
| frontend lint / unit / build | PASS / 10 passed / PASS |
| post-restart priority counts | unchanged: 1,500 / 1,778 / 400 |

No PostgreSQL, Qdrant or Redis volume was removed. The bootstrap is additive and
idempotent: a later restart observes complete stable-ID inventory and performs
zero imports. Frontend startup now waits for the backend health check, so the
long first bootstrap is not presented as a transient API-ready state.

## Reproduction commands

```powershell
docker compose -p endotutor-v1-stage1-acceptance `
  -f docker-compose.yml -f compose.stage1-clean-start.override.yml up -d --build

Invoke-RestMethod http://127.0.0.1:8003/api/v3/question-banks
```

For another host, configure `ENDO_LOCAL_VQA_HOST_ROOT` in the untracked `.env`.
Do not store raw third-party datasets or provider secrets in the repository.
