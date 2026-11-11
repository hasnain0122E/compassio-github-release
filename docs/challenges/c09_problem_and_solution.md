# C09: adversarial feature perturbation defense

C09 asks whether a 2% presentation change can evade a climate classifier. Compassio ML v2
accepts **title and description only**, joined with `" \n "` when both are present. Its frozen
character TF-IDF (char_wb, 2–5 grams) and balanced logistic regression can respond to visual
changes that a reader would ignore. The score is text relevance to donor Rio annotations,
not a numerical green rating, climate impact, financial quality or funding approval.

The opt-in `compassio_ml.c09.guard.GuardedClassifier` wraps the verified existing classifier.
It uses NFC, whitespace normalization outside numeric spans, narrowly scoped invisible
removal, sentence-punctuation presentation normalization, and bounded mixed-script confusable
mapping. It returns both raw and guarded scores, the unchanged model threshold,
`unstable_input`, `requires_review`, normalized fields and reasons. A review flag is not a
negative prediction or a successful prevention. Callers must route flagged inputs to review.
Invisible boundaries immediately following a negation are retained for review, so sanitation
does not silently join `not` to the following word. This safety rule was added after the first
assessment run during source review; it was not selected by optimizing benchmark scores.

This is an offline research adapter and judge CLI. Existing HTTP preprocessing and serving
behavior are unchanged. In particular, the existing API already sanitizes control characters;
the artifact-level invisible-character benchmark must not be described as an API exploit.

The model, vectorizer, trained vocabulary, threshold, v1 release, financial code and database
are unchanged. Neither training nor model updates are part of this implementation. Tests of
existing training code use their existing artificial engineering fixtures only.

Implementation: `packages/compassio_ml/src/compassio_ml/c09/`; versioned settings:
`configs/c09_protocol.json`; security and correctness checks: `tests/ml/test_c09.py`.
Measured outcomes and residual failures are in [results](c09_results.md); reproduce using the
[judge instructions](c09_judge_demo.md).
