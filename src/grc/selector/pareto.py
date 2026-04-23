from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict

from grc.selector.history import append_history_record

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


MAXIMIZE_KEYS = ("acc",)
MINIMIZE_KEYS = ("cost", "latency", "regression")
MANIFEST_MATCH_KEYS = (
    "protocol_id",
    "test_category",
    "bfcl_model_alias",
    "upstream_profile",
    "upstream_model_route",
)
TARGET_UPLIFT_TAU = 0.5
COST_BUDGET_RATIO = 0.10
LATENCY_BUDGET_RATIO = 0.10
SUBSET_REGRESSION_CAP = 0.5
LATENCY_SCORE_WEIGHT = 0.001
REGRESSION_SCORE_WEIGHT = 1.0


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


def _target_metric(metrics: Dict[str, Any]) -> float:
    test_category = str(metrics.get("test_category") or "").strip()
    subsets = metrics.get("subsets")
    if test_category and isinstance(subsets, dict) and test_category in subsets:
        return _metric_value(subsets, test_category)
    return _metric_value(metrics, "acc")


def _selection_score(metrics: Dict[str, Any]) -> float:
    return (
        _target_metric(metrics)
        - LATENCY_SCORE_WEIGHT * _metric_value(metrics, "latency")
        - REGRESSION_SCORE_WEIGHT * _metric_value(metrics, "regression")
    )


def _within_budget(candidate: Dict[str, Any], baseline: Dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    base_cost = _metric_value(baseline, "cost")
    cand_cost = _metric_value(candidate, "cost")
    allowed_cost = base_cost + max(1.0, base_cost) * COST_BUDGET_RATIO
    if cand_cost > allowed_cost:
        issues.append(f"cost budget exceeded: {cand_cost:.3f} > {allowed_cost:.3f}")

    base_latency = _metric_value(baseline, "latency")
    cand_latency = _metric_value(candidate, "latency")
    allowed_latency = base_latency + max(1.0, base_latency) * LATENCY_BUDGET_RATIO
    if cand_latency > allowed_latency:
        issues.append(f"latency budget exceeded: {cand_latency:.3f} > {allowed_latency:.3f}")

    if _metric_value(candidate, "regression") > SUBSET_REGRESSION_CAP:
        issues.append(
            f"subset regression exceeded cap: {_metric_value(candidate, 'regression'):.3f} > {SUBSET_REGRESSION_CAP:.3f}"
        )
    return not issues, issues


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
    label = str(metrics.get("label") or "").strip().lower()
    artifact_dir = metrics_path.parent
    rule_path = artifact_dir / "rule.yaml"
    compile_status_path = artifact_dir / "compile_status.json"
    is_candidate_artifact = label == "candidate" or rule_path.exists() or compile_status_path.exists()
    evaluation_status = str(metrics.get("evaluation_status") or "").strip().lower()
    if evaluation_status != "complete":
        issues.append(f"evaluation_status != complete ({evaluation_status or 'missing'})")
    metric_sources = metrics.get("metric_sources")
    if not isinstance(metric_sources, list) or not any(str(item).strip() for item in metric_sources):
        issues.append("metric_sources empty")

    manifest_path = artifact_dir / "run_manifest.json"
    if not manifest_path.exists():
        issues.append("run_manifest missing")

    failure_summary_path = artifact_dir / "failure_summary.json"
    if failure_summary_path.exists():
        failure_summary = _load_json(failure_summary_path)
        trace_count = failure_summary.get("trace_count")
        if trace_count is None or float(trace_count) <= 0:
            issues.append("trace_count <= 0")

    if rule_path.exists():
        rule_data = _load_yaml(rule_path)
        if float(rule_data.get("source_failure_count") or 0) <= 0:
            issues.append("source_failure_count <= 0")
        rules = rule_data.get("rules")
        if not isinstance(rules, list) or not rules:
            issues.append("rules empty")
    elif is_candidate_artifact:
        issues.append("rule.yaml missing")

    if is_candidate_artifact:
        if not compile_status_path.exists():
            issues.append("compile_status missing")
        else:
            compile_status = _load_json(compile_status_path)
            status = str(compile_status.get("status") or "").strip().lower()
            if status != "actionable_patch":
                issues.append(f"compile_status != actionable_patch ({status or 'missing'})")

    return issues


def _load_manifest(metrics_path: Path) -> Dict[str, Any]:
    manifest_path = metrics_path.parent / "run_manifest.json"
    if not manifest_path.exists():
        return {}
    return _load_json(manifest_path)


def _load_paired_rerun(metrics_path: Path) -> Dict[str, Any]:
    paired_path = metrics_path.parent / "paired_rerun.json"
    if not paired_path.exists():
        return {}
    return _load_json(paired_path)


def _manifest_consistency_issues(
    baseline_manifest: Dict[str, Any],
    candidate_manifest: Dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    if not baseline_manifest or not candidate_manifest:
        return issues
    for key in MANIFEST_MATCH_KEYS:
        base_value = baseline_manifest.get(key)
        cand_value = candidate_manifest.get(key)
        if base_value != cand_value:
            issues.append(f"{key} mismatch: baseline={base_value!r}, candidate={cand_value!r}")
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
    paired_rerun = _load_paired_rerun(candidate_file)
    if "paired_rerun_consistent" not in candidate and "paired_rerun_consistent" in paired_rerun:
        candidate["paired_rerun_consistent"] = paired_rerun.get("paired_rerun_consistent")
    baseline_valid = not baseline_issues
    candidate_valid = not candidate_issues
    baseline_manifest = _load_manifest(baseline_file)
    candidate_manifest = _load_manifest(candidate_file)
    manifest_issues = _manifest_consistency_issues(baseline_manifest, candidate_manifest)
    manifest_valid = not manifest_issues

    if not baseline_valid or not candidate_valid or not manifest_valid:
        blockers = []
        if not baseline_valid:
            blockers.append(f"baseline invalid: {', '.join(baseline_issues)}")
        if not candidate_valid:
            blockers.append(f"candidate invalid: {', '.join(candidate_issues)}")
        if not manifest_valid:
            blockers.append(f"manifest mismatch: {', '.join(manifest_issues)}")
        accept = False
        reason = "selection blocked: " + "; ".join(blockers)
        if not manifest_valid:
            decision_code = "candidate_invalid"
        elif not candidate_valid:
            if any(str(issue).startswith("evaluation_status != complete") for issue in candidate_issues):
                decision_code = "evaluation_incomplete"
            else:
                decision_code = "candidate_invalid"
        else:
            decision_code = "candidate_invalid"
    else:
        budget_ok, budget_issues = _within_budget(candidate, baseline)
        paired_consistent = bool(candidate.get("paired_rerun_consistent"))
        target_delta = _target_metric(candidate) - _target_metric(baseline)
        if not budget_ok:
            accept = False
            decision_code = "candidate_does_not_dominate"
            reason = "candidate exceeds bounded acceptance budget: " + "; ".join(budget_issues)
        elif paired_consistent and target_delta > TARGET_UPLIFT_TAU:
            accept = True
            decision_code = "accepted"
            reason = "candidate passed bounded acceptance with stable uplift"
        elif target_delta > 0:
            accept = False
            decision_code = "retained"
            if paired_consistent:
                reason = "candidate shows positive uplift but does not clear the acceptance threshold"
            else:
                reason = "candidate shows positive uplift but paired rerun consistency is not established"
        else:
            accept = False
            decision_code = "candidate_does_not_dominate"
            reason = "candidate did not produce positive target-slice uplift"

    return {
        "accept": accept,
        "decision_code": decision_code,
        "baseline": baseline,
        "candidate": candidate,
        "baseline_manifest": baseline_manifest,
        "candidate_manifest": candidate_manifest,
        "baseline_valid": baseline_valid,
        "candidate_valid": candidate_valid,
        "baseline_validity_issues": baseline_issues,
        "candidate_validity_issues": candidate_issues,
        "manifest_valid": manifest_valid,
        "manifest_consistency_issues": manifest_issues,
        "paired_rerun": paired_rerun,
        "reason": reason,
        "subset_regressions": subset_regressions,
        "target_delta": (_target_metric(candidate) - _target_metric(baseline)) if baseline and candidate else 0.0,
        "selection_score": _selection_score(candidate) if candidate else 0.0,
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
    def remove_path(path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

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
        append_history_record(candidate_path.parent / "history.jsonl", decision, candidate_dir)
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

    decision_code = str(decision.get("decision_code") or "")
    target_root = accepted_dir if decision.get("accept") else (rejected_dir if decision_code != "retained" else None)
    if target_root:
        target_dir = Path(target_root) / patch_id
        if candidate_dir and Path(candidate_dir).exists():
            shutil.copytree(Path(candidate_dir), target_dir, dirs_exist_ok=True)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target_dir / "rule.yaml")

    if accepted_dir and rejected_dir and decision_code != "retained":
        stale_root = rejected_dir if decision.get("accept") else accepted_dir
        stale_dir = Path(stale_root) / patch_id
        if stale_dir.exists():
            remove_path(stale_dir)

    if decision.get("accept") and active_dir:
        target = Path(active_dir) / f"{patch_id}.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    elif active_dir:
        stale_active = Path(active_dir) / f"{patch_id}.yaml"
        if stale_active.exists():
            remove_path(stale_active)
