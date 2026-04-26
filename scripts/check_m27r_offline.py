#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_HOLDOUT_ROOT = Path("outputs/artifacts/bfcl_ctspc_holdout30_v1")
DEFAULT_OUTPUT = DEFAULT_ROOT / "m27r_offline_summary.json"
DEFAULT_MD = DEFAULT_ROOT / "m27r_offline_summary.md"


def _read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evaluate_m27r_offline(root: Path = DEFAULT_ROOT, holdout_root: Path = DEFAULT_HOLDOUT_ROOT) -> dict[str, Any]:
    dev = _read_json(root / "m27r_dev_subset_protocol.json", default={})
    retention = _read_json(root / "m27r_rule_retention.json", default={})
    not_activated = _read_json(root / "m27r_not_activated_audit.json", default={})
    arg = _read_json(root / "m27r_arg_realization.json", default={})
    holdout = _read_json(holdout_root / "holdout_manifest.json", default={})
    checks = {
        "m27r_dev_subset_protocol_ready": bool(dev.get("m27r_dev_subset_protocol_ready")),
        "m27r_rule_retention_ready": bool(retention.get("m27r_rule_retention_ready")),
        "m27r_not_activated_audit_ready": bool(not_activated.get("m27r_not_activated_audit_ready")),
        "m27r_arg_realization_audit_ready": bool(arg.get("m27r_arg_realization_audit_ready")),
        "m27r_holdout_manifest_ready": bool(holdout.get("m27r_holdout_manifest_ready")),
    }
    report = {
        "report_scope": "m2_7r_offline_summary",
        "artifact_root": str(root),
        "holdout_root": str(holdout_root),
        **checks,
        "m2_7r_offline_passed": all(checks.values()),
        "rule_decision_distribution": retention.get("decision_distribution"),
        "not_activated_classification_distribution": not_activated.get("classification_distribution"),
        "arg_realization_failure_reason_distribution": arg.get("failure_reason_distribution"),
        "holdout_selected_case_count": holdout.get("selected_case_count"),
        "holdout_overlap_with_dev_case_ids": holdout.get("overlap_with_dev_case_ids"),
        "diagnostic": {
            "offline_readiness_only": True,
            "bfcl_performance_evidence": False,
            "no_bfcl_rerun": True,
            "no_100_case": True,
            "no_m2_8": True,
            "no_full_bfcl": True,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7r Offline Summary",
        "",
        f"- Passed: `{report.get('m2_7r_offline_passed')}`",
        "",
        "| Check | Passed |",
        "| --- | ---: |",
    ]
    for key in [
        "m27r_dev_subset_protocol_ready",
        "m27r_rule_retention_ready",
        "m27r_not_activated_audit_ready",
        "m27r_arg_realization_audit_ready",
        "m27r_holdout_manifest_ready",
    ]:
        lines.append(f"| `{key}` | `{report.get(key)}` |")
    lines.extend([
        "",
        "## Diagnostics",
        "",
        f"- Rule decisions: `{report.get('rule_decision_distribution')}`",
        f"- Not-activated classifications: `{report.get('not_activated_classification_distribution')}`",
        f"- Arg realization reasons: `{report.get('arg_realization_failure_reason_distribution')}`",
        f"- Holdout selected cases: `{report.get('holdout_selected_case_count')}`",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check M2.7r offline diagnostics and protocol readiness.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--holdout-root", type=Path, default=DEFAULT_HOLDOUT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_m27r_offline(args.root, args.holdout_root)
    _write_json(args.output, report)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "m2_7r_offline_passed": report.get("m2_7r_offline_passed"),
            "m27r_dev_subset_protocol_ready": report.get("m27r_dev_subset_protocol_ready"),
            "m27r_rule_retention_ready": report.get("m27r_rule_retention_ready"),
            "m27r_not_activated_audit_ready": report.get("m27r_not_activated_audit_ready"),
            "m27r_arg_realization_audit_ready": report.get("m27r_arg_realization_audit_ready"),
            "m27r_holdout_manifest_ready": report.get("m27r_holdout_manifest_ready"),
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
