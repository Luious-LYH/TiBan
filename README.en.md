<div align="center">

# TiBan

### An Agent-native learning workspace for every domain

Question banks, contextual tutoring, knowledge retrieval, and review scheduling
come together as one continuously improving learning path.

[中文 README](./README.md)

</div>

![TiBan learning overview](./docs/v3/evidence/readme/01-overview-1440.png)

## TiBan in one sentence

TiBan is an Agent-native adaptive learning workspace for organizing question
banks, learning materials, and progress across domains. It turns each answer
into a useful next step through contextual tutoring, governed retrieval,
review scheduling, and persistent learning memory.

The repository includes a Medical / Endoscopy Demo Domain Pack to demonstrate a
complete professional-learning journey. The shared learning engine, Tutor,
Mentor Agent, RAG, FSRS, memory, and question-import workflows are designed to
be reused with additional domain packs.

## Product experience

Learners choose a question bank, enter Practice or Exam, answer in a focused
workspace, and ask the learning assistant for hints or explanations. After
submission, TiBan records the attempt, updates mastery and FSRS scheduling, and
keeps the result available for future review.

The learning assistant understands the current question, learning mode, and
conversation context. When supporting material is genuinely useful, it
retrieves enabled sources and presents readable citations beside the answer.
The Mentor Agent extends this context across question banks and sessions so
learners can decide what to review next, revisit mistakes, and explore a topic.

## Core capabilities

- **Question banks and Practice** — browse question states, start a focused
  session, submit answers, and continue through a durable learning loop.
- **Contextual learning assistant** — controlled tools, mode-aware permissions,
  SSE streaming, retrieval status, and inline citations.
- **Mentor Agent** — cross-session view of recent attempts, review scheduling,
  bank progress, learning memory, and enabled knowledge sources.
- **Question import** — validate CSV / JSONL / Markdown banks or generate
  reviewable drafts from teaching documents through a durable workflow.
- **Knowledge library** — parse, index, enable, disable, reindex, and preview
  PDF, DOCX, Markdown, and TXT sources.
- **Evaluation Lab** — freezes an EvalSuite before comparing runtime models or
  versioned RetrievalProfiles through durable background experiments.

## A connected learning path

```text
Choose a question bank
        ↓
Practice / Exam
        ↓
Answer with contextual tutoring
        ↓
Immediate grading and explanation
        ↓
Mastery · FSRS review · learning memory
        ↓
A better next session
```

## Product interface

The following views show the main TiBan experience and the core learning loop.

<table>
  <tr>
    <td width="50%"><strong>Learning overview</strong><br><img src="./docs/v3/evidence/readme/01-overview-1440.png" alt="TiBan learning overview" width="100%"></td>
    <td width="50%"><strong>Practice + learning assistant</strong><br><img src="./docs/v3/evidence/readme/04-practice-tutor-selected-1440.png" alt="Practice with the learning assistant" width="100%"></td>
  </tr>
  <tr>
    <td width="50%"><strong>Question bank details</strong><br><img src="./docs/v3/evidence/readme/03-bank-detail-1440.png" alt="Question bank details and status" width="100%"></td>
    <td width="50%"><strong>Mentor Agent</strong><br><img src="./docs/v3/evidence/readme/05-mentor-agent-1440.png" alt="Mentor Agent workspace" width="100%"></td>
  </tr>
  <tr>
    <td width="50%"><strong>Knowledge library</strong><br><img src="./docs/v3/evidence/readme/08-knowledge-library-1440.png" alt="Knowledge library" width="100%"></td>
    <td width="50%"><strong>Model evaluation</strong><br><img src="./docs/v3/evidence/readme/07-model-evaluation-1440.png" alt="Model evaluation workspace" width="100%"></td>
  </tr>
</table>

## Agent-native architecture

TiBan places Agent capabilities inside a real learning workflow:

- **Context-aware tutoring** — every request carries the current question,
  learner, mode, and learning phase, with clear Study, Exam, and Review
  permissions.
- **Governed retrieval** — sources are searched only when useful; domain,
  namespace, relevance, and deduplication gates keep citations focused.
- **Persistent learning memory** — memory is distilled from real attempts and
  review facts to inform the next learning step.
- **FSRS review scheduling** — every submission contributes to a durable review
  schedule.
- **Durable Question Factory** — parsing, generation, quality gates, revision,
  human review, and publishing remain traceable and recoverable.
- **Reproducible Evaluation Lab** — freezes question samples, prompt and runtime
  conditions in an EvalSuite. Model runs use temperature=0 and no fallback;
  RAG runs share the product RagService and only change a versioned RetrievalProfile.
- **Domain Pack architecture** — content, terminology, and policy stay in a
  domain pack while the learning engine and Agent capabilities remain reusable.

## Technology

```text
React 19 + TypeScript + Vite
        │  generated OpenAPI client + SSE
        ▼
FastAPI + Pydantic + SQLAlchemy
        ├─ PostgreSQL: question banks, attempts, reviews, sources, and jobs
        ├─ Qdrant + BGE-M3: governed retrieval and semantic memory
        ├─ Redis + Dramatiq: durable import, indexing, and reflection jobs
        ├─ py-fsrs: review scheduling
        └─ OpenAI-compatible providers: controlled model access
```

## Quick start

Requirements: Python 3.12+, Node.js 22+, npm, and Docker Desktop.

```powershell
git clone https://github.com/Luious-LYH/TiBan.git
cd TiBan
docker compose up --build
```

Open `http://127.0.0.1:5173/` and follow:

```text
/banks → bank details → Practice → submit → Review
```

For a guided walkthrough, see the [Demo Flow](./docs/v3/portfolio/V3_DEMO_FLOW.md),
[Tutor and Mentor Agent architecture](./docs/architecture/tutor-agent.md), and
[data attribution policy](./THIRD_PARTY_DATA.md).

## Data and safety

- Large third-party datasets remain outside the public repository and are
  imported only in authorized local environments.
- API keys stay in local environment configuration or request-scoped runtime
  settings; they are never written to browser storage or Git.
- Knowledge sources keep their own metadata, versions, parsed chunks, and
  retrieval status.
- Medical teaching output retains physician-review boundaries and is not a
  substitute for clinical diagnosis or treatment decisions.

## Support TiBan

TiBan is independently maintained. If it helps your learning or project
experience, you can support continued development on
[Afdian](https://afdian.com/a/tiban).
