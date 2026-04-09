from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def dominates(a: Dict[str, float], b: Dict[str, float]) -> bool:
    return (
        a["acc"] >= b["acc"]
        and a["cost"] <= b["cost"]
        and a["regression"] <= b["regression"]
        and (
            a["acc"] > b["acc"]
            or a["cost"] < b["cost"]
            or a["regression"] < b["regression"]
        )
    )


def select_patch(baseline_path: str, candidate_path: str) -> Dict[str, object]:
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    candidate = json.loads(Path(candidate_path).read_text(encoding="utf-8"))

    decision = {
        "accept": dominates(candidate, baseline),
        "baseline": baseline,
        "candidate": candidate,
        "reason": "",
    }
    if decision["accept"]:
        decision["reason"] = "candidate dominates baseline on Pareto criteria"
    else:
        decision["reason"] = "candidate does not dominate baseline"
    return decision

