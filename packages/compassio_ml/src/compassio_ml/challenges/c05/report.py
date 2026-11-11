"""Self-contained judge report (HTML, no scripts, no external assets) for a verified C05 run.

The report is generated from a run directory whose manifest hashes verify. It is written next
to the run (git-ignored, local only) and states plainly that it shows CACHED results of a
previously executed experiment. Record text is limited to short title excerpts.
"""

import html
import json
from pathlib import Path
from typing import Any

STYLE = """
:root{--bg:#f7f8f6;--fg:#1d2420;--muted:#5d675f;--card:#fff;--line:#d9dfd9;--accent:#1f6f4a;
--warn:#9a5b00;--bad:#a12a2a}
@media (prefers-color-scheme:dark){:root{--bg:#131714;--fg:#e6ebe7;--muted:#9aa59c;--card:#1b211d;
--line:#2c352f;--accent:#5fc28f;--warn:#e0a54a;--bad:#ef7b7b}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px}
.muted{color:var(--muted)}.badge{display:inline-block;padding:2px 8px;border-radius:10px;
border:1px solid var(--line);font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.big{font-size:24px;font-weight:600}
table{width:100%;border-collapse:collapse;background:var(--card);font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}.num{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:var(--accent)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.scroll{overflow-x:auto}
"""


def _e(value: Any) -> str:
    return html.escape(str(value))


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def _models_table(summary: dict[str, Any], mode: str) -> str:
    rows = [("Clean reference (no attack)", summary["models"]["clean_reference"])]
    attack = summary["attacks"][mode]["models"]
    rows.append(("Naive: trained on poisoned batch", attack["naive_poisoned"]))
    rows.append(("Protected: trained after quarantine", attack["protected_after_quarantine"]))
    if "strict_variant_excluding_review" in attack:
        rows.append(
            ("Strict variant (also drops review)", attack["strict_variant_excluding_review"])
        )
    body = "".join(
        f"<tr><td>{_e(name)}</td><td class=num>{m['training_records']}</td>"
        f"<td class=num>{m['benchmark']['average_precision']:.4f}</td>"
        f"<td class=num>{m['benchmark']['f1']:.4f}</td>"
        f"<td class=num>{m['benchmark']['precision']:.4f}</td>"
        f"<td class=num>{m['benchmark']['recall']:.4f}</td>"
        f"<td class=num>{_pct(m['benchmark']['non_energy_recall']['recall'])}</td>"
        f"<td class=num>{_pct(m['benchmark']['adaptation_only_recall']['recall'])}</td>"
        f"<td class=num>{m['fit_seconds']}</td></tr>"
        for name, m in rows
    )
    return (
        "<div class=scroll><table><tr><th>Training run</th><th class=num>Records</th>"
        "<th class=num>PR-AUC (AP)</th><th class=num>F1</th><th class=num>Precision</th>"
        "<th class=num>Recall</th><th class=num>Non-energy recall</th>"
        "<th class=num>Adaptation-only recall</th><th class=num>Fit s</th></tr>"
        f"{body}</table></div>"
    )


def _examples(run_dir: Path, mode: str, titles: dict[str, str], limit: int = 12) -> str:
    report = json.loads((run_dir / "gate" / f"{mode}_report.json").read_text("utf-8"))
    oracle = json.loads((run_dir / "private_oracle" / f"oracle_{mode}.json").read_text("utf-8"))
    flipped = set(oracle["flipped_ids"])
    flagged = [r for r in report["flagged_records"] if r["status"] == "quarantined"]
    flagged.sort(key=lambda r: (-(r["suspicion"] or 0), r["record_id"]))
    rows = []
    for r in flagged[:limit]:
        title = titles.get(r["record_id"], "")
        title = title if len(title) <= 90 else title[:87] + "..."
        truth = (
            "<span class=ok>was poisoned</span>"
            if r["record_id"] in flipped
            else "<span class=warn>was NOT poisoned (natural disagreement)</span>"
        )
        rows.append(
            f"<tr><td>{_e(r['record_id'])}<br><span class=muted>{_e(r['source_id'])}</span></td>"
            f"<td>{_e(title)}</td><td class=num>{r['supplied_label']}</td>"
            f"<td class=num>{r['suspicion']:.2f}</td><td>{_e(r['reason'])}</td>"
            f"<td>{truth}</td></tr>"
        )
    return (
        "<div class=scroll><table><tr><th>Record</th><th>Title (excerpt)</th>"
        "<th class=num>Supplied label</th><th class=num>Suspicion</th><th>Why it was flagged</th>"
        "<th>Oracle check (after the decision)</th></tr>" + "".join(rows) + "</table></div>"
    )


POLICY_ORDER = ("two_signal", "hardened", "top_share")
POLICY_SHORT = {
    "two_signal": "A. Deployed two-signal",
    "hardened": "B. Hardened candidate",
    "top_share": "C. Top 5% suspicion (analysis only)",
}


def scorecard_rows(summary: dict[str, Any], addendum: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per (attack, policy) with detection and downstream-model numbers."""
    rows = []
    for mode, _ in _ordered(summary["attacks"]):
        base_models = summary["attacks"][mode]["models"]
        for policy in POLICY_ORDER:
            det = addendum["final_seed"]["attacks"][mode][policy]["detection"]
            if policy == "two_signal":
                model = base_models["protected_after_quarantine"]["benchmark"]
            else:
                model = addendum["models"][f"{mode}|{policy}"]["benchmark"]
            rows.append(
                {
                    "attack": mode,
                    "policy": policy,
                    "precision": det["detection_precision"],
                    "recall": det["detection_recall"],
                    "false_quarantine_rate": det["false_quarantine_rate"],
                    "clean_positive_quarantined": det["clean_climate_positive_quarantined"],
                    "clean_adaptation_quarantined": det[
                        "clean_adaptation_only_positive_quarantined"
                    ],
                    "poisoned_accepted": det["poisoned_accepted_into_training"],
                    "model_f1": model["f1"],
                    "model_recall": model["recall"],
                    "model_adaptation_recall": model["adaptation_only_recall"]["recall"],
                    "naive_f1": base_models["naive_poisoned"]["benchmark"]["f1"],
                    "naive_recall": base_models["naive_poisoned"]["benchmark"]["recall"],
                }
            )
    return rows


def scorecard_html(summary: dict[str, Any], addendum: dict[str, Any]) -> str:
    clean = summary["models"]["clean_reference"]["benchmark"]
    body = "".join(
        f"<tr><td>{_e(r['attack'])}</td><td>{_e(POLICY_SHORT[r['policy']])}</td>"
        f"<td class=num>{_pct(r['precision'])}</td><td class=num>{_pct(r['recall'])}</td>"
        f"<td class=num>{_pct(r['false_quarantine_rate'])}</td>"
        f"<td class=num>{r['clean_positive_quarantined']}</td>"
        f"<td class=num>{r['poisoned_accepted']}</td>"
        f"<td class=num>{r['model_f1']:.4f} <span class=muted>(naive "
        f"{r['naive_f1']:.4f})</span></td>"
        f"<td class=num>{r['model_recall']:.4f} <span class=muted>(naive "
        f"{r['naive_recall']:.4f})</span></td></tr>"
        for r in scorecard_rows(summary, addendum)
    )
    return (
        "<h2>C05 scorecard</h2><p class=muted>Final seed 20261112, 666 of 13,317 labels "
        "inverted. Detection metrics use the oracle only AFTER the decision. Model columns: "
        "disposable model trained on the accepted records; clean reference F1 "
        f"{clean['f1']:.4f}, recall {clean['recall']:.4f}. Policy A is deployed; B is a "
        "hardened candidate; C is analysis only.</p><div class=scroll><table><tr>"
        "<th>Attack</th><th>Policy</th><th class=num>Detection precision</th>"
        "<th class=num>Detection recall</th><th class=num>False-quarantine rate</th>"
        "<th class=num>Clean positives quarantined</th>"
        "<th class=num>Poisoned accepted into training</th><th class=num>Model F1</th>"
        f"<th class=num>Model recall</th></tr>{body}</table></div>"
    )


def _targeted_limit_html(summary: dict[str, Any], addendum: dict[str, Any]) -> str:
    mode = "targeted_non_energy_positive"
    runs = addendum["final_seed"]["attacks"][mode]
    a, b = runs["two_signal"]["detection"], runs["hardened"]["detection"]
    naive = summary["attacks"][mode]["models"]["naive_poisoned"]["benchmark"]
    hard = addendum["models"][f"{mode}|hardened"]["benchmark"]
    return (
        "<li><b>Targeted attack:</b> deployed policy A catches "
        f"{_pct(a['detection_recall'])} of the flips; hardened candidate B catches "
        f"{_pct(b['detection_recall'])} at {_pct(b['detection_precision'])} precision, but "
        f"adaptation-only recall is not restored ({_pct(hard['adaptation_only_recall']['recall'])}"
        f" after B vs {_pct(naive['adaptation_only_recall']['recall'])} naive). Compassio does "
        "not claim protection against targeted label poisoning.</li>"
    )


def _outcomes_html(addendum: dict[str, Any], mode: str) -> str:
    runs = addendum["final_seed"]["attacks"][mode]
    rows = "".join(
        f"<tr><td>{_e(POLICY_SHORT[p])}</td><td class=num>{runs[p]['accepted']:,}</td>"
        f"<td class=num>{runs[p]['insufficient_evidence']:,}</td>"
        f"<td class=num>{runs[p]['quarantined']:,}</td>"
        f"<td class=num>{runs[p]['poisoned_by_status']['accepted']}</td>"
        f"<td class=num>{runs[p]['poisoned_by_status']['insufficient_evidence']}</td>"
        f"<td class=num>{runs[p]['poisoned_by_status']['quarantined']}</td></tr>"
        for p in POLICY_ORDER
    )
    escaped = "".join(
        f"<tr><td>{_e(POLICY_SHORT[p])}</td><td>{_e(x['record_id'])}<br>"
        f"<span class=muted>{_e(x['source_id'])}</span></td><td>{_e(x['title_excerpt'])}</td>"
        f"<td class=num>{x['supplied_label']}</td><td>{_e(x['status'])}</td>"
        f"<td>{_e(x['reason'])}</td></tr>"
        for p in ("two_signal", "hardened")
        for x in runs[p]["escaped_examples"][:4]
    )
    return (
        "<h3>Where did every record go? (accepted / insufficient evidence / quarantined)</h3>"
        "<div class=scroll><table><tr><th>Policy</th><th class=num>Accepted</th>"
        "<th class=num>Insufficient evidence (kept, review)</th><th class=num>Quarantined</th>"
        "<th class=num>Poisoned: accepted</th><th class=num>Poisoned: review</th>"
        f"<th class=num>Poisoned: quarantined</th></tr>{rows}</table></div>"
        "<h3>Measured attacks that ESCAPED detection (most suspicious first)</h3>"
        "<div class=scroll><table><tr><th>Policy</th><th>Record</th><th>Title (excerpt)</th>"
        "<th class=num>Poisoned label</th><th>Decision</th><th>Detector evidence</th></tr>"
        f"{escaped}</table></div>"
    )


def _card(label: str, value: Any, sub: str) -> str:
    return (
        f"<div class=card><div class=muted>{_e(label)}</div><div class=big>{_e(value)}</div>"
        f"<div class=muted>{_e(sub)}</div></div>"
    )


def _ordered(attacks: dict[str, Any]) -> list[tuple[str, Any]]:
    """The organizers' core scenario (uniform) first, then the targeted variant."""
    return sorted(attacks.items(), key=lambda kv: (kv[0] != "uniform", kv[0]))


def render(
    run_dir: Path,
    summary: dict[str, Any],
    manifest: dict[str, Any],
    addendum: dict[str, Any] | None = None,
) -> str:
    titles: dict[str, str] = {}
    with (run_dir / "batch_A_clean.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            titles[row["record_id"]] = row["title"]
    parts = [
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>C05 Quarantine Report</title><style>{STYLE}</style></head><body><main>",
        "<h1>Compassio Data Integrity Shield: C05 poisoned batch quarantine</h1>",
        f"<p class=muted><span class=badge>CACHED RESULTS of run {_e(summary['run_id'])}</span> "
        f"finished {_e(summary['finished_at'])}; every file hash re-verified when this page was "
        f"generated. Detector {_e(summary['versions']['detector_version'])}, config "
        f"{_e(summary['versions']['config_version'])}, "
        f"git {_e(str(manifest.get('git_head'))[:10])}."
        "</p>",
        f"<p>{_e(summary['benchmark_label'])}</p>",
    ]
    if addendum is not None:
        parts.append(scorecard_html(summary, addendum))
    batch = summary["batch"]
    nat = summary["natural_disagreement_on_unpoisoned_batch"]
    for mode, entry in _ordered(summary["attacks"]):
        a, g, d = entry["attack"], entry["gate"], entry["detection"]
        parts.append(f"<h2>Attack: {_e(mode)}</h2>")
        cards = [
            ("Incoming batch", f"{batch['records']:,}", "FCDO + EC donor-labelled records"),
            (
                "Labels inverted (attack)",
                a["flipped"],
                f"{_pct(a['flipped_share'])} of the batch, seed {a['seed']}",
            ),
            (
                "Policy A (deployed): quarantined",
                g["quarantined"],
                f"{g['insufficient_evidence']} more kept but sent to review",
            ),
            (
                "Policy A: poisoned labels caught",
                d["detected_poison_true_positives"],
                f"recall {_pct(d['detection_recall'])}, precision {_pct(d['detection_precision'])}",
            ),
            (
                "Policy A: clean records wrongly quarantined",
                d["false_positives"],
                f"false-quarantine rate {_pct(d['false_quarantine_rate'])}",
            ),
            (
                "Policy A: accepted for training",
                f"{g['accepted']:,}",
                f"{d['poisoned_accepted_into_training']} poisoned still inside",
            ),
        ]
        parts.append("<div class=grid>" + "".join(_card(*c) for c in cards) + "</div>")
        parts.append(
            "<h3>Model trained on each batch (same settings, same benchmark; "
            "protected = Policy A)</h3>"
        )
        parts.append(_models_table(summary, mode))
        sweep = "".join(
            f"<tr><td class=num>{_pct(s['quarantine_share'])}</td>"
            f"<td class=num>{s['quarantined']}</td>"
            f"<td class=num>{s['true_positives']}</td><td class=num>{_pct(s['precision'])}</td>"
            f"<td class=num>{_pct(s['recall'])}</td></tr>"
            for s in d["suspicion_rank_sweep"]
        )
        parts.append(
            "<h3>Policy C, ANALYSIS ONLY (not deployed): quarantine the top share by suspicion</h3>"
            "<table><tr><th class=num>Share</th><th class=num>Quarantined</th>"
            "<th class=num>Poison caught</th><th class=num>Precision</th><th class=num>Recall</th>"
            f"</tr>{sweep}</table>"
        )
        parts.append("<h3>Policy A: examples of quarantined labels and why</h3>")
        parts.append(_examples(run_dir, mode, titles))
        if addendum is not None:
            parts.append(_outcomes_html(addendum, mode))
    parts.append(
        "<h2>Honest limits</h2><ul>"
        f"<li>With NO attack, the same detector still quarantines {nat['quarantined']} records "
        f"({_pct(nat['share_quarantined'])}): donor Rio markers disagree with similar records. "
        "A flag is evidence for review, not proof of corruption.</li>"
        "<li>Labels are never corrected automatically; quarantined records keep their supplied "
        "label for investigation.</li>"
        "<li>The benchmark is the ML v2 development-validation partition, not a sealed test.</li>"
        + (_targeted_limit_html(summary, addendum) if addendum is not None else "")
        + "</ul>"
    )
    rt = summary["runtime"]
    parts.append(
        f"<p class=muted>Runtime: total {rt['timings']['total_s']} s; peak memory "
        f"{rt['peak_memory_mb']} MB; {_e(rt['machine']['processor'])}.</p></main></body></html>"
    )
    return "\n".join(parts)
