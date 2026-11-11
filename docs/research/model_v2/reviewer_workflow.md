# Human review workflow (label policy `rio_label_policy_v2.1`)

For the people who label, adjudicate and audit. Scoring rules are in
`labeling_guidelines.md`; read them first. **Nothing in this workflow is automated:** no code
fills a reviewer, adjudicator or final-label value, and agreement is computed only from what
people return.

Paths below are relative to `data/ml_v2/labeling/<build_id>/` (git-ignored; the build ID is
printed by `uv run compassio-v2 worksheets`). Commands run from the worktree root with
`COMPASSIO_DATA_ROOT` set.

## 0. Who does what

| Worksheet | People | Role names |
| --- | --- | --- |
| `external_test_pilot_v1/reviewer_A.csv` | 1 person | `reviewer_a` |
| `external_test_pilot_v1/reviewer_B.csv` | a **different** person | `reviewer_b` |
| `external_test_pilot_v1/adjudication/…` | a **third** person | `adjudicator` |
| `training_label_audit_v1/reviewer.csv` | 1 person (may be A or B) | `auditor` |

Reviewers must not see each other's sheets, model outputs, AI suggestions or source
classifications. Anyone who also develops v2 models must declare it in
`conflicts_of_interest`.

## 1. Register reviewers (required before any review is accepted)

1. Copy `reviewers.template.yaml` to `reviewers.yaml` in the same folder.
2. Replace the placeholder with one entry per **genuine person**. A pseudonym (e.g. `rv-07`) is
   fine; it must map to one real human. `is_human: true`, a role list and a one-sentence
   attestation are mandatory. IDs beginning with `example` are refused.
3. Keep the mapping from pseudonym to person outside the repository.

```yaml
reviewers:
  - reviewer_id: rv-07
    is_human: true
    roles: [reviewer_a, auditor]
    attestation: "I label independently, from the text only, without AI assistance."
    conflicts_of_interest: "none"
```

## 2. Open and edit a worksheet

- **Never edit the issued file.** Copy it into `completed/` with the **same file name**
  (e.g. `completed/reviewer_A.csv`) and edit the copy.
- Excel: *Data → From Text/CSV*, file origin **UTF-8**, delimiter comma; save as **CSV UTF-8**.
  LibreOffice Calc: character set **UTF-8**, "quoted field as text" on; save as CSV (UTF-8).
- Do not change, add, delete or reorder columns; do not edit `item_id`, `title` or
  `description` (the validator compares the text with what was issued).

## 3. Fill one row per item

| Column | What to enter |
| --- | --- |
| `reviewer_id` | your registered ID (same on every row) |
| `rio_mitigation`, `rio_adaptation` | 0, 1 or 2 (definitions in `labeling_guidelines.md`) |
| `rio_overall` | the larger of the two; any other value is rejected |
| `confidence` | `low`, `medium` or `high` |
| `insufficient_information` | `true` only if the text cannot support a score (see §4); otherwise leave blank or `false` |
| `evidence_quote` | the shortest decisive phrase **copied verbatim** from title or description (case and spacing may differ); required for every scored row |
| `rationale` | at least one sentence explaining the score |
| `flag_needs_discussion` | `true` for borderline items you want the adjudicator to look at |
| `reviewed_at` | ISO date, e.g. `2026-11-20` |

## 4. Uncertain items and insufficient information

- **Uncertain but decidable:** give your best score, `confidence = low`, and set
  `flag_needs_discussion = true`. The item goes to adjudication.
- **Cannot be decided from the text** (too short, generic, only a title, wrong language):
  set `insufficient_information = true`, leave all three Rio columns **blank**, explain why in
  `rationale`. Do not guess and do not research the project elsewhere. Such items go to
  adjudication and may end as `needs_review` (excluded from headline metrics).

## 5. Submit and validate

1. Save the completed copy in `completed/`.
2. Run `uv run compassio-v2 validate-reviews`. It checks registration and role, column
   integrity, unchanged text, value rules, verbatim evidence, and that A and B are different
   people. It reports blank rows and, once both pilot sheets exist, per-objective agreement
   and Cohen's kappa. Fix any reported error in your own copy and re-run.

## 6. Adjudicate

1. When **both** pilot sheets validate with no blank rows, run
   `uv run compassio-v2 adjudication-sheet`. It writes
   `external_test_pilot_v1/adjudication/adjudication_sheet.csv` listing every item with both
   reviews; rows with `needs_adjudication = True` are disagreements, flagged items or
   insufficient-information items. Only now are source context columns (World Bank theme tags,
   sector) shown.
2. The adjudicator copies the sheet to `adjudication/completed/adjudication_sheet.csv` and, for
   every `needs_adjudication` row, fills `adjudicator_id`, `final_status` (`verified` or
   `needs_review`), `final_rio_mitigation` and `final_rio_adaptation` (verified rows only) and
   `adjudication_rationale`. Agreed rows need no action: two independent human scores that
   match become the final label.
3. The adjudicator must be registered with role `adjudicator` and must not be reviewer A or B.

## 7. Freeze

`uv run compassio-v2 freeze-labels` refuses unless both sheets are complete and valid and every
item needing adjudication is resolved. It then writes
`sealed_external_test/<build_id>/external_test_labels.parquet` and
`external_test_labels.lock.json` (SHA-256, counts, agreement statistics). These are readable
only after a v2 final-evaluation plan is frozen (`external_test_access_policy.md`). A frozen
file is never overwritten; corrections require a new label version.

## 8. Training-label audit

One `auditor` completes `training_label_audit_v1/reviewer.csv` the same way (copy to
`completed/reviewer.csv`, validate). It measures how often donor-reported markers (hidden from
the sheet) agree with a human reading. Audit results describe label noise in training data;
they are not external-test labels.

If binary kappa on the pilot is below 0.60, stop: revise the guidelines and relabel before any
model is scored (`evaluation_protocol_v2_proposal.md`).
