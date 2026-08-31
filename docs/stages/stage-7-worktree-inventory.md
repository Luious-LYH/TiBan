# Stage 7 working-tree inventory

**Recorded at:** Stage 7 / v2.0 start, from `47d8bab` on
`refactor/v3-agent-learning-platform`.

## Release lineage

```text
23a643a  Stage 6 implementation
8014374  v1.2.0 release commit
           └── annotated tag v1.2.0 (preserved)
47d8bab  post-release documentation sync / Stage 7 baseline HEAD
```

`v1.2.0` points at `8014374`; it is not moved.  `47d8bab` is a verified
documentation-only continuation point, so Stage 7 starts from the current
branch head without retagging a historical release.

## Existing working-tree material

| Class | Paths / pattern | Decision | Reason |
| --- | --- | --- | --- |
| B — retain locally, do not commit | `artifacts/eval/latest.{json,md}` | Preserve | Local latest-evaluation output; it is not a reproducible release input. |
| B — retain locally, do not commit | modified `docs/portfolio/evidence/stage-1/**` and `stage-2/**` screenshots | Preserve | Historical browser captures are user-owned evidence, not a Stage 7 code change. |
| B — retain locally, do not commit | `backend/scripts/stage6_rag_probe.py` | Preserve | Useful one-off Stage 6 diagnostic; not part of the product runtime or a required Stage 7 test harness. |
| C — generated local output | `backend/stage4-*.log`, `frontend/*.exit`, `frontend/npm-audit*.json`, `frontend/docs/**` | Ignore prospectively | Test/build/audit output that can be regenerated locally.  No deletion is performed. |
| D — user/archive material | untracked `docs/portfolio/23_*` through `27_*` | Preserve, do not commit as Stage 7 code | Historical audit and portfolio documents supplied during prior work. |

There are no known Class A files: the current tracked Stage 6 implementation
was clean at release, and no untracked file is required for the v2.0 runtime.
There are no Class E targets.  In particular, this checkpoint does **not** run
`git clean`, reset, stash, remove screenshots, or delete raw local datasets.

## Stage 6 evidence wording calibration

Stage 6 evidence supports the following exact claims:

- Docker exercised real PostgreSQL, Redis, Dramatiq, Qdrant and FastEmbed
  infrastructure.
- The Factory Docker acceptance used the deterministic Factory model adapter;
  it is not evidence of a real external-LLM Factory generation run.
- A user-owned OpenAI-compatible provider was smoke-tested separately for
  Tutor streaming on the host.  Its endpoint and credential are intentionally
  absent from tracked configuration, Docker defaults, logs and artifacts.
- `PracticeWorkflowPort` is an intentional anti-corruption seam around the
  retained transactional Stage 5 workflow.  It has characterization and
  adapter tests; Stage 7 will not move code merely to make the abstraction
  look more formal.

The one skipped backend test is
`test_kvasir_curated_bank_has_lineage_and_legacy_vqa_is_quarantined`.  It skips
only when the local 3,678-question acceptance database is absent.  The
repository deliberately does not redistribute those local third-party samples;
hosted CI still executes the source-policy and EndoBench-exclusion tests.  The
skip remains appropriate in hosted CI and the Stage 7 test suite must continue
to cover the policy boundary with legal checked-in fixtures.

## Stage 7 accepted scope brief

**Product promise:** TiBan is an agent-native adaptive QBank platform whose
practice, Tutor, learning state and evaluation core can serve independently
configured learning domains.

**Primary actor:** a learner who switches between a governed medical/endoscopy
pack and a general-science pack without a separate product flow.

**Success moment:** a learner can create Study, Exam or Review sessions in
either domain, receive the correctly scoped Tutor and knowledge sources, and
have attempts, memory, mastery and FSRS remain isolated by domain.

**Keep:** FastAPI/OpenAPI, PostgreSQL, Qdrant, Redis + Dramatiq, the bounded
Tutor runtime, the Stage 5 adaptive sequence and the existing evaluation
workbench.

**Implement:** a minimal `DomainManifest` registry, medical and general
domain packs, domain-scoped learning/retrieval/Tutor inputs, and offline
engineering evaluation for tool selection and personalization behavior.

**Defer:** Multi-Agent, VLM Tutor productization, public SaaS/multi-tenancy,
auth redesign, Kubernetes, Terraform, GraphRAG, a second vector DB/queue,
model training and universal plugin discovery.

**Validation:** regression tests, domain-isolation tests, frozen evaluation
artifacts, OpenAPI drift, frontend tests/build, Playwright medical/general
smoke, Docker clean-start and hosted GitHub Actions.
