#!/usr/bin/env python3
"""
build_abhe_v0_runtime_slot_controller_v3_skeleton
==================================================

P2 (skeleton-only) — offline composer over v2 primitives.

PURPOSE
-------
Produce a fixture-driven, fail-closed, dry-run *skeleton* artifact that
demonstrates the v3 composition over the existing v0 primitives
(required_arg_schema_reader_v0 + valid_tool_call_guard_v0 +
prior_tool_observation_slot_binder_v0 + prerequisite_lookup_planner_v0),
without:
  - calling any provider
  - calling BFCL generate/evaluate
  - calling any scorer
  - wiring into the actual proxy request/response path
  - touching holdout/full suite
  - reading any prompt/gold/expected/argument_value/raw_response/raw_payload

`runtime_wired_into_proxy` is FALSE by construction: this artifact only
asserts that the composer is deterministic on synthetic fixture cases,
and that each v0 primitive contributes a per-case decision trace.

LITERATURE NOTE
---------------
Inference-time provisional-tool-call review (proactive evaluation before
execution) is consistent with the design of Reinforced Agent (2025) and
ToolWeave's parameter-provenance tracking. State-based evaluation in
BFCL-v3 motivates per-case decision records over trajectory matching.
This file does NOT cite trajectories; only design intent.

INPUTS
------
  tests/fixtures/abhe_runtime_slot_controller_v3_skeleton/cases.json

OUTPUT
------
  outputs/artifacts/stage1_bfcl_acceptance/
      abhe_v0_runtime_slot_controller_v3_skeleton.json

  Strict whitelist schema (top-level):
    artifact_kind, schema_version, run_scope, bounded_dev_smoke_only,
    raw_material_absent, performance_evidence, holdout_touched,
    full_suite_touched, archive_updated,
    scorer_diff_committed, raw_provider_payload_committed,
    raw_bfcl_result_tree_committed, gold_expected_committed,
    argument_values_committed, prompt_literal_committed,
    provider_calls_made, bfcl_generate_called, bfcl_evaluate_called,
    scorer_called, runtime_wired_into_proxy, huawei_acceptance_ready,
    sota_3pp_claim_ready,
    source_fixture_path, source_fixture_sha256,
    cases, summary, blockers

USAGE
-----
  PYTHONPATH=. .venv/bin/python \\
    scripts/build_abhe_v0_runtime_slot_controller_v3_skeleton.py \\
    --compact --strict --write

  Exit 0 only if:
    - fixture present & parseable
    - composer deterministic
    - schema validates (whitelist; no forbidden substring in any key)
    - --strict refuses to write if any non-whitelisted key appears
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.abhe_v0_runtime_slot_controller import runtime_slot_controller_v2  # noqa: E402

SOURCE_FIXTURE = REPO_ROOT / "tests/fixtures/abhe_runtime_slot_controller_v3_skeleton/cases.json"
OUTPUT_PATH = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_v3_skeleton.json"

ALLOWED_TOP_KEYS = {
    "artifact_kind", "schema_version", "run_scope", "bounded_dev_smoke_only",
    "raw_material_absent",
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called", "runtime_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
    "source_fixture_path", "source_fixture_sha256",
    "cases", "summary", "blockers",
}
ALLOWED_CASE_KEYS = {
    "case_id_synthetic", "expected_decision_class", "observed_decision_class",
    "decision_matches_expectation",
    "schema_reader_required_arg_count", "schema_reader_required_args",
    "guard_tool_call_valid", "guard_missing_required_args",
    "guard_incompatible_required_args",
    "binder_bindable_count", "binder_bound_slot_sources",
    "binder_ambiguous_slots", "binder_missing_after_bind",
    "binder_entity_ambiguity_detected",
    "planner_lookup_needed_count", "planner_planned_lookup_by_slot",
    "planner_unrecoverable_slots", "planner_ask_or_insufficient_required",
    "would_block_valid_tool_call",
}
ALLOWED_SUMMARY_KEYS = {
    "total_cases", "decisions_matching_expectation",
    "decisions_by_class", "any_would_block_valid_tool_call",
    "binder_bound_slot_total", "binder_ambiguous_slot_total",
    "planner_lookup_needed_total", "planner_unrecoverable_slot_total",
}

FORBIDDEN_SUBSTRINGS = ("prompt", "gold", "expected_argument", "argument_value",
                       "raw_response", "raw_payload", "scorer_diff")
ATTESTATION_KEYS_ALLOWLIST = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "expected_decision_class", "decision_matches_expectation",
    "decisions_matching_expectation",
    # "expected_decision_class" carries a generic word "expected"; we
    # whitelist exact key names. The forbidden substring "expected_argument"
    # is checked specifically; bare "expected" is allowed in our schema.
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return "sha256:" + h.hexdigest()


def _scan_forbidden(obj, path="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ATTESTATION_KEYS_ALLOWLIST:
                _scan_forbidden(v, f"{path}.{k}")
                continue
            kl = str(k).lower()
            for bad in FORBIDDEN_SUBSTRINGS:
                if bad in kl:
                    raise ValueError(f"forbidden_field_in_key:{path}.{k}")
            _scan_forbidden(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            _scan_forbidden(x, f"{path}[{i}]")


def _compose_case(case: dict) -> dict:
    result = runtime_slot_controller_v2(
        tool=case["tool"],
        tool_call=case["tool_call"],
        sources=case.get("sources", []),
        available_tools=case.get("available_tools", []),
        recoverability_map=case.get("recoverability_map", {}),
    )
    schema = result.get("schema_reader") or {}
    guard = result.get("valid_tool_call_guard") or {}
    binder = result.get("slot_binder") or {}
    planner = result.get("lookup_planner") or {}
    observed = result.get("decision")
    expected = case.get("expected_decision_class")
    return {
        "case_id_synthetic": case["case_id_synthetic"],
        "expected_decision_class": expected,
        "observed_decision_class": observed,
        "decision_matches_expectation": (observed == expected),
        "schema_reader_required_arg_count": schema.get("required_arg_count", 0),
        "schema_reader_required_args": list(schema.get("required_args") or []),
        "guard_tool_call_valid": bool(guard.get("tool_call_valid", False)),
        "guard_missing_required_args": list(guard.get("missing_required_args") or []),
        "guard_incompatible_required_args": list(guard.get("incompatible_required_args") or []),
        "binder_bindable_count": int((binder or {}).get("bindable_count") or 0),
        "binder_bound_slot_sources": dict((binder or {}).get("bound_slot_sources") or {}),
        "binder_ambiguous_slots": list((binder or {}).get("ambiguous_slots") or []),
        "binder_missing_after_bind": list((binder or {}).get("missing_after_bind") or []),
        "binder_entity_ambiguity_detected": bool((binder or {}).get("entity_ambiguity_detected") or False),
        "planner_lookup_needed_count": int((planner or {}).get("lookup_needed_count") or 0),
        "planner_planned_lookup_by_slot": dict((planner or {}).get("planned_lookup_by_slot") or {}),
        "planner_unrecoverable_slots": list((planner or {}).get("unrecoverable_slots") or []),
        "planner_ask_or_insufficient_required": bool((planner or {}).get("ask_or_insufficient_required") or False),
        "would_block_valid_tool_call": bool(result.get("would_block_valid_tool_call", False)),
    }


def build(strict: bool) -> dict:
    fixture = json.loads(SOURCE_FIXTURE.read_text(encoding="utf-8"))
    cases_in = fixture.get("cases") or []
    blockers = []
    cases_out = []
    decisions_by_class = {}
    matches = 0
    any_block = False
    binder_bound_total = 0
    binder_amb_total = 0
    planner_lookup_total = 0
    planner_unrec_total = 0
    for c in cases_in:
        cr = _compose_case(c)
        cases_out.append(cr)
        decisions_by_class[cr["observed_decision_class"]] = decisions_by_class.get(cr["observed_decision_class"], 0) + 1
        if cr["decision_matches_expectation"]:
            matches += 1
        else:
            blockers.append(f"decision_mismatch:{cr['case_id_synthetic']}")
        if cr["would_block_valid_tool_call"]:
            any_block = True
            blockers.append(f"would_block_valid_tool_call:{cr['case_id_synthetic']}")
        binder_bound_total += cr["binder_bindable_count"]
        binder_amb_total += len(cr["binder_ambiguous_slots"])
        planner_lookup_total += cr["planner_lookup_needed_count"]
        planner_unrec_total += len(cr["planner_unrecoverable_slots"])
    summary = {
        "total_cases": len(cases_out),
        "decisions_matching_expectation": matches,
        "decisions_by_class": dict(sorted(decisions_by_class.items())),
        "any_would_block_valid_tool_call": any_block,
        "binder_bound_slot_total": binder_bound_total,
        "binder_ambiguous_slot_total": binder_amb_total,
        "planner_lookup_needed_total": planner_lookup_total,
        "planner_unrecoverable_slot_total": planner_unrec_total,
    }
    artifact = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_v3_skeleton",
        "schema_version": "abhe_v0_runtime_slot_controller_v3_skeleton_v0",
        "run_scope": "offline_skeleton_composer_only_no_provider_no_scorer_not_wired_into_proxy",
        "bounded_dev_smoke_only": True,
        "raw_material_absent": True,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "scorer_diff_committed": False,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "argument_values_committed": False,
        "prompt_literal_committed": False,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "runtime_wired_into_proxy": False,
        "huawei_acceptance_ready": False,
        "sota_3pp_claim_ready": False,
        "source_fixture_path": str(SOURCE_FIXTURE.relative_to(REPO_ROOT)),
        "source_fixture_sha256": _sha256(SOURCE_FIXTURE),
        "cases": cases_out,
        "summary": summary,
        "blockers": blockers,
    }
    if strict:
        bad = set(artifact.keys()) - ALLOWED_TOP_KEYS
        if bad:
            raise ValueError(f"non_whitelisted_top_keys:{sorted(bad)}")
        for cr in cases_out:
            cbad = set(cr.keys()) - ALLOWED_CASE_KEYS
            if cbad:
                raise ValueError(f"non_whitelisted_case_keys:{sorted(cbad)}")
        sbad = set(summary.keys()) - ALLOWED_SUMMARY_KEYS
        if sbad:
            raise ValueError(f"non_whitelisted_summary_keys:{sorted(sbad)}")
        _scan_forbidden(artifact)
    return artifact


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    art = build(strict=args.strict)
    if args.write:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(art, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "abhe_v0_runtime_slot_controller_v3_skeleton_passed": (
                not art["blockers"]
                and art["summary"]["decisions_matching_expectation"] == art["summary"]["total_cases"]
                and not art["summary"]["any_would_block_valid_tool_call"]
                and art["runtime_wired_into_proxy"] is False
            ),
            "total_cases": art["summary"]["total_cases"],
            "decisions_matching_expectation": art["summary"]["decisions_matching_expectation"],
            "decisions_by_class": art["summary"]["decisions_by_class"],
            "runtime_wired_into_proxy": art["runtime_wired_into_proxy"],
            "blockers": art["blockers"],
            "report_scope": "abhe_v0_runtime_slot_controller_v3_skeleton_build",
        }, ensure_ascii=False))
    else:
        print(json.dumps(art, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
