#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from grc.runtime.engine import RuleEngine  # noqa: E402
from scripts.check_m27i_guard_preflight import DEFAULT_ARTIFACT_ROOT, evaluate_guard_preflight  # noqa: E402

DEFAULT_ROOT = DEFAULT_ARTIFACT_ROOT
OUT = DEFAULT_ROOT / "m27v_arg_realization.json"
MD = DEFAULT_ROOT / "m27v_arg_realization.md"


def _j(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _serializable(value: Any) -> bool:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        return True
    except TypeError:
        return False


def _canonical_map(candidate: dict[str, Any]) -> dict[str, Any]:
    cmap = candidate.get("canonical_arg_map") if isinstance(candidate.get("canonical_arg_map"), dict) else {}
    if cmap:
        return cmap
    args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
    return {str(key): {"schema_arg_name": str(key), "alias_group": "inferred", "normalization_type": "path_basename" if any(tok in str(key).lower() for tok in ("file", "path", "dir", "source", "dest")) else "string_exact"} for key in args}


def _candidate_case(candidate: dict[str, Any], case_id: str) -> dict[str, Any]:
    args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
    cmap = _canonical_map(candidate)
    validation = RuleEngine._validate_action_candidate_args_normalized({**candidate, "canonical_arg_map": cmap}, dict(args))
    required_pair_complete = RuleEngine._candidate_required_pair_complete(candidate)
    serializable = _serializable(args)
    canonical_covered = bool(cmap) or not args
    value_ready = serializable and required_pair_complete and canonical_covered
    return {
        "case_id": case_id,
        "selected_tool": candidate.get("tool"),
        "candidate_arg_json": args,
        "emitted_arg_json": None,
        "canonical_arg_map": cmap,
        "candidate_args_serializable": serializable,
        "required_pair_complete": required_pair_complete,
        "canonical_arg_validation": validation,
        "key_mismatch": any(row.get("key_mismatch") for row in validation.values()),
        "alias_match": any(row.get("alias_match") for row in validation.values()),
        "value_mismatch": any(row.get("value_mismatch") for row in validation.values()),
        "path_normalized_match": any(row.get("path_normalized_match") for row in validation.values()),
        "arg_realization_proxy_ready": value_ready,
        "failure_reason": None if value_ready else "candidate_arg_guidance_not_ready",
    }


def evaluate(root: Path = DEFAULT_ROOT, *, refresh_replay: bool = True) -> dict[str, Any]:
    replay = evaluate_guard_preflight(artifact_root=root) if refresh_replay else _j(root / "m27i_guard_preflight.json", {})
    cases: list[dict[str, Any]] = []
    for row in replay.get("cases") or []:
        plan = row.get("after_guard_plan") if isinstance(row.get("after_guard_plan"), dict) else {}
        if not plan.get("activated"):
            continue
        candidate = plan.get("selected_action_candidate") if isinstance(plan.get("selected_action_candidate"), dict) else {}
        if not candidate:
            cases.append({"case_id": row.get("case_id"), "arg_realization_proxy_ready": False, "failure_reason": "missing_selected_action_candidate"})
            continue
        cases.append(_candidate_case(candidate, str(row.get("case_id") or "")))
    total = len(cases)
    ready = sum(1 for case in cases if case.get("arg_realization_proxy_ready"))
    serializable = sum(1 for case in cases if case.get("candidate_args_serializable"))
    canonical = sum(1 for case in cases if case.get("canonical_arg_map") is not None)
    emitted_proxy_wrong = sum(1 for case in cases if not case.get("arg_realization_proxy_ready"))
    scorer_summary = _j(root / "subset_summary.json", {}) or {}
    scorer_arg = _j(root / "m27r_arg_realization.json", {}) or {}
    report = {
        "report_scope": "m2_7v_arg_realization",
        "artifact_root": str(root),
        "raw_arg_match_rate_proxy": ready / total if total else 0.0,
        "emitted_arg_wrong_or_guidance_not_followed_count": emitted_proxy_wrong,
        "candidate_args_serializable_rate": serializable / total if total else 1.0,
        "canonical_arg_validation_coverage": canonical / total if total else 1.0,
        "cases": cases,
        "last_scorer_raw_arg_match_rate": scorer_summary.get("raw_normalized_arg_match_rate_among_activated"),
        "last_scorer_arg_failure_reason_distribution": scorer_arg.get("failure_reason_distribution"),
        "m27v_arg_realization_passed": (ready / total if total else 0.0) >= 0.6 and emitted_proxy_wrong <= 1 and serializable == total and canonical == total,
        "diagnostic": {
            "offline_only": True,
            "readiness_source": "source_trace_replay_current_rules",
            "guidance_only": True,
            "last_scorer_metrics_retained_for_postmortem_only": True,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# M2.7v Arg Realization",
            "",
            f"- Passed: `{report['m27v_arg_realization_passed']}`",
            f"- Raw arg match proxy: `{report['raw_arg_match_rate_proxy']}`",
            f"- Emitted/guidance proxy wrong count: `{report['emitted_arg_wrong_or_guidance_not_followed_count']}`",
            f"- Canonical coverage: `{report['canonical_arg_validation_coverage']}`",
            "",
            "This is an offline guidance-readiness proxy. Last scorer arg metrics are retained for postmortem only.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--no-refresh-replay", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root, refresh_replay=not args.no_refresh_replay)
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({k: report.get(k) for k in ["raw_arg_match_rate_proxy", "emitted_arg_wrong_or_guidance_not_followed_count", "candidate_args_serializable_rate", "canonical_arg_validation_coverage", "m27v_arg_realization_passed"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
