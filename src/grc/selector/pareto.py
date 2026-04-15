from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


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


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        data: Dict[str, Any] = {}
        active_list_key: str | None = None
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue
            if not raw_line.startswith(" ") and ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if value == "[]":
                    data[key] = []
                    active_list_key = None
                elif value == "":
                    data[key] = []
                    active_list_key = key
                elif value.isdigit():
                    data[key] = int(value)
                    active_list_key = None
                else:
                    data[key] = value.strip("'\"")
                    active_list_key = None
                continue
            if active_list_key and line.lstrip().startswith("-"):
                data.setdefault(active_list_key, []).append(line.lstrip()[1:].strip())
        return data
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _artifact_validity(metrics: Dict[str, Any], metrics_path: Path) -> list[str]:
    issues: list[str] = []
    metric_sources = metrics.get("metric_sources")
    if not isinstance(metric_sources, list) or not any(str(item).strip() for item in metric_sources):
        issues.append("metric_sources empty")

    artifact_dir = metrics_path.parent

    failure_summary_path = artifact_dir / "failure_summary.json"
    if failure_summary_path.exists():
        failure_summary = _load_json(failure_summary_path)
        trace_count = failure_summary.get("trace_count")
        if trace_count is None or float(trace_count) <= 0:
            issues.append("trace_count <= 0")

    rule_path = artifact_dir / "rule.yaml"
    if rule_path.exists():
        rule_data = _load_yaml(rule_path)
        if float(rule_data.get("source_failure_count") or 0) <= 0:
            issues.append("source_failure_count <= 0")
        rules = rule_data.get("rules")
        if not isinstance(rules, list) or not rules:
            issues.append("rules empty")

    return issues


def select_patch(baseline_path: str, candidate_path: str) -> Dict[str, object]:
    baseline_file = Path(baseline_path)
    candidate_file = Path(candidate_path)
    baseline = _load_json(baseline_file)
    candidate = _load_json(candidate_file)

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

    baseline_issues = _artifact_validity(baseline, baseline_file)
    candidate_issues = _artifact_validity(candidate, candidate_file)
    baseline_valid = not baseline_issues
    candidate_valid = not candidate_issues

    if not baseline_valid or not candidate_valid:
        blockers = []
        if not baseline_valid:
            blockers.append(f"baseline invalid: {', '.join(baseline_issues)}")
        if not candidate_valid:
            blockers.append(f"candidate invalid: {', '.join(candidate_issues)}")
        accept = False
        reason = "selection blocked: " + "; ".join(blockers)
    else:
        accept = dominates(candidate, baseline)
        reason = "candidate dominates baseline on Pareto criteria" if accept else "candidate does not dominate baseline"

    return {
        "accept": accept,
        "baseline": baseline,
        "candidate": candidate,
        "baseline_valid": baseline_valid,
        "candidate_valid": candidate_valid,
        "baseline_validity_issues": baseline_issues,
        "candidate_validity_issues": candidate_issues,
        "reason": reason,
        "subset_regressions": subset_regressions,
    }


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
            patch_data = _load_yaml(source)
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
