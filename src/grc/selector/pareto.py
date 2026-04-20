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
MANIFEST_MATCH_KEYS = (
    "protocol_id",
    "test_category",
    "bfcl_model_alias",
    "upstream_profile",
    "upstream_model_route",
)


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
    evaluation_status = str(metrics.get("evaluation_status") or "")
    if evaluation_status != "complete":
        issues.append(f"evaluation_status={evaluation_status or 'missing'}")

    metric_sources = metrics.get("metric_sources")
    if not isinstance(metric_sources, list) or not any(str(item).strip() for item in metric_sources):
        issues.append("metric_sources empty")

    artifact_issues = metrics.get("artifact_validity_issues")
    if isinstance(artifact_issues, list) and artifact_issues:
        issues.extend(f"artifact: {item}" for item in artifact_issues)

    artifact_dir = metrics_path.parent
    failure_summary_path = artifact_dir / "failure_summary.json"
    if failure_summary_path.exists():
        failure_summary = _load_json(failure_summary_path)
        trace_count = failure_summary.get("trace_count")
        if trace_count is None or float(trace_count) <= 0:
            issues.append("trace_count <= 0")

    return issues


def _validate_manifest_consistency(
    baseline_manifest_path: str | None,
    candidate_manifest_path: str | None,
) -> list[str]:
    if not baseline_manifest_path or not candidate_manifest_path:
        return ["run manifest missing for baseline or candidate"]
    baseline_manifest = _load_json(Path(baseline_manifest_path))
    candidate_manifest = _load_json(Path(candidate_manifest_path))
    issues: list[str] = []

    # Equality checks for core experiment identity
    for key in MANIFEST_MATCH_KEYS:
        if str(baseline_manifest.get(key, "")) != str(candidate_manifest.get(key, "")):
            issues.append(f"manifest mismatch on {key}")

    # Special lane pairing validation (baseline vs candidate must form a valid pair)
    baseline_lane = str(baseline_manifest.get("lane", ""))
    candidate_lane = str(candidate_manifest.get("lane", ""))
    if baseline_lane != "compatibility_baseline":
        issues.append(f"baseline lane must be compatibility_baseline, got {baseline_lane}")
    if candidate_lane != "compiler_patch":
        issues.append(f"candidate lane must be compiler_patch, got {candidate_lane}")

    return issues


def _load_compile_status(path: str | None) -> Dict[str, Any]:
    if not path:
        return {}
    return _load_json(Path(path))


def _compile_status_block_reason(compile_status: Dict[str, Any]) -> str | None:
    status = str(compile_status.get("status") or "")
    if status in {"", "actionable_patch"}:
        return None
    if status in {
        "no_failure_evidence",
        "uncompilable_failure_evidence",
        "evaluation_incomplete",
        "candidate_invalid",
        "candidate_does_not_dominate",
        "compile_failed",
    }:
        return status
    return f"compile_status_{status}"


def select_patch(
    baseline_path: str,
    candidate_path: str,
    *,
    baseline_manifest_path: str | None = None,
    candidate_manifest_path: str | None = None,
    compile_status_path: str | None = None,
) -> Dict[str, object]:
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

    compile_status = _load_compile_status(compile_status_path)
    compile_block_reason = _compile_status_block_reason(compile_status)
    manifest_issues = _validate_manifest_consistency(baseline_manifest_path, candidate_manifest_path)

    if compile_block_reason == "no_failure_evidence":
        accept = False
        reason = "no_failure_evidence"
    elif compile_block_reason == "uncompilable_failure_evidence":
        accept = False
        reason = "uncompilable_failure_evidence"
    elif compile_block_reason == "compile_failed":
        accept = False
        reason = "candidate_invalid"
    elif not baseline_valid or not candidate_valid:
        accept = False
        reason = "evaluation_incomplete" if any("evaluation_status" in issue for issue in candidate_issues) else "candidate_invalid"
    elif manifest_issues:
        accept = False
        reason = "candidate_invalid"
    else:
        accept = dominates(candidate, baseline)
        reason = "candidate_does_not_dominate" if not accept else "accepted"

    detail_issues: list[str] = []
    if not baseline_valid:
        detail_issues.extend(f"baseline: {issue}" for issue in baseline_issues)
    if not candidate_valid:
        detail_issues.extend(f"candidate: {issue}" for issue in candidate_issues)
    if manifest_issues:
        detail_issues.extend(f"manifest: {issue}" for issue in manifest_issues)
    if compile_block_reason and compile_block_reason not in {"no_failure_evidence", "uncompilable_failure_evidence"}:
        detail_issues.append(f"compile: {compile_block_reason}")

    return {
        "accept": accept,
        "reason": reason,
        "baseline": baseline,
        "candidate": candidate,
        "baseline_valid": baseline_valid,
        "candidate_valid": candidate_valid,
        "baseline_validity_issues": baseline_issues,
        "candidate_validity_issues": candidate_issues,
        "manifest_validity_issues": manifest_issues,
        "compile_status": compile_status,
        "detail_issues": detail_issues,
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

    if accepted_dir and rejected_dir:
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
