from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

from grc.compiler.failure_signature import top_k_signatures
from grc.selector.history import retrieve

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


def _load_failures(path: Path) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            failures.append(item)
    return failures


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_yaml_like(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _signature_matches(failure: dict[str, Any], signature: dict[str, Any]) -> bool:
    return (
        str(failure.get("stage")) == str(signature.get("stage"))
        and str(failure.get("failure_type") or failure.get("error_type")) == str(signature.get("type"))
    )


def _subset_failures(failures: list[dict[str, Any]], signature: dict[str, Any]) -> list[dict[str, Any]]:
    return [failure for failure in failures if _signature_matches(failure, signature)]


def _policy_units_from_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    payload = {
        "policy_units": [
            {
                "name": f"policy_{fingerprint}",
                "trigger": {
                    "error_types": list(record.get("error_families") or []),
                    "request_predicates": list(record.get("request_predicates") or []),
                },
                "source_failure_signature": signature,
            }
            for fingerprint, signature in zip(
                record.get("policy_fingerprints") or ["history_reuse"],
                record.get("failure_signatures") or [{}],
            )
        ]
    }
    return payload["policy_units"]


def generate_proposals(
    failures_path: Path,
    history_path: Path,
    out_dir: Path,
    *,
    top_k_signatures_count: int = 3,
    target_category: str = "multi_turn_miss_param",
    holdout_category: str = "simple_python",
    iteration_id: str | None = None,
) -> dict[str, Any]:
    failures = _load_failures(failures_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = top_k_signatures([type("Failure", (), item)() for item in failures], k=top_k_signatures_count)
    created: list[dict[str, Any]] = []
    for index, summary in enumerate(summaries):
        signature = summary.signature.model_dump(mode="json")
        signature["request_predicates"] = sorted(
            {
                predicate
                for failure in _subset_failures(failures, signature)
                for predicate in (failure.get("request_predicates") or [])
            }
        )
        fresh_dir = out_dir / f"fresh_{index:02d}"
        fresh_failures = _subset_failures(failures, signature)
        fresh_failures_path = fresh_dir / "failures.jsonl"
        fresh_dir.mkdir(parents=True, exist_ok=True)
        fresh_failures_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in fresh_failures),
            encoding="utf-8",
        )
        if "yaml" not in sys.modules:
            sys.modules["yaml"] = types.SimpleNamespace(
                safe_dump=lambda data, **_: json.dumps(data, ensure_ascii=False, indent=2),
                safe_load=json.loads,
            )
        from grc.compiler.trace_to_patch import compile_patch

        compile_status = compile_patch(
            str(fresh_failures_path),
            str(fresh_dir / "rule.yaml"),
            patch_id=fresh_dir.name,
            candidate_dir=str(fresh_dir),
        )
        metadata = {
            "proposal_mode": "fresh",
            "proposal_kind": "fresh",
            "failure_signature": signature,
            "target_category": target_category,
            "holdout_category": holdout_category,
            "iteration_id": iteration_id,
            "compile_status": compile_status.get("status"),
        }
        _write_json(fresh_dir / "proposal_metadata.json", metadata)
        created.append({"candidate_dir": str(fresh_dir), **metadata})

        for reused in retrieve(history_path, signature, top_k=1):
            reuse_dir = out_dir / f"reuse_{index:02d}_{str(reused.get('patch_id') or 'history')}"
            reuse_dir.mkdir(parents=True, exist_ok=True)
            _write_yaml_like(reuse_dir / "policy_unit.yaml", {"policy_units": _policy_units_from_record(reused)})
            reuse_meta = {
                "proposal_mode": "reuse",
                "proposal_kind": "reuse",
                "source_history_fingerprint": (reused.get("policy_fingerprints") or [None])[0],
                "reuse_source_patch_id": reused.get("patch_id"),
                "failure_signature": signature,
                "target_category": target_category,
                "holdout_category": holdout_category,
                "iteration_id": iteration_id,
                "compile_status": "incomplete",
            }
            _write_json(reuse_dir / "proposal_metadata.json", reuse_meta)
            _write_json(reuse_dir / "compile_status.json", {"status": "incomplete"})
            created.append({"candidate_dir": str(reuse_dir), **reuse_meta})

            if signature.get("request_predicates"):
                specialize_dir = out_dir / f"specialize_{index:02d}_{str(reused.get('patch_id') or 'history')}"
                specialize_dir.mkdir(parents=True, exist_ok=True)
                units = _policy_units_from_record(reused)
                for unit in units:
                    trigger = unit.setdefault("trigger", {})
                    trigger["request_predicates"] = list(signature.get("request_predicates") or [])
                _write_yaml_like(specialize_dir / "policy_unit.yaml", {"policy_units": units})
                specialize_meta = {
                    "proposal_mode": "specialize",
                    "proposal_kind": "specialize",
                    "source_history_fingerprint": (reused.get("policy_fingerprints") or [None])[0],
                    "reuse_source_patch_id": reused.get("patch_id"),
                    "failure_signature": signature,
                    "target_category": target_category,
                    "holdout_category": holdout_category,
                    "iteration_id": iteration_id,
                    "compile_status": "incomplete",
                }
                _write_json(specialize_dir / "proposal_metadata.json", specialize_meta)
                _write_json(specialize_dir / "compile_status.json", {"status": "incomplete"})
                created.append({"candidate_dir": str(specialize_dir), **specialize_meta})
            break

    summary = {
        "proposal_count": len(created),
        "proposals": created,
        "top_failure_signatures": [item.model_dump(mode="json") for item in summaries],
    }
    _write_json(out_dir / "proposal_summary.json", summary)
    return summary
