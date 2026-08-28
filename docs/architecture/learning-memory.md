# Learning memory and FSRS

The learning model is structured and server-owned:

```text
PracticeSession → immutable Attempt → LearnerMastery projection → ReviewCard / py-fsrs
                                                    → Mentor StudyPlan
```

On every successful submit, the deterministic application workflow grades first, writes an immutable `Attempt`, rebuilds affected `LearnerMastery`, then calls `fsrs==6.3.2` with deterministic fuzzing disabled. `ReviewCard` stores `fsrs_card`, rating logs, difficulty, stability, retrievability, due and state. The Tutor has no write tool for any of these entities.

Mentor reads due cards, mastery, recent errors and study goal to emit a typed StudyPlan. It derives different plans from different learner histories; it does not use alternate prompts to simulate personalization. The fixed Again/Hard/Good/Easy comparison is recorded in [`artifacts/learning/fsrs-again-hard-good-easy-v1.json`](../../artifacts/learning/fsrs-again-hard-good-easy-v1.json).
