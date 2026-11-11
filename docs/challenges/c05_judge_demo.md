# C05 judge demo

## 60-second presentation script

> **(0–10 s) The problem.** "Compassio's AI learns what a climate project looks like from donor
> labels. The challenge: someone secretly flipped 5% of those labels. Here, 666 out of 13,317
> real FCDO and EC projects."
>
> **(10–25 s) The defence.** "Before any training, every label goes through a quarantine gate.
> It asks two independent questions: does a model trained on *other* records disagree, and do
> the 15 most similar projects disagree? Both yes: quarantined. Only one: kept, but sent to
> review. Labels are never silently changed."
>
> **(25–45 s) The measured result.** "Against random flips, our deployed policy A catches 37% of
> the poison at 40% precision. It wrongly holds back under 3% of clean records, and the model
> trained afterwards has the best F1: 0.761 versus 0.737 poisoned. Against a smarter attacker
> who hides adaptation projects, policy A catches only 8%. Our hardened candidate B adds
> independent evidence, the donor's own sector code. It lifts that to 28% at 54% precision,
> reproduced on four seeds, and cuts wrongful quarantine of real climate projects from 370 to
> 79."
>
> **(45–60 s) The honesty.** "We do *not* claim to stop targeted poisoning: adaptation recall is
> still lower than before the attack. Every number you see was measured on real data, every
> result re-verifies by hash, and a flag is evidence for review, not proof."

## Commands (PowerShell, repository root)

All commands run offline from the hash-verified cached runs. None needs the raw ML v2 data or
any environment variable.

```powershell
# 1. Prove both cached experiments are intact (base run + hardening addendum)
uv run python -m compassio_ml.challenges.c05.cli verify
#    OK  c05_acbd465eef5a: 12 files match manifest.json
#    OK  addendum_80ef1619158b: 6 files match manifest.json

# 2. LIVE, deployed policy A, random attack on a fresh 3,001-record sample (~13 s)
uv run python -m compassio_ml.challenges.c05.cli live --sample 3000
#    inverted 150 labels; policy A: accepted 2884, quarantined 117, insufficient evidence 238
#    where the poisoned labels went: quarantined 42, review 44, accepted silently 64

# 3. LIVE, targeted attack: deployed policy A vs hardened candidate B
uv run python -m compassio_ml.challenges.c05.cli live --sample 3000 --attack targeted_non_energy_positive
#    policy A: poisoned -> quarantined 18, review 53, accepted silently 79 (recall 12%)
uv run python -m compassio_ml.challenges.c05.cli live --sample 3000 --attack targeted_non_energy_positive --policy hardened
#    policy B: poisoned -> quarantined 48, review 47, accepted silently 55 (recall 32%, precision 50%)

# 4. CACHED full results + scorecard + judge page
uv run python -m compassio_ml.challenges.c05.cli show
start data\ml_v2\challenges\c05\c05_acbd465eef5a\judge_report.html
```

**Say clearly:**
- Steps 2–3 are **live** runs on a subsample, with live attack seed 7, so their numbers differ
  from the full run.
- Step 4 shows **cached results** of the full 13,317-record experiments, re-verified by hash.
  They are not re-run live: each full run takes about 19 minutes.

## What the judge page shows (one page, no scripts, no internet)

1. **C05 scorecard:** one row per attack × policy.
   - Detection precision, recall, false-quarantine rate, clean positives wrongly quarantined
     and poisoned records accepted into training.
   - Model F1 and recall next to the naive (poisoned) model.
   - Policies are labelled **A. Deployed two-signal**, **B. Hardened candidate** and **C. Top 5%
     suspicion (analysis only)**.
2. **Per attack (uniform first):**
   - **Cards for policy A:** batch size, labels inverted, quarantined, poison caught, clean
     records wrongly quarantined, accepted.
   - **Model table:** clean vs naive vs protected (policy A).
   - **Policy C threshold table**, labelled ANALYSIS ONLY.
   - **Examples of quarantined labels**, with the reason and an after-the-fact oracle check
     ("was poisoned" / "was NOT poisoned").
   - **Where did every record go?** accepted / insufficient evidence / quarantined for A, B and
     C, and the same split for the poisoned records.
   - **Measured attacks that ESCAPED detection:** the most suspicious poisoned records that A and
     B still accepted or only sent to review, with the detector's evidence.
3. **Honest limits:** the no-attack false-alarm floor, "a flag is not proof", and the
   development-benchmark caveat.

## Numbers to remember

Full tables: `c05_scorecard.md`.

| | A deployed | B candidate |
| --- | --- | --- |
| Uniform: poison caught | 245 / 666 (36.8%), precision 40.5% | 164 / 666 (24.6%), precision 48.4% |
| Uniform: clean records wrongly quarantined | 2.85% | 1.38% |
| Uniform: model F1 / recall (naive 0.7365 / 0.7823) | 0.7611 / 0.7437 | 0.7552 / 0.7908 |
| Targeted: poison caught | 56 / 666 (8.4%), precision 12.2% | 187 / 666 (28.1%), precision 54.0% |
| Targeted: model PR-AUC / adaptation recall (naive 0.8305 / 0.647) | 0.8302 / 0.640 | 0.8379 / 0.624 |
| No attack: records quarantined | 374 | 195 |

## Full re-runs (optional, ~19 minutes each, need the ML v2 environment)

```powershell
$env:COMPASSIO_DATA_ROOT = "$PWD\data"; $env:COMPASSIO_V1_PROJECT_ROOT = "$PWD"
$env:COMPASSIO_V2_OUTPUT_ROOT = "$PWD\data\ml_v2"
$env:COMPASSIO_V2_EXTERNAL_INPUT_ROOT = "<ml worktree>\data\ml_v2\external_raw"
uv run python -m compassio_ml.challenges.c05.cli run        # base run (refuses to overwrite)
uv run python -m compassio_ml.challenges.c05.cli addendum   # policies A/B/C on identical inputs
```

## Data use

The judge page and the cached runs contain short title excerpts and IDs of FCDO/EC IATI
records. These sources are permitted for ML training and automated evaluation *pending review*.
Show them locally at the event only; do not publish the page or upload the run directories.
