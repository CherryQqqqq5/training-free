from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict

import yaml


MAXIMIZE_KEYS = ("acc",)
MINIMIZE_KEYS = ("cost", "latency", "regression")


def _metric_value(metrics: Dict[str, object], key: str, default: float = 0.0) -> float:
    value = metrics.get(key, default)
    if value is None:
        return default
    return float(value)


def dominates(a: Dict[str, float], b: Dict[str, float]) -> bool:
    maximize_ok = all(_metric_value(a, key) >= _metric_value(b, key) for key in MAXIMIZE_KEYS)
    minimize_ok = all(_metric_value(a, key) <= _metric_value(b, key) for key in MINIMIZE_KEYS)
    strict = any(_metric_value(a, key) > _metric_value(b, key) for key in MAXIMIZE_KEYS) or any(
        _metric_value(a, key) < _metric_value(b, key) for key in MINIMIZE_KEYS
    )
    return maximize_ok and minimize_ok and strict


def select_patch(baseline_path: str, candidate_path: str) -> Dict[str, object]:
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    candidate = json.loads(Path(candidate_path).read_text(encoding="utf-8"))

    subset_regressions = []
    baseline_subsets = baseline.get("subsets", {}) if isinstance(baseline, dict) else {}
    candidate_subsets = candidate.get("subsets", {}) if isinstance(candidate, dict) else {}
    if isinstance(baseline_subsets, dict) and isinstance(candidate_subsets, dict):
        for subset, base_score in baseline_subsets.items():
            cand_score = candidate_subsets.get(subset)
            if cand_score is not None and float(cand_score) < float(base_score):
                subset_regressions.append(
                    {
                        "subset": subset,
                        "baseline": float(base_score),
                        "candidate": float(cand_score),
                    }
                )

    regression = sum(item["baseline"] - item["candidate"] for item in subset_regressions)
    candidate["regression"] = max(_metric_value(candidate, "regression"), regression)

    decision = {
        "accept": dominates(candidate, baseline),
        "baseline": baseline,
        "candidate": candidate,
        "reason": "",
        "subset_regressions": subset_regressions,
    }
    if decision["accept"]:
        decision["reason"] = "candidate dominates baseline on Pareto criteria"
    else:
        decision["reason"] = "candidate does not dominate baseline"
    return decision


def write_selection_outputs(
    decision: Dict[str, object],
    candidate_dir: str | None,
    rule_path: str | None,
    accepted_dir: str | None,
    rejected_dir: str | None,
    active_dir: str | None,
    out_path: str | None,
) -> None:
    patch_id = None
    source = Path(rule_path) if rule_path else None

    if out_path:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    if candidate_dir:
        candidate_path = Path(candidate_dir)
        candidate_file = candidate_path / "accept.json"
        candidate_file.parent.mkdir(parents=True, exist_ok=True)
        candidate_file.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
        patch_id = candidate_path.name

    if not source or not source.exists():
        return

    if patch_id is None:
        patch_id = source.stem
        try:
            patch_data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
            patch_id = str(patch_data.get("patch_id") or patch_id)
        except Exception:
            pass

    target_root = accepted_dir if decision.get("accept") else rejected_dir
    if target_root:
        target_dir = Path(target_root) / patch_id
        if candidate_dir and Path(candidate_dir).exists():
            shutil.copytree(Path(candidate_dir), target_dir, dirs_exist_ok=True)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target_dir / "rule.yaml")

    if decision.get("accept") and active_dir:
        target = Path(active_dir) / f"{patch_id}.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
