# C09 scorecard

The complete, self-contained offline scorecard is generated at
`artifacts/c09/judge/scorecard.html`. It includes original and manipulated source text,
visible Unicode escapes, exact edit receipts, verified edit percentages, raw/attacked/guarded
scores, prediction-flip indicators, query counts, aggregate slices, review burden, performance,
integrity and actual residual failures. All source text is HTML-escaped. No CDN, network,
JavaScript service or model server is needed to read it.

The HTML contains local source records and stays Git-ignored. Do not redistribute it as a
licensed dataset. FCDO IATI attribution: public sector information under OGL v3.0. EC DG INTPA
IATI: EU-owned content under CC BY 4.0; third-party rights may differ. Manipulations are
explicitly marked. Public/safe aggregate findings are in [results](c09_results.md).

Assessment summary: fixed flips **5 → 2 / 1,280 pairs**, raw-selected search flips
**8 → 2 / 512 pairs**, fresh guard-targeted search **5 guarded flips / 512 pairs**.
Clean disagreement: **0/256**. This is partial mitigation with observed failures.
The [sanitized aggregate report](c09_benchmark_aggregates.json) contains complete per-attack
metrics, distributions, slices, query totals, both performance measurements and all nine
successful reproducibility comparisons, without source text or record identifiers.

Use [the offline demo](c09_judge_demo.md) to regenerate rather than substituting invented
examples. The CLI automatically prints one measured prevention and one measured failure,
when present. The HTML lists all assessment cases, sorted with residual failures first.
