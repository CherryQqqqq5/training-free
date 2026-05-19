#!/usr/bin/env python3
"""Diagnose M2.8-pre source/result availability for prior-aware scanning.

This is a read-only offline audit. It explains why dataset cases do or do not
have usable baseline source results before any scorer authorization is considered.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_m28pre_explicit_required_arg_literal import (
    DEFAULT_OUT_ROOT,
    DEFAULT_SOURCE_MANIFEST,
    _render_source_result_availability_audit,
    _source_result_availability_audit,
    _write_json,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = _source_result_availability_audit(args.source_manifest)
    args.out_root.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_root / "m28pre_source_result_availability_audit.json", report)
    (args.out_root / "m28pre_source_result_availability_audit.md").write_text(
        _render_source_result_availability_audit(report), encoding="utf-8"
    )
    if args.compact:
        print(json.dumps({
            "source_result_availability_audit_ready": report["source_result_availability_audit_ready"],
            "source_result_availability_ready": report["source_result_availability_ready"],
            "hard_issue_counts": report["hard_issue_counts"],
            "issue_counts": report["issue_counts"],
            "candidate_commands": report["candidate_commands"],
            "planned_commands": report["planned_commands"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
