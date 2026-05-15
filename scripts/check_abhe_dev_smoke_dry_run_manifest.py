#!/usr/bin/env python3
"""Validate the dry-run manifest emitted by the ABHE dev smoke runner skeleton."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_dev_smoke_dry_run_manifest.json")
REQUIRED_FIELDS = {
    "artifact_kind",
    "schema_version",
    "arm",
    "fresh_dev_slice",
    "dry_run",
    "compact_only",
    "no_provider",
    "no_bfcl",
    "no_scorer",
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
    "candidate_generated",
    "candidate_jsonl_created",
    "performance_evidence",
    "execution_authorized",
    "runner_mode",
}
TRUE_KEYS = {"dry_run", "compact_only", "no_provider", "no_bfcl", "no_scorer"}
FALSE_KEYS = {
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
    "candidate_generated",
    "candidate_jsonl_created",
    "performance_evidence",
    "execution_authorized",
}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def validate_manifest(manifest: Dict[str, Any]) -> List[str]:
    blockers = []
    missing = sorted(REQUIRED_FIELDS - set(manifest))
    if missing:
        blockers.append("dry_run_manifest_required_fields_missing:%s" % ",".join(missing))
        return blockers
    if manifest.get("artifact_kind") != "abhe_dev_smoke_dry_run_manifest":
        blockers.append("dry_run_manifest_artifact_kind_invalid:%r" % manifest.get("artifact_kind"))
    if manifest.get("schema_version") != "abhe_dev_smoke_dry_run_manifest_v0":
        blockers.append("dry_run_manifest_schema_version_invalid:%r" % manifest.get("schema_version"))
    if manifest.get("arm") not in {"baseline", "candidate"}:
        blockers.append("dry_run_manifest_arm_invalid:%r" % manifest.get("arm"))
    if not manifest.get("fresh_dev_slice"):
        blockers.append("dry_run_manifest_fresh_dev_slice_empty")
    if manifest.get("runner_mode") != "dry_run_only":
        blockers.append("dry_run_manifest_runner_mode_invalid:%r" % manifest.get("runner_mode"))
    for key in sorted(TRUE_KEYS):
        if manifest.get(key) is not True:
            blockers.append("dry_run_manifest_%s_not_true:%r" % (key, manifest.get(key)))
    for key in sorted(FALSE_KEYS):
        if manifest.get(key) is not False:
            blockers.append("dry_run_manifest_%s_not_false:%r" % (key, manifest.get(key)))
    blockers.extend(scan_value(manifest, label="dry_run_manifest"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_MANIFEST) -> Dict[str, Any]:
    if not path.exists():
        return {
            "report_scope": "abhe_dev_smoke_dry_run_manifest_check",
            "manifest_path": str(path),
            "manifest_present": False,
            "abhe_dev_smoke_dry_run_manifest_passed": False,
            "blockers": ["dry_run_manifest_missing"],
        }
    manifest = _load(path)
    blockers = validate_manifest(manifest)
    return {
        "report_scope": "abhe_dev_smoke_dry_run_manifest_check",
        "manifest_path": str(path),
        "manifest_present": True,
        "arm": manifest.get("arm"),
        "provider_calls_made": manifest.get("provider_calls_made"),
        "bfcl_generate_called": manifest.get("bfcl_generate_called"),
        "bfcl_evaluate_called": manifest.get("bfcl_evaluate_called"),
        "scorer_called": manifest.get("scorer_called"),
        "candidate_generated": manifest.get("candidate_generated"),
        "performance_evidence": manifest.get("performance_evidence"),
        "abhe_dev_smoke_dry_run_manifest_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "abhe_dev_smoke_dry_run_manifest_check",
            "abhe_dev_smoke_dry_run_manifest_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_dev_smoke_dry_run_manifest_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
