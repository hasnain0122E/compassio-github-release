# C09 threat model

The applicant controls presentation of title and description at inference time, and may see
the relevance score. They cannot change the model, its threshold, source labels, eligibility,
finance values, source identity or evaluation membership. The benchmark targets increased or
decreased relevance, including crossing the fixed binary decision boundary.

The allowed budget is **at most floor(N / 50) Unicode character edits**, where N counts eligible
positions in the original two text fields. The synthetic model separator is excluded. Each
insertion, deletion or substitution costs one; a transposition would cost two. Original
coordinates, before/after characters, operation counts and independently verified bounded
Levenshtein distances are recorded. The reported edit percentage is `100 * distance / N`;
zero eligible positions permit zero edits. This is stricter than 2% of all text characters.

Eligible letters belong to a fixed allowlist of administrative words such as project, support,
programme, technical and implementation. Safe whitespace between letters and comma/semicolon
separators before alphabetic text are eligible. Everything else is protected, including
numeric characters, currency/value punctuation, negations and substantive climate words.
The complete allowlist and exact boundary rules are in `c09/attacks.py`. Attacks do not add
climate claims or rewrite numbers. Duplicated interior letters are restricted to these neutral
words. This is a conservative operational meaning-preservation rule, not human verification
of semantic equivalence. Ambiguous natural-language cases still need a reviewer.

Five fixed attacks cover Cyrillic lookalikes, zero-width spaces, nonbreaking whitespace,
fullwidth comma/semicolon presentation forms, and duplicated-letter typos. A bounded score
search selects the minimum and maximum from 12 deterministic candidate requests. The two
directions share a pool; it is not 24 distinct queries. A fresh candidate pool is selected
against the guarded score for adaptive assessment. All candidates start from original text;
query iterations cannot compound their edit budgets.

Numeric reporting metadata does not enter the model. An artificial +/-2% Decimal metadata
control is measured separately and explicitly labeled as engineering evidence. It is not
observed project finance, and does not support a numeric-feature evasion claim.

Out of scope: changing climate meaning, deleting negations, financial manipulation, poisoning,
model extraction, unbounded search, semantic paraphrases, and sealed evaluation data. This
limited benchmark cannot certify robustness to those threats or all Unicode confusables.
