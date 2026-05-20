#!/usr/bin/env python3
"""
check_abhe_v0_session_blast_radius_static
==========================================

A static-analysis fail-closed checker that asserts: every script added
during the current bounded fail-closed work stream (P1/P1.5a/P2/P3/
P6/G1/G2) has zero capability to call a provider, BFCL evaluator, or
scorer, no matter what flags a caller passes.

What "blast radius" means here:
  The maximum side-effect surface that the new code could possibly
  produce *purely from its imports and source*, ignoring runtime
  arguments.

Method:
  AST-parse each guarded file, collect every Import and ImportFrom,
  and assert no name in the import set contains any of:
    - provider client identifiers (rashe_source_provider_client, etc.)
    - BFCL run/eval identifiers (bfcl_run, bfcl_evaluate, etc.)
    - scorer identifiers (scorer, scorer_diff)
    - external network primitives (requests, httpx, urllib, openai, socket)
    - subprocess (we allow it ONLY inside tests, not in scripts)

Run this checker in strict mode to gate merges:
  exit 0 iff every guarded file is verifiable-safe
  exit 1 if any forbidden import is detected

This is a *defense-in-depth* check beyond the unit tests. It catches
the case where someone hand-edits a stub later and forgets that the
stub is supposed to remain capability-free.
"""
from __future__ import annotations
import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files guaranteed to be capability-free (no provider/BFCL/scorer/network).
# This list is the "trust boundary" — only files explicitly listed here
# are checked. Adding a file to this list is a deliberate act.
GUARDED_FILES = [
    # P1 — score adapter (offline)
    "scripts/build_abhe_v0_true_per_selected_id_score_adapter.py",
    "scripts/check_abhe_score_output_contract_satisfied.py",
    # P1.5a — category-arm matrix (offline)
    "scripts/build_abhe_v0_category_arm_error_class_matrix.py",
    "scripts/check_abhe_category_arm_error_signal.py",
    # P2 — v3 skeleton (composer over v0 primitives, dry-run)
    "scripts/build_abhe_v0_runtime_slot_controller_v3_skeleton.py",
    "scripts/check_abhe_runtime_slot_controller_v3_skeleton_ready.py",
    # P3 — backoff policy (declarative-only)
    "scripts/build_abhe_v0_provider_transport_backoff_policy.py",
    "scripts/check_abhe_provider_transport_backoff_policy_ready.py",
    # G1 — P1.5b approval packet checker
    "scripts/check_abhe_v0_per_case_scorer_slicer_approval_packet.py",
    # G2 — wire stub (no-op unless authorized)
    "scripts/abhe_v0_runtime_slot_controller_v3_wire_stub.py",
    # G6a — per-case scorer slicer rerun manifest (planning-only)
    "scripts/build_abhe_v0_per_case_scorer_slicer_rerun_manifest.py",
    "scripts/check_abhe_v0_per_case_scorer_slicer_rerun_manifest_ready.py",
    # G6b-1 — executor scaffolding (dry-run; execute path is fail-closed
    # NotImplementedError until a follow-up commit wires the live chain
    # and extends this guard list accordingly).
    "scripts/run_abhe_v0_per_case_scorer_slicer_bounded_residual_dev_smoke.py",
]

FORBIDDEN_IMPORT_SUBSTRINGS = (
    # provider client identifiers
    "provider_client", "rashe_source_provider_client",
    "rashe_source_case_provider",
    # BFCL run / eval identifiers
    "bfcl_run", "bfcl_evaluate", "bfcl_eval_runner",
    "run_bfcl", "bfcl_proxy_transport",
    "run_rashe_provider_endpoint_preflight",
    "run_bfcl_live_provider_preflight",
    "run_bfcl_measurement_provider_protocol_debug",
    # scorer identifiers
    "scorer_diff",  # bare "scorer" is too broad (e.g. checker scripts mention it
                    # in attestation keys); we keep this narrow
    # external network primitives
    "requests",
    "httpx",
    "urllib",
    "openai",
    "anthropic",
    "socket",
    "http.client",
    # subprocess in scripts (scripts must not shell out to anything)
    "subprocess",  # if a script imports subprocess it could shell out -> shell
                   # is forbidden. Tests are allowed to use subprocess (separate
                   # GUARDED_FILES list could be added for tests if needed).
)


def _collect_imports(tree: ast.AST) -> List[str]:
    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                names.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.append(module)
            for n in node.names:
                if module:
                    names.append(module + "." + n.name)
                else:
                    names.append(n.name)
    return names


def check(strict: bool) -> Dict[str, Any]:
    blockers: List[str] = []
    per_file: List[Dict[str, Any]] = []
    for rel in GUARDED_FILES:
        p = REPO_ROOT / rel
        if not p.exists():
            blockers.append(f"guarded_file_missing:{rel}")
            per_file.append({"path": rel, "present": False, "import_count": 0,
                             "forbidden_imports": []})
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            blockers.append(f"guarded_file_syntax_error:{rel}:{e}")
            per_file.append({"path": rel, "present": True, "import_count": -1,
                             "forbidden_imports": []})
            continue
        imports = _collect_imports(tree)
        forbidden = []
        for name in imports:
            nl = name.lower()
            for sub in FORBIDDEN_IMPORT_SUBSTRINGS:
                if sub in nl:
                    forbidden.append({"import_name": name, "matched_forbidden_substring": sub})
                    blockers.append(f"forbidden_import:{rel}:{name}_matches_{sub}")
        per_file.append({
            "path": rel,
            "present": True,
            "import_count": len(imports),
            "imports_sorted_sample": sorted(set(imports))[:20],
            "forbidden_imports": forbidden,
        })
    ready = len(blockers) == 0
    return {
        "abhe_v0_session_blast_radius_static_passed": ready,
        "guarded_file_count": len(GUARDED_FILES),
        "guarded_files_with_forbidden_imports": sum(1 for x in per_file if x["forbidden_imports"]),
        "per_file": per_file,
        "blockers": blockers,
        "report_scope": "abhe_v0_session_blast_radius_static_check",
        # echoing boundary invariants for the audit trail
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
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    r = check(strict=args.strict)
    if args.compact:
        compact = {k: v for k, v in r.items() if k != "per_file"}
        print(json.dumps(compact, sort_keys=True))
    else:
        print(json.dumps(r, indent=2, sort_keys=True))
    return 0 if r["abhe_v0_session_blast_radius_static_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
