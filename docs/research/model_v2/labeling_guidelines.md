# Reviewer guidelines — Rio-marker labelling (policy `rio_label_policy_v2.0`)

For human reviewers of the v2 worksheets. **You label what the text states, not what you
believe the project achieved.** Climate relevance is not proof of environmental benefit.

Reviewers must read the official OECD DAC *Rio Markers for Climate* handbook definitions
before starting. The summary below paraphrases them and does not replace them.

## 1. What to score

For each item, score two objectives independently on the 0/1/2 scale, from the title and
description in the worksheet only:

| Score | Meaning |
| --- | --- |
| **2 — principal** | The objective is explicitly stated as fundamental to the design of the activity; the activity would not have been undertaken without it. |
| **1 — significant** | The objective is explicitly stated but is not the fundamental driver. |
| **0 — not targeted** | The objective is not explicitly targeted in the text. |

- **Mitigation**: the activity contributes to stabilising greenhouse-gas concentrations by
  reducing or limiting emissions or enhancing sequestration.
- **Adaptation**: the activity intends to reduce the vulnerability of human or natural systems
  to current and expected climate-change impacts, including climate variability, by
  maintaining or increasing resilience. Score adaptation only when the text (a) sets out a
  climate-vulnerability context, (b) states an intent to address it, and (c) links the
  activities to that context.
- `rio_overall` = max(mitigation, adaptation). The worksheet validator rejects any other value.

## 2. Rules

1. **Evidence:** copy the shortest decisive phrase into `evidence_quote`. Write a rationale of
   at least one sentence.
2. **Implicit climate purpose:** irrigation, flood protection, drought-resistant crops, urban
   transit and similar activities are **not** automatically climate-relevant. Score them only
   if the text states a climate objective or a climate-vulnerability context. Note borderline
   cases with `flag_needs_discussion = true`.
3. **Retrospective or outcome text:** do not reward reported achievements. Score the stated
   objectives.
4. **Fossil fuels:** gas/LNG and efficiency at fossil plants follow the project's documented
   gas/LNG policy (`docs/data/conflicting_label_review.md`). If unsure, flag the item.
5. **Insufficient text:** if the description is too short or generic to decide, give your best
   score with `confidence = low` and flag the item. Do not research the project elsewhere.
6. **Independence:** do not look at the other reviewer's sheet, source classifications (GCF
   theme, donor markers, World Bank themes), model outputs or AI suggestions. Reviewer sheets
   intentionally omit them.
7. **Publisher identity is not evidence.** A GCF or climate-fund publisher does not by itself
   justify a score.
8. Use a stable `reviewer_id` (initials or pseudonym). Fill `reviewed_at` (ISO date).

## 3. Workflow

1. Reviewer A fills `reviewer_A.csv`; reviewer B fills `reviewer_B.csv`; different people.
2. Save completed files to `completed/` next to the worksheet, keeping the file names.
3. Run `uv run compassio-v2 validate-reviews`. It checks values and computes per-objective
   agreement and Cohen's kappa, and lists disagreements.
4. A third person adjudicates disagreements, **then** may view the source classifications.
   Adjudication records `adjudicated_by` and the final values. Only adjudicated items count as
   verified labels.
5. Claude Code and other AI tools may help triage or draft rationale text **only** as
   clearly marked suggestions outside the reviewer columns; they never fill reviewer or final
   label fields.

Ambiguous items that remain unresolved after adjudication get `final_label_status =
needs_review` and are excluded from headline metrics; they are never relabelled to improve
scores.
