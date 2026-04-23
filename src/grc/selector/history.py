from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if yaml is None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _load_policy_units_without_yaml(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    units: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_trigger = False
    in_signature = False

    def parse_inline_list(raw: str) -> list[str]:
        raw = raw.strip()
        if not (raw.startswith("[") and raw.endswith("]")):
            return []
        body = raw[1:-1].strip()
        if not body:
            return []
        return [item.strip().strip("'\"") for item in body.split(",") if item.strip()]

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- name:"):
            if current:
                units.append(current)
            current = {"name": line.split(":", 1)[1].strip(), "trigger": {}, "source_failure_signature": {}}
            in_trigger = False
            in_signature = False
            continue
        if current is None:
            continue
        if line == "trigger:":
            in_trigger = True
            in_signature = False
            continue
        if line == "source_failure_signature:":
            in_trigger = False
            in_signature = True
            continue
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        if in_trigger and key in {"error_types", "request_predicates"}:
            current["trigger"][key] = parse_inline_list(value)
        elif in_signature:
            current["source_failure_signature"][key] = value.strip("'\"")
        elif key in {"recommended_tools", "forbidden_terminations", "evidence_requirements"}:
            current[key] = parse_inline_list(value)
        elif key in {"continue_condition", "stop_condition"}:
            current[key] = value.strip("'\"")
    if current:
        units.append(current)
    return units


def policy_fingerprint(policy_unit: dict[str, Any]) -> str:
    encoded = json.dumps(policy_unit, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _policy_units(candidate_dir: Path | None) -> list[dict[str, Any]]:
    if candidate_dir is None:
        return []
    policy_path = candidate_dir / "policy_unit.yaml"
    if policy_path.exists() and yaml is None:
        return _load_policy_units_without_yaml(policy_path)
    data = _load_yaml(policy_path)
    units = data.get("policy_units") if isinstance(data, dict) else []
    if isinstance(units, list) and units:
        return [unit for unit in units if isinstance(unit, dict)]

    rule_data = _load_yaml(candidate_dir / "rule.yaml")
    rules = rule_data.get("rules") if isinstance(rule_data, dict) else []
    synthesized: list[dict[str, Any]] = []
    if isinstance(rules, list):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            action = rule.get("action") if isinstance(rule.get("action"), dict) else {}
            policy = action.get("decision_policy") if isinstance(action.get("decision_policy"), dict) else {}
            trigger = rule.get("trigger") if isinstance(rule.get("trigger"), dict) else {}
            if not policy:
                continue
            synthesized.append(
                {
                    "name": f"policy_{rule.get('rule_id') or 'unknown'}",
                    "rule_id": rule.get("rule_id"),
                    "trigger": {
                        "error_types": list(trigger.get("error_types") or []),
                        "request_predicates": list(
                            trigger.get("request_predicates") or policy.get("request_predicates") or []
                        ),
                    },
                    "source_failure_signature": {
                        "stage": "*",
                        "type": (trigger.get("error_types") or ["*"])[0],
                        "tool_schema_hash": "*",
                        "literals_pattern": "unknown",
                    },
                    **policy,
                }
            )
    return synthesized


def _proposal_metadata(candidate_dir: Path | None) -> dict[str, Any]:
    if candidate_dir is None:
        return {}
    return _load_json(candidate_dir / "proposal_metadata.json")


def history_record_from_selection(decision: dict[str, Any], candidate_dir: str | None) -> dict[str, Any]:
    candidate_path = Path(candidate_dir) if candidate_dir else None
    units = _policy_units(candidate_path)
    candidate = decision.get("candidate") if isinstance(decision.get("candidate"), dict) else {}
    proposal_metadata = _proposal_metadata(candidate_path)
    compile_status = _load_json(candidate_path / "compile_status.json") if candidate_path else {}
    decision_code = str(decision.get("decision_code") or "")
    return {
        "decision_code": decision.get("decision_code"),
        "accept": bool(decision.get("accept")),
        "target_delta": decision.get("target_delta"),
        "selection_score": decision.get("selection_score"),
        "patch_id": candidate_path.name if candidate_path else None,
        "proposal_kind": proposal_metadata.get("proposal_mode") or proposal_metadata.get("proposal_kind"),
        "reuse_source_patch_id": proposal_metadata.get("reuse_source_patch_id"),
        "reuse_source_fingerprint": proposal_metadata.get("source_history_fingerprint"),
        "subset_family": proposal_metadata.get("target_category"),
        "regression_profile": {
            "regression": candidate.get("regression"),
            "subset_regressions": decision.get("subset_regressions") or [],
        },
        "compile_status": str(compile_status.get("status") or proposal_metadata.get("compile_status") or "unknown"),
        "error_families": sorted(
            {
                error
                for unit in units
                for error in ((unit.get("trigger") or {}).get("error_types") or [])
                if isinstance(error, str)
            }
        ),
        "request_predicates": sorted(
            {
                predicate
                for unit in units
                for predicate in ((unit.get("trigger") or {}).get("request_predicates") or [])
                if isinstance(predicate, str)
            }
        ),
        "recommended_tools": sorted(
            {
                tool
                for unit in units
                for tool in (unit.get("recommended_tools") or [])
                if isinstance(tool, str)
            }
        ),
        "policy_fingerprints": [policy_fingerprint(unit) for unit in units],
        "policy_units": units,
        "reusable_for_search": decision_code in {"accepted", "retained"}
        and decision.get("candidate_valid") is not False
        and decision.get("manifest_valid") is not False
        and str(compile_status.get("status") or proposal_metadata.get("compile_status") or "ok")
        not in {"compile_failed", "incomplete", "rejected_before_eval"},
        "failure_signatures": [
            unit.get("source_failure_signature")
            for unit in units
            if isinstance(unit.get("source_failure_signature"), dict)
        ],
        "candidate_metrics": candidate,
    }


def append_history_record(history_path: Path, decision: dict[str, Any], candidate_dir: str | None) -> dict[str, Any]:
    record = history_record_from_selection(decision, candidate_dir)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_history(history_path: Path) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def query_history(
    history_path: Path,
    *,
    error_family: str,
    request_predicates: list[str] | None = None,
    policy_fingerprint: str | None = None,
) -> list[dict[str, Any]]:
    wanted_predicates = set(request_predicates or [])
    matches: list[dict[str, Any]] = []
    for record in load_history(history_path):
        if not record.get("reusable_for_search"):
            continue
        if error_family not in set(record.get("error_families") or []):
            continue
        record_predicates = set(record.get("request_predicates") or [])
        if wanted_predicates and not wanted_predicates.issubset(record_predicates):
            continue
        if policy_fingerprint and policy_fingerprint not in set(record.get("policy_fingerprints") or []):
            continue
        matches.append(record)
    return matches


def retrieve(history_path: Path, signature: dict[str, Any], *, top_k: int = 5) -> list[dict[str, Any]]:
    wanted_stage = signature.get("stage")
    wanted_type = signature.get("type")
    wanted_hash = signature.get("tool_schema_hash")
    wanted_literals = signature.get("literals_pattern")
    wanted_predicates = set(signature.get("request_predicates") or [])
    matches: list[tuple[int, dict[str, Any]]] = []
    for record in load_history(history_path):
        if not record.get("reusable_for_search"):
            continue
        signatures = record.get("failure_signatures") or []
        if not isinstance(signatures, list):
            continue
        for item in signatures:
            if not isinstance(item, dict):
                continue
            if item.get("stage") == wanted_stage and item.get("type") == wanted_type:
                score = 10
                reasons = ["stage_type_exact"]
                if wanted_hash and item.get("tool_schema_hash") == wanted_hash:
                    score += 4
                    reasons.append("tool_schema_hash_exact")
                elif wanted_hash and (item.get("tool_schema_hash") == "*" or wanted_hash == "*"):
                    score += 1
                    reasons.append("tool_schema_hash_wildcard")
                if wanted_literals and item.get("literals_pattern") == wanted_literals:
                    score += 3
                    reasons.append("literals_pattern_exact")
                record_predicates = set(record.get("request_predicates") or [])
                overlap = wanted_predicates & record_predicates
                if overlap:
                    score += len(overlap)
                    reasons.append("request_predicate_overlap")
                enriched = dict(record)
                enriched["match_score"] = score
                enriched["match_reasons"] = reasons
                enriched["matched_fields"] = {
                    "stage": item.get("stage"),
                    "type": item.get("type"),
                    "tool_schema_hash": item.get("tool_schema_hash"),
                    "literals_pattern": item.get("literals_pattern"),
                }
                matches.append((score, enriched))
                break
    return [record for _, record in sorted(matches, key=lambda pair: pair[0], reverse=True)[:top_k]]
