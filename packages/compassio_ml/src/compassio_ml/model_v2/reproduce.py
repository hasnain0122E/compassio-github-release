"""Re-fit the saved champion from scratch and compare it with the saved artifact and scores."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from compassio_ml.external.paths import V2Paths
from compassio_ml.model_v2 import candidates as cm
from compassio_ml.model_v2.benchmark import expand, run_population
from compassio_ml.model_v2.data import load_aiddata_training, load_development
from compassio_ml.model_v2.plan import FastPlan


def reproduce_champion(paths: V2Paths, plan: FastPlan, run_dir: Path) -> dict[str, Any]:
    results = json.loads((run_dir / "results.json").read_text("utf-8"))
    artifact = results.get("champion_artifact")
    if not artifact:
        raise RuntimeError("this run selected no champion")
    candidate_dir = Path(artifact["directory"])
    manifest = json.loads((candidate_dir / "candidate_manifest.json").read_text("utf-8"))
    population, name = manifest["population"], manifest["candidate"]
    data = load_development(paths, plan)
    train = data.part("train")
    pop = plan.populations[population]
    mask = None
    if population == "combined_plus_aiddata":
        iati = train[train["source_id"].isin(plan.populations["combined"].train_sources)]
        train = pd.concat([iati, load_aiddata_training(paths, plan)], ignore_index=True)
        mask = (train["source_id"] != "aiddata").to_numpy()
    else:
        train = train[train["source_id"].isin(pop.train_sources)]
    names = [name] if name[0] in "ABCD" else [*expand(("A", "B", "C")), name]
    res = run_population(
        f"reproduce_{population}", train, plan, names, threshold_mask=mask, log=lambda _: None
    )
    refit = next(f for f in res.finalists if f.name == name)
    valid = data.part("valid")
    valid = valid[valid["source_id"].isin(plan.populations["combined"].valid_sources)]
    new_scores = cm.scores(refit.model, valid["text"].to_numpy(), refit.classifier_kind)
    saved = pd.read_parquet(run_dir / "valid_predictions.parquet")
    column = f"score::{population}/{name}"
    order = saved.set_index("candidate_id").loc[valid["candidate_id"], column].to_numpy()
    return {
        "candidate": f"{population}/{name}",
        "saved_fingerprint": manifest["model_fingerprint"],
        "refit_fingerprint": cm.fingerprint(refit.model),
        "fingerprint_identical": manifest["model_fingerprint"] == cm.fingerprint(refit.model),
        "threshold_identical": float(manifest["threshold"]) == float(refit.threshold),
        "max_abs_valid_score_difference": float(np.max(np.abs(order - new_scores))),
    }
