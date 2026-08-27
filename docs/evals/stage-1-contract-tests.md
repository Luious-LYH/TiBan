# Stage 1 Contract Test Evidence

## Command

```powershell
cd code/backend
$env:PYTHONPATH = "."
pytest -q
```

## Result

```text
23 passed, 20 warnings
```

The warnings are upstream/deprecation warnings (`FastAPI on_event`, `datetime.utcnow`, and the installed Starlette/httpx compatibility layer); no test failure is suppressed.

## Covered boundaries

- Public list and detail payloads are recursively checked for `answer`, `correct_option_id`, `correct_option_ids`, `hidden_rubric`, `reference_answer`, `benchmark_target`, and `expected_facts`.
- `QuestionPublic` validates through a Pydantic v2 discriminated union.
- The OpenAPI document exposes the four public variants and their `question_type` constants.
- Two real seeded banks produce disjoint question ID sets.
- Single choice, multiple choice (`string[]`), true/false (`bool`), and short answer (`string`) all submit without 422.
- Four successful submissions create four immutable Attempt rows and four ReviewCard rows for a fresh learner.
- `/api/v3/overview` returns serializable public bank projections rather than SQLAlchemy ORM instances.

## Test file

[test_stage1_contracts.py](../../backend/tests/test_stage1_contracts.py)
