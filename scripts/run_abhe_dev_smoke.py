#!/usr/bin/env python3
"""Dry-run-only ABHE dev smoke runner skeleton."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_dev_smoke_dry_run_manifest.json")


def build_manifest(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "artifact_kind": "abhe_dev_smoke_dry_run_manifest",
        "schema_version": "abhe_dev_smoke_dry_run_manifest_v0",
        "arm": args.arm,
        "fresh_dev_slice": args.fresh_dev_slice,
        "dry_run": True,
        "compact_only": args.compact_only,
        "no_provider": args.no_provider,
        "no_bfcl": args.no_bfcl,
        "no_scorer": args.no_scorer,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "candidate_generated": False,
        "candidate_jsonl_created": False,
        "performance_evidence": False,
        "execution_authorized": False,
        "runner_mode": "dry_run_only",
    }


def write_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=["baseline", "candidate"], required=True)
    parser.add_argument("--fresh-dev-slice", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact-only", action="store_true")
    parser.add_argument("--no-provider", action="store_true")
    parser.add_argument("--no-bfcl", action="store_true")
    parser.add_argument("--no-scorer", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)

    missing_guards = [
        name
        for name in ("dry_run", "compact_only", "no_provider", "no_bfcl", "no_scorer")
        if getattr(args, name) is not True
    ]
    if missing_guards:
        print(json.dumps({
            "artifact_kind": "abhe_dev_smoke_dry_run_manifest",
            "dry_run_manifest_written": False,
            "blockers": ["missing_required_dry_run_guards:%s" % ",".join(missing_guards)],
        }, sort_keys=True))
        return 2

    manifest = build_manifest(args)
    write_manifest(args.output, manifest)
    if args.compact:
        print(json.dumps(manifest, sort_keys=True))
    else:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
