# QBank Scale Acceptance

## Isolated acceptance environment

The Stage 3 scale test runs in the dedicated PostgreSQL database
`endotutor_stage3_scale`; it does not modify the 3,678-question learner Demo
QBank. The full local CMExam source has 68,119 input rows; 68,112 contract-valid
single/multiple-choice questions were bulk imported. Seven malformed rows were
rejected because their options/answer mapping did not satisfy the typed question
contract.

## Results

- Bulk import: 68,112 questions in 20,757.02 ms; database size 140,141,071 bytes.
- Page 1 (`limit=50`): P50 199.90 ms, P95 219.15 ms.
- Page 2 (`offset=50`): P50 207.40 ms, P95 221.12 ms; no overlap with page 1.
- Subject filter: P50 83.25 ms, P95 106.80 ms.
- Server-persisted random 50-question session: P50 364.10 ms, P95 633.55 ms.

The acceptance verifies seed-reproducible random sampling, 50 unique session
members, pagination, subject filtering, one incorrect attempt, 49 unused
session items, one incorrect-session query result and persisted navigator state.

## Contract boundary

The Demo ships 3,678 curated learner-facing questions. The separate import and
session pipeline has been verified on 68,112 valid real CMExam rows. This does
not support a claim that the Demo itself ships tens of thousands of questions.
