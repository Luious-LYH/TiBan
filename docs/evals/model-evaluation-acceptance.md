# Model Evaluation Acceptance v1

## Scope

This is a bounded portfolio acceptance for the candidate-model workbench. It
uses two frozen evaluation packs and the same OpenAI-compatible provider path
used by the application. The private API base and credential are intentionally
not recorded here.

| Pack | Source | Version | Size | Modality | Tutor indexed |
|---|---|---|---:|---|---|
| CMExam text | CMExam | `cmexam-text-eval-v1` | 100 | text single-choice | false |
| EndoBench VLM | EndoBench | `endobench-vlm-eval-v1` | 100 | image single-choice | false |

EndoBench is Evaluation-only. Its cases, images and gold answers are not
eligible for Tutor RAG, Question Factory or the learner-facing QBank.

## Real acceptance runs

The following runs were executed against the locally configured provider on
2026-08-28 and 2026-08-29. `allow_fallback=false` was enforced for every
request.

| Run | Pack | Model | Samples | Status | Accuracy | Valid parse | Failure rate | P50 / P95 |
|---|---|---|---:|---|---:|---:|---:|---:|
| `evalrun_62e886fd456c44` | CMExam text | `gpt-5.6-sol` | 5 | completed | 1.0000 | 1.0000 | 0.0000 | 2879 / 41258 ms |
| `evalrun_fcb3a57b3e934e` | EndoBench VLM | `gpt-5.6-sol` | 1 | completed | 0.0000 | 1.0000 | 0.0000 | 5009 / 5009 ms |
| `evalrun_8ca3f74df1064f` | CMExam text | `gpt-5.6-sol` | 5 | completed | 1.0000 | 1.0000 | 0.0000 | 2917 / 3130 ms |

The VLM run attached an image through the provider path and returned a
schema-valid but incorrect answer. This is retained as a real error, not
converted into a text-only success.

Artifacts:

- [`evalrun_62e886fd456c44.json`](../../artifacts/eval/model-runs/evalrun_62e886fd456c44.json)
- [`evalrun_fcb3a57b3e934e.json`](../../artifacts/eval/model-runs/evalrun_fcb3a57b3e934e.json)
- [`evalrun_8ca3f74df1064f.json`](../../artifacts/eval/model-runs/evalrun_8ca3f74df1064f.json)

The artifacts keep only answer-shaped candidate output, parsed answer,
latency, error category and aggregate usage. They do not keep raw model
reasoning, API keys or private endpoint URLs. Gold answers are stored in the
evaluation domain for reproducibility and are withheld by the normal API
projection until an explicit `reveal_gold=true` request.

## Reproduction

Configure a local provider in an untracked `.env`, then run from `backend`:

```bash
set PYTHONPATH=.
python scripts/run_model_evaluation_acceptance.py --text-samples 5 --vlm-samples 1
```

The script never prints the base URL or key. A missing provider returns
`EXTERNAL_PROVIDER_ACCEPTANCE_PENDING`; a provider failure remains a failed
run and does not use the configured Tutor fallback.

## API contract

- `GET /api/v3/evaluation/datasets` lists frozen packs and hashes.
- `POST /api/v3/evaluation/connection-test` performs a request-scoped probe.
- `POST /api/v3/evaluation/runs` executes bounded text or image evaluation.
- `GET /api/v3/evaluation/runs/{id}` with default `reveal_gold=false` hides
  per-case gold/correctness; the explicit reveal action opens the comparison
  view.

This artifact is an engineering/model-integration acceptance, not a clinical
effectiveness study.
