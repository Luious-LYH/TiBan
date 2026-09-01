# QBank product UX specification

## Product promise

The learner sees a real question bank: question, options/image, answer feedback, explanation, progress and review actions. Dataset provenance remains available in backend/developer evidence, while license and evaluation controls stay in the developer/data layer rather than occupying the ordinary learner question surface.

## Session modes

| Mode | Primary job | Answer visibility | Tutor |
|---|---|---|---|
| Study / Tutor | learn while practising | immediate answer, own choice and explanation after submit | continuous right-side chat |
| Exam | simulate a block | locked until the block/session ends | disabled or limited |
| Review | revisit Incorrect / Marked / Due | answer reveal plus FSRS rating controls | available for explanation |

Session creation supports bank, mode, count, status filter (`Unused`, `Incorrect`, `Marked`, `All`), subject/topic/difficulty/type/image filters and optional question/option shuffling. The current implementation exposes the core bank/mode/count/status controls and preserves the extension points in the API contract.

## Practice workspace

Desktop uses a two-column workspace. The question area contains Navigator, question/image, options, feedback and explanation. Tutor occupies a full-height right panel with its own conversation scroll and sticky composer. On mobile the Tutor panel becomes a full-height sheet. There are no `.v2`/`.v3` duplicate pages.

The toolbar is intentionally learner-facing: `1 / N`, type, difficulty, Mark, Note and Navigator. Engineering fields such as vector scores, ToolReceipt, trace and FSRS internals are not part of the ordinary question surface.

## Feedback contract

For MCQ, the result is human-readable rather than a large numeric score:

```text
回答正确 / 回答错误
你的答案：...
正确答案：...
解析：官方解析 | AI 补充解释 | 解析提示
```

Study mode reveals the answer after submit. Exam mode explicitly states that answer and explanation are locked until the exam ends. Again/Hard/Good/Easy are Review-mode controls; the ordinary submit flow only offers a lightweight `加入复习` action.

## Data and safety

Only `business_usage=user_ready` is learner-facing. Imported questions retain `source_item_id`, dataset lineage, answer source, explanation source and license gate status. `EndoBench` remains `benchmark_only`; legacy VQA samples without suitability lineage remain `generation_source`. All medical teaching output keeps the platform safety notice and is not an independent diagnosis.

## Acceptance evidence

- [Current v2 QBank, feedback and review captures](../portfolio/evidence/current-v2/index.md)
