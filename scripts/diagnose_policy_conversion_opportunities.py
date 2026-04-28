#!/usr/bin/env python3
"""Audit theory-prior policy conversion opportunities from existing traces.

This is an offline-only diagnostic for postcondition-guided trajectory policy.
It does not execute BFCL/model/scorer and does not authorize runtime changes.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

DEFAULT_TRACE_ROOT = Path("outputs/phase2_validation/required_next_tool_choice_v1")
DEFAULT_OUT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/policy_conversion_opportunity_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/policy_conversion_opportunity_audit.md")

NO_TOOL_POLICY_LABELS = {
    "(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)",
    "(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)",
    "(POST_TOOL,POST_TOOL_PROSE_SUMMARY)",
    "(POST_TOOL,TERMINATION_INADMISSIBLE)",
}

WITNESS_KEY_ALIASES: dict[str, set[str]] = {
    "file_exists": {"file_exists", "exists", "created", "path"},
    "file_content": {"file_content", "content", "last_lines", "sorted_content"},
    "file_content_changed": {"file_content", "content", "written", "updated", "sorted_content"},
    "matching_results": {"matching_results", "matches", "matching_lines", "results", "files", "paths"},
    "comparison_result": {"comparison_result", "diff", "diff_lines", "differences"},
    "target_path_changed": {"target_path_changed", "destination", "target", "path"},
    "current_working_directory": {"current_working_directory", "cwd"},
    "memory_records": {"memory_records", "records", "memories"},
    "search_results": {"search_results", "results"},
}


CAPABILITY_RULES: list[tuple[str, list[str], list[str], list[str]]] = [
    ("create_file", ["create", "new file", "set up a new file", "produce a file"], ["touch"], ["file_exists"]),
    ("write_content", ["write", "append", "add content", "put", "save"], ["echo"], ["file_content_changed"]),
    ("read_content", ["read", "show", "display", "view", "contents of"], ["cat"], ["file_content"]),
    ("search_or_find", ["search", "find", "locate", "look for"], ["grep", "find"], ["matching_results"]),
    ("compare", ["compare", "diff", "difference"], ["diff"], ["comparison_result"]),
    ("copy", ["copy", "duplicate"], ["cp"], ["target_path_changed"]),
    ("move_or_rename", ["move", "rename", "relocate"], ["mv"], ["target_path_changed"]),
    ("directory_navigation", ["folder", "directory", "cd", "navigate", "go to"], ["cd"], ["current_working_directory"]),
    ("memory_recall", ["remember", "recall", "preference", "previous", "stored"], ["memory_search", "memory_retrieve", "search_memory"], ["memory_records"]),
    ("web_evidence", ["latest", "current", "today", "web", "online", "news"], ["web_search", "search"], ["search_results"]),
]


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _walk(obj: Any) -> Iterable[Any]:
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def _trace_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.json") if "/traces/" in str(path).replace("\\", "/"))


def _request(payload: dict[str, Any]) -> dict[str, Any]:
    req = payload.get("request_original") if isinstance(payload.get("request_original"), dict) else None
    if req is None:
        req = payload.get("request") if isinstance(payload.get("request"), dict) else None
    return req or {}


def _validation(payload: dict[str, Any]) -> dict[str, Any]:
    val = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    return val


def _available_tools(request: dict[str, Any]) -> list[str]:
    tools: list[str] = []
    for item in request.get("tools") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name and isinstance(item.get("function"), dict):
            name = item["function"].get("name")
        if isinstance(name, str) and name:
            tools.append(name)
    return sorted(dict.fromkeys(tools))


def _input_messages(request: dict[str, Any]) -> list[dict[str, Any]]:
    raw = request.get("input") or request.get("messages") or []
    return [msg for msg in raw if isinstance(msg, dict)]


def _user_text(request: dict[str, Any]) -> str:
    chunks: list[str] = []
    for msg in _input_messages(request):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            chunks.append(msg["content"])
    return "\n".join(chunks)


def _prior_tool_output_present(request: dict[str, Any]) -> bool:
    for msg in _input_messages(request):
        if msg.get("type") in {"function_call_output", "tool_result"}:
            return True
        if msg.get("role") == "tool":
            return True
    return False


def _safe_word_match(text: str, cues: list[str]) -> str | None:
    lowered = text.lower()
    for cue in cues:
        if re.search(r"(?<![a-z0-9_])" + re.escape(cue.lower()) + r"(?![a-z0-9_])", lowered):
            return cue
    return None


def _infer_capability(user_text: str, available_tools: list[str]) -> tuple[str | None, list[str], list[str], str | None]:
    tool_set = set(available_tools)
    for capability, cues, tools, witnesses in CAPABILITY_RULES:
        cue = _safe_word_match(user_text, cues)
        if cue is None:
            continue
        matched = [tool for tool in tools if tool in tool_set]
        if matched:
            return capability, matched, witnesses, cue
    return None, [], [], None



def _load_json_from_text(text: str) -> Any | None:
    try:
        return json.loads(text)
    except Exception:
        return None


def _tool_output_payloads(request: dict[str, Any]) -> list[Any]:
    payloads: list[Any] = []
    for msg in _input_messages(request):
        if msg.get("type") not in {"function_call_output", "tool_result"} and msg.get("role") != "tool":
            continue
        raw = msg.get("output", msg.get("content"))
        if isinstance(raw, str):
            parsed = _load_json_from_text(raw)
            payloads.append(parsed if parsed is not None else raw)
        elif raw is not None:
            payloads.append(raw)
    return payloads


def _flatten_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.add(str(key))
            keys.update(_flatten_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            keys.update(_flatten_keys(item))
    return keys


def _postcondition_already_satisfied(
    request: dict[str, Any],
    witnesses: list[str],
    *,
    capability: str | None = None,
    user_text: str = "",
) -> tuple[bool, list[str]]:
    if not witnesses:
        return False, []
    aliases: set[str] = set()
    for witness in witnesses:
        aliases.update(WITNESS_KEY_ALIASES.get(witness, {witness}))
    matched: set[str] = set()
    for payload in _tool_output_payloads(request):
        keys = _flatten_keys(payload)
        matched.update(key for key in keys if key in aliases)
        if (
            capability == "read_content"
            and "current_directory_content" in keys
            and "list" in user_text.lower()
            and any(token in user_text.lower() for token in ["file", "files", "directory", "folder"])
        ):
            matched.add("current_directory_content")
    return bool(matched), sorted(matched)


def _record_from_trace(path: Path, root: Path) -> dict[str, Any] | None:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        return None
    req = _request(payload)
    val = _validation(payload)
    labels = [str(item) for item in val.get("failure_labels") or []]
    predicates = [str(item) for item in val.get("request_predicates") or []]
    rule_hits = [str(item) for item in val.get("rule_hits") or []]
    policy_hits = [str(item) for item in val.get("policy_hits") or []]
    request_patches = [str(item) for item in val.get("request_patches") or []]
    available = _available_tools(req)
    text = _user_text(req)
    policy_failure = bool(set(labels) & NO_TOOL_POLICY_LABELS)
    capability, recommended, witnesses, cue = _infer_capability(text, available)
    postcondition_satisfied, satisfied_witness_keys = _postcondition_already_satisfied(
        req,
        witnesses,
        capability=capability,
        user_text=text,
    )
    rejection_reason = None
    if not policy_failure:
        rejection_reason = "not_no_tool_policy_failure"
    elif not available:
        rejection_reason = "no_tools_available"
    elif not ("prior_tool_outputs_present" in predicates or _prior_tool_output_present(req)):
        rejection_reason = "no_prior_observation_for_postcondition_policy"
    elif not rule_hits:
        rejection_reason = "no_rule_hit"
    elif not recommended:
        rejection_reason = "no_schema_local_recommended_tool"
    elif postcondition_satisfied:
        rejection_reason = "postcondition_already_satisfied"
    candidate_ready = rejection_reason is None
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    return {
        "trace_path": str(path),
        "trace_relative_path": rel,
        "trace_id": path.stem,
        "run_name": rel.split("/", 1)[0] if "/" in rel else None,
        "failure_labels": labels,
        "request_predicates": predicates,
        "rule_hits": rule_hits,
        "policy_hits": policy_hits,
        "request_patch_count": len(request_patches),
        "available_tools": available,
        "user_text_excerpt": text[:240],
        "postcondition_gap": capability,
        "disambiguation_cue": cue,
        "recommended_tools": recommended,
        "expected_observation_keys": witnesses,
        "policy_family": "postcondition_guided_trajectory_policy" if candidate_ready else None,
        "theory_class": "postcondition_guided_trajectory_progress" if candidate_ready else None,
        "intervention_strength": "guidance_only" if candidate_ready else None,
        "exact_tool_choice": False,
        "precondition_observable": bool(candidate_ready),
        "postcondition_witness_available": bool(candidate_ready and witnesses),
        "postcondition_already_satisfied": postcondition_satisfied,
        "satisfied_witness_keys": satisfied_witness_keys,
        "target_or_scorer_field_dependency": False,
        "candidate_ready": candidate_ready,
        "rejection_reason": rejection_reason,
    }


def evaluate(trace_root: Path = DEFAULT_TRACE_ROOT) -> dict[str, Any]:
    records = [row for path in _trace_files(trace_root) if (row := _record_from_trace(path, trace_root)) is not None]
    candidates = [row for row in records if row.get("candidate_ready")]
    candidate_tools = sum((row.get("recommended_tools") or [] for row in candidates), [])
    rejection_counts = Counter(str(row.get("rejection_reason") or "candidate_ready") for row in records)
    run_counts = Counter(str(row.get("run_name") or "unknown") for row in records)
    capability_counts = Counter(str(row.get("postcondition_gap") or "unknown") for row in candidates)
    ready = bool(records)
    return {
        "report_scope": "policy_conversion_opportunity_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "trace_root": str(trace_root),
        "policy_conversion_opportunity_audit_ready": ready,
        "trace_count": len(records),
        "rule_hit_trace_count": sum(1 for row in records if row.get("rule_hits")),
        "no_tool_policy_failure_count": sum(1 for row in records if set(row.get("failure_labels") or []) & NO_TOOL_POLICY_LABELS),
        "policy_candidate_count": len(candidates),
        "recommended_tools_count": len(candidate_tools),
        "candidate_runs": dict(sorted(Counter(str(row.get("run_name") or "unknown") for row in candidates).items())),
        "candidate_capability_distribution": dict(sorted(capability_counts.items())),
        "recommended_tool_distribution": dict(sorted(Counter(candidate_tools).items())),
        "rejection_reason_counts": dict(sorted(rejection_counts.items())),
        "candidate_records": candidates,
        "sample_candidates": candidates[:20],
        "sample_rejections": [row for row in records if not row.get("candidate_ready")][:20],
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "review_policy_family_before_runtime_integration" if candidates else "inspect_policy_artifact_generation",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Policy Conversion Opportunity Audit",
        "",
        f"- Ready: `{report['policy_conversion_opportunity_audit_ready']}`",
        f"- Trace count: `{report['trace_count']}`",
        f"- Rule-hit traces: `{report['rule_hit_trace_count']}`",
        f"- No-tool policy failure traces: `{report['no_tool_policy_failure_count']}`",
        f"- Policy candidate count: `{report['policy_candidate_count']}`",
        f"- Recommended tools count: `{report['recommended_tools_count']}`",
        f"- Candidate capability distribution: `{report['candidate_capability_distribution']}`",
        f"- Recommended tool distribution: `{report['recommended_tool_distribution']}`",
        f"- Rejection reason counts: `{report['rejection_reason_counts']}`",
        "",
        "Offline audit only. This artifact does not authorize BFCL/model/scorer runs.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.trace_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "policy_conversion_opportunity_audit_ready",
            "trace_count",
            "rule_hit_trace_count",
            "no_tool_policy_failure_count",
            "policy_candidate_count",
            "recommended_tools_count",
            "candidate_capability_distribution",
            "recommended_tool_distribution",
            "rejection_reason_counts",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
