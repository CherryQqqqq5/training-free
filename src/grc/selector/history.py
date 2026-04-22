from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


def _load_yaml(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except Exception:
        data = None
    if isinstance(data, dict):
        return data
    if yaml is None:
        return {}
    try:
        data = yaml.safe_load(text) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalized_predicates(rule: Dict[str, Any]) -> List[str]:
    action = rule.get("action", {}) if isinstance(rule, dict) else {}
    trigger = rule.get("trigger", {}) if isinstance(rule, dict) else {}
    decision_policy = action.get("decision_policy", {}) if isinstance(action, dict) else {}
    predicates = decision_policy.get("request_predicates")
    if not predicates:
        predicates = trigger.get("request_predicates", [])
    if not isinstance(predicates, list):
        return []
    return sorted({str(item).strip() for item in predicates if str(item).strip()})


def _policy_fingerprint(rule: Dict[str, Any]) -> str | None:
    action = rule.get("action", {}) if isinstance(rule, dict) else {}
    decision_policy = action.get("decision_policy", {}) if isinstance(action, dict) else {}
    if not isinstance(decision_policy, dict) or not decision_policy:
        return None
    payload = {
        "error_types": sorted(rule.get("trigger", {}).get("error_types", [])),
        "request_predicates": _normalized_predicates(rule),
        "decision_policy": decision_policy,
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()[:16]


def _error_families(rule_bundle: Dict[str, Any]) -> List[str]:
    families: set[str] = set()
    for rule in rule_bundle.get("rules", []) if isinstance(rule_bundle, dict) else []:
        trigger = rule.get("trigger", {}) if isinstance(rule, dict) else {}
        for error_type in trigger.get("error_types", []) if isinstance(trigger, dict) else []:
            normalized = str(error_type).strip()
            if normalized:
                families.add(normalized)
    return sorted(families)


def _request_predicates(rule_bundle: Dict[str, Any]) -> List[str]:
    predicates: set[str] = set()
    for rule in rule_bundle.get("rules", []) if isinstance(rule_bundle, dict) else []:
        predicates.update(_normalized_predicates(rule))
    return sorted(predicates)


def _policy_fingerprints(rule_bundle: Dict[str, Any]) -> List[str]:
    fingerprints: list[str] = []
    for rule in rule_bundle.get("rules", []) if isinstance(rule_bundle, dict) else []:
        fingerprint = _policy_fingerprint(rule)
        if fingerprint and fingerprint not in fingerprints:
            fingerprints.append(fingerprint)
    return fingerprints


def _reusable_for_search(decision: Dict[str, Any]) -> bool:
    decision_code = str(decision.get("decision_code") or "")
    candidate = decision.get("candidate") if isinstance(decision.get("candidate"), dict) else {}
    return bool(
        decision_code in {"accepted", "retained"}
        and decision.get("candidate_valid")
        and decision.get("manifest_valid")
        and str(candidate.get("evaluation_status") or "").strip().lower() == "complete"
        and not decision.get("subset_regressions")
    )


def build_history_record(
    decision: Dict[str, Any],
    *,
    rule_path: str | None,
) -> Dict[str, Any] | None:
    if not rule_path:
        return None
    source = Path(rule_path)
    if not source.exists():
        return None

    bundle = _load_yaml(source)
    if not bundle:
        return None

    candidate = decision.get("candidate") if isinstance(decision.get("candidate"), dict) else {}
    return {
        "patch_id": str(bundle.get("patch_id") or source.stem),
        "decision_code": str(decision.get("decision_code") or ""),
        "error_families": _error_families(bundle),
        "request_predicates": _request_predicates(bundle),
        "policy_fingerprints": _policy_fingerprints(bundle),
        "target_delta": float(decision.get("target_delta") or 0.0),
        "acc": float(candidate.get("acc") or 0.0),
        "cost": float(candidate.get("cost") or 0.0),
        "latency": float(candidate.get("latency") or 0.0),
        "regression": float(candidate.get("regression") or 0.0),
        "paired_rerun_consistent": bool((decision.get("paired_rerun") or {}).get("paired_rerun_consistent")),
        "reusable_for_search": _reusable_for_search(decision),
    }


def append_history(history_path: str | Path, record: Dict[str, Any] | None) -> None:
    if not record:
        return
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_history(history_path: str | Path) -> List[Dict[str, Any]]:
    path = Path(history_path)
    if not path.exists():
        return []
    records: list[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def query_history(
    history_path: str | Path,
    *,
    error_family: str | None = None,
    request_predicates: Iterable[str] | None = None,
    policy_fingerprint: str | None = None,
) -> List[Dict[str, Any]]:
    requested_predicates = sorted({str(item).strip() for item in (request_predicates or []) if str(item).strip()})
    matches: list[Dict[str, Any]] = []
    for record in load_history(history_path):
        if not record.get("reusable_for_search"):
            continue
        if error_family and error_family not in record.get("error_families", []):
            continue
        if policy_fingerprint and policy_fingerprint not in record.get("policy_fingerprints", []):
            continue
        if requested_predicates:
            record_predicates = sorted(record.get("request_predicates", []))
            if record_predicates != requested_predicates:
                continue
        matches.append(record)
    return matches
