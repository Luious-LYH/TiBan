<div align="center">

# TiBan

### An Agent-native adaptive learning workspace for every domain

Question banks, contextual tutoring, knowledge retrieval, and review scheduling
work together as one learning path that remembers where the learner is.

[中文 README](./README.md) | [Live Demo](https://tiban.liuaihub.com/) | [Desktop app (v3.3.1)](https://github.com/Luious-LYH/TiBan/releases/download/v3.3.1/%E9%A2%98%E4%BC%B4%20TiBan-3.3.1-x64-Portable.exe)

Current release: **v3.5.2** · [release notes](./docs/releases/V3.5.2.md)

> Recommended: try the live Demo for the latest V3.5.2 product experience. The Windows desktop package remains v3.3.1 and is kept as a compatibility download.

</div>

<p align="center">
  <img src="./docs/v3/evidence/readme/01-practice-tutor-hero.png" alt="TiBan Practice and learning assistant workspace" width="100%">
</p>

## What is TiBan?

TiBan connects question banks, learning materials, contextual tutoring, and
long-term learning state in one adaptive workspace. Learners choose a domain,
enter Practice or Exam, answer questions, inspect explanations, ask follow-up
questions, and return later with their progress intact.

The repository includes a Medical Demo Domain Pack for a complete professional
learning journey. The shared learning engine, knowledge layer, and Agent
capabilities are designed to extend to other subjects through additional
domain packs.

## One connected learning path

~~~text
Choose a question bank
        ↓
Practice / Exam
        ↓
Answer, review, and ask the learning assistant
        ↓
Mastery · FSRS review · Learning Memory
        ↓
A more focused next session
~~~

Every submission updates the server-side learning workflow: attempts, mastery,
FSRS scheduling, and learning memory move together. Review queues and bank
progress reflect the learner's actual history.

## Core experience

| Area | Learner experience | Technology |
| --- | --- | --- |
| Question banks | Browse domains, inspect bank scale, and filter by question state | Domain Packs, persistent progress, state projections |
| Practice + assistant | Answer, see feedback, and ask about the current question | Context-aware Tutor, SSE streaming, controlled tool routing |
| Mentor Agent | Review activity across banks and plan the next learning step | Persistent sessions, Learning Memory, Review Queue |
| Knowledge library | Manage text and image sources with visible captions and provenance | Layout-aware parsing, BGE-M3 + CLIP retrieval, Qdrant multimodal index, evidence graph |
| Question import | Validate banks or create reviewable drafts from teaching material | CSV / JSONL / Markdown, quality gates, review and publish |
| Evaluation Lab | Compare runtime models and retrieval profiles under fixed conditions | EvalSuite, durable jobs, versioned RetrievalProfile |

## Product interface

These views are from the current TiBan product and cover the main journey from
selecting a bank to tutoring, review, Agent collaboration, and evaluation.

### Practice + learning assistant

Questions, answer choices, feedback, explanations, and contextual tutoring
share one focused workspace. The assistant understands the current learning
context and can bring in cited material when it is useful.

Image questions use the same focused layout: the image is shown with its
original aspect ratio, while the Tutor receives it as a real visual input.
The bundled endoscopy practice bank contains 30 image questions, and question
media is kept separate from the knowledge-library image index.

<p align="center">
  <img src="./docs/v3/evidence/readme/21-multimodal-practice.png" alt="Image question and Tutor workspace" width="100%">
</p>

<p align="center"><em>Image-question practice: the image, choices, and Tutor remain in one familiar learning workspace.</em></p>

### Question banks and status browsing

<table>
  <tr>
    <td width="50%"><strong>Question banks</strong><br><img src="./docs/v3/evidence/readme/02-banks-current.png" alt="Question bank selection" width="100%"></td>
    <td width="50%"><strong>Bank details and status</strong><br><img src="./docs/v3/evidence/readme/03-bank-detail-current.png" alt="Question bank details and status browsing" width="100%"></td>
  </tr>
</table>

### Mentor Agent

The Mentor Agent brings together recent attempts, mistakes, review queues, bank
progress, learning memory, and enabled sources across question banks.

<p align="center">
  <img src="./docs/v3/evidence/readme/04-mentor-current.png" alt="Mentor Agent workspace" width="100%">
</p>

### Knowledge library

Learning materials become managed, versioned context for the Tutor and Mentor
Agent. Each source has its own parsing, indexing, and enablement state. The
bundled endoscopy guide demonstrates Figure-caption alignment, image previews,
page provenance, and linked text evidence.

<p align="center">
  <img src="./docs/v3/evidence/readme/20-knowledge-multimodal.png" alt="Multimodal knowledge library with images, captions, and parsed evidence" width="100%">
</p>

<p align="center"><em>Multimodal evidence chain: source images, Figure captions, licensing metadata, and parsed text are visible together.</em></p>

<p align="center">
  <img src="./docs/v3/evidence/readme/22-knowledge-textbook-detail.png" alt="Multimodal knowledge-library detail for the Medical Imaging textbook" width="100%">
</p>

<p align="center"><em>V3.5.2 live detail view: a 406-page teaching book is represented by 2,298 chunks and 252 retained searchable images, with image previews, parsed text, page provenance, and cross-modal linkage in one source workspace.</em></p>

### Evaluation Lab

The Evaluation Lab freezes the question set, prompt, and runtime conditions so
model and RAG comparisons remain easy to understand and reproduce.

<p align="center">
  <img src="./docs/v3/evidence/readme/06-evaluation-current.png" alt="Evaluation Lab" width="100%">
</p>

### Question import and settings

<table>
  <tr>
    <td width="50%"><strong>Question import</strong><br><img src="./docs/v3/evidence/readme/07-factory-current.png" alt="Question import workspace" width="100%"></td>
    <td width="50%"><strong>Settings</strong><br><img src="./docs/v3/evidence/readme/08-settings-current.png" alt="Model and embedding settings" width="100%"></td>
  </tr>
</table>

### Mistakes and review

FSRS scheduling and actual attempts form a durable Review Queue. Learners can
move between due items, mistakes, and marked questions while keeping the full
question detail and explanation in view.

<p align="center">
  <img src="./docs/v3/evidence/readme/09-review-current.png" alt="Mistakes and review workspace" width="100%">
</p>

## Technical highlights

### Multimodal RAG and vision-enabled Agents

**Keyword map:** `Multimodal RAG` · `Vision Agent` · `Layout-aware Ingestion` ·
`Figure-caption Grounding` · `CLIP` · `BGE-M3` · `Qdrant` · `Evidence Graph /
GraphRAG` · `Provenance` · `OpenAI-compatible Vision API`

```text
Multimodal sources / image questions
      ↓ layout-aware parsing and governed asset storage
Figure caption + page + section + linked text
      ├─ BGE-M3 hybrid text retrieval
      ├─ CLIP shared text ↔ image retrieval
      └─ Evidence Graph one-hop cross-modal expansion
      ↓ evidence pack (image / caption / source / page)
Tutor / Mentor Vision Agent
```

- **Layout-aware PDF ingestion** — PyMuPDF reads text blocks, image positions,
  and Figure captions, then binds evidence-bearing images to captions, pages,
  sections, and nearby text. Logos, headers, and uncaptioned decoration are
  excluded from the image index.
- **Three-channel retrieval** — BGE-M3 handles hybrid text retrieval, CLIP
  provides a shared text-image space in Qdrant, and a governed concept graph
  performs one-hop text ↔ Figure evidence expansion.
- **Evidence-grounded GraphRAG** — every result retains the image, caption,
  page, source, and linked text chunk, so evidence can be traced from text to
  image and back.
- **Vision-capability routing** — Tutor and Mentor share one Provider path;
  image requests compose OpenAI-compatible text and `image_url` content blocks,
  while text-only requests keep the existing default route.
- **Governed media assets** — MIME, file-header, size, pixel, and path checks
  protect controlled runtime assets. Databases, Qdrant payloads, logs, and jobs
  keep opaque asset IDs and provenance metadata rather than image bytes.

- **Context-aware Tutor** — every request carries the current question, mode,
  learning phase, and conversation context.
- **Governed retrieval** — the product routes ordinary knowledge directly and
  calls <code>search_knowledge</code> when supporting material is useful; result
  relevance and deduplication keep citations focused.
- **Persistent Learning Memory** — real attempts, review facts, and learning
  conversations become reusable context for the next session.
- **FSRS scheduling** — review timing evolves with the learner's actual
  performance.
- **Domain Pack architecture** — content, terminology, and safety policy live
  with the domain while the learning engine remains reusable.
- **Durable Question Factory** — parsing, generation, quality checks, revisions,
  review, and publishing are traceable and recoverable.
- **Reproducible Evaluation Lab** — EvalSuite freezes questions, prompts, and
  runtime conditions; model runs use <code>temperature=0</code> and no fallback,
  while RAG runs reuse the product <code>RagService</code>.
- **Typed end-to-end contracts** — React communicates with FastAPI through a
  generated OpenAPI client, with SSE for streaming Tutor and job state.

## Technology

~~~text
React 19 + TypeScript + Vite
        │  Generated OpenAPI client + SSE
        ▼
FastAPI + Pydantic + SQLAlchemy
        ├─ PostgreSQL: banks, attempts, reviews, sources, and jobs
        ├─ PyMuPDF: layout-aware PDF and Figure-caption parsing
        ├─ Qdrant + BGE-M3: hybrid text retrieval and semantic learning memory
        ├─ Qdrant + CLIP: shared text-image retrieval space
        ├─ Evidence Graph: governed one-hop cross-modal expansion
        ├─ Redis + Dramatiq: import, indexing, and reflection jobs
        ├─ py-fsrs: review scheduling
        └─ OpenAI-compatible vision providers: text/image routing and evaluation
~~~

## Quick start

Requirements: Python 3.12+, Node.js 22+, npm, and Docker Desktop.

~~~powershell
git clone https://github.com/Luious-LYH/TiBan.git
cd TiBan
docker compose up --build
~~~

Open http://127.0.0.1:5173/ and follow:

~~~text
/banks → bank details → Practice + assistant → submit → Review
~~~

Local regression commands:

~~~powershell
# Backend
cd backend
$env:PYTHONPATH='.'
python -m pytest -q

# Frontend
cd ../frontend
npm run api:check
npm run lint
npm test -- --run
npm run build
~~~

## Data and safety

- Large third-party datasets remain outside the public repository and are
  imported only in authorized local environments.
- API keys stay in local environment configuration or request-scoped runtime
  settings; they are not written to browser storage, databases, logs, or Git.
- Knowledge sources keep their own metadata, versions, parsed chunks, and
  retrieval status.
- Medical Demo output retains physician-review boundaries and safety notices
  for teaching and pre-review assistance.

See [THIRD_PARTY_DATA.md](./THIRD_PARTY_DATA.md) for data attribution and
licensing boundaries.

The reproducible multimodal retrieval fixture and implementation notes are in
[`docs/architecture/multimodal-evidence-rag-v35.md`](./docs/architecture/multimodal-evidence-rag-v35.md).
The release record is in [`docs/releases/V3.5.2.md`](./docs/releases/V3.5.2.md).

## Windows desktop app

The current Windows desktop package is **v3.3.1**. For the latest features and multimodal knowledge-library experience, use the [live Demo](https://tiban.liuaihub.com/).

[Download the Windows portable app (v3.3.1)](https://github.com/Luious-LYH/TiBan/releases/download/v3.3.1/%E9%A2%98%E4%BC%B4%20TiBan-3.3.1-x64-Portable.exe)

## Support TiBan

TiBan is independently maintained. If it helps your learning, research, or
project work, you can support continued development through
[Afdian](https://afdian.com/a/tiban).
