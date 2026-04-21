#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _git_value(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip() or None
    except Exception:
        return None


def _git_dirty(repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def _load_config(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_upstream(config: dict[str, Any]) -> tuple[str | None, str | None]:
    upstream_cfg = config.get("upstream", {}) if isinstance(config.get("upstream"), dict) else {}
    profiles = upstream_cfg.get("profiles", {}) if isinstance(upstream_cfg.get("profiles"), dict) else {}

    profile_name = os.environ.get("GRC_UPSTREAM_PROFILE") or upstream_cfg.get("active_profile")
    resolved = dict(upstream_cfg)
    if profile_name and profile_name in profiles and isinstance(profiles[profile_name], dict):
        resolved.update(profiles[profile_name])

    upstream_model = os.environ.get("GRC_UPSTREAM_MODEL") or resolved.get("model")
    return (str(profile_name) if profile_name else None, str(upstream_model) if upstream_model else None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--kind", required=True, choices=("baseline", "candidate"))
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--runtime-config-path", required=True)
    parser.add_argument("--rules-dir", required=True)
    parser.add_argument("--bfcl-model-alias", required=True)
    parser.add_argument("--protocol-id", required=True)
    parser.add_argument("--test-category", default="")
    parser.add_argument("--rule-path")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    runtime_config_path = Path(args.runtime_config_path)
    config = _load_config(runtime_config_path)
    upstream_profile, upstream_model_route = _resolve_upstream(config)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    manifest = {
        "kind": args.kind,
        "comparison_line": "compatibility_baseline" if args.kind == "baseline" else "compiler_patch_candidate",
        "bfcl_model_alias": args.bfcl_model_alias,
        "upstream_profile": upstream_profile,
        "upstream_model_route": upstream_model_route,
        "protocol_id": args.protocol_id,
        "test_category": args.test_category,
        "git_sha": _git_value(["git", "-C", str(repo_root), "rev-parse", "HEAD"]),
        "git_dirty": _git_dirty(repo_root),
        "runtime_config_path": str(runtime_config_path),
        "rules_dir": args.rules_dir,
        "rule_path": args.rule_path or None,
        "run_id": args.run_id,
        "timestamp": timestamp,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
