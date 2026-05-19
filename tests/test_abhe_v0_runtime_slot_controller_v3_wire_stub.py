"""
Boundary tests for v3 decision-to-proxy wire stub.

Hard contract:
  - default (no flags) -> always no_op_unauthorized
  - wire_authorized=True alone -> no_op_unauthorized
  - policy_enabled=True alone -> no_op_unauthorized
  - both False -> no_op_unauthorized
  - non-bool truthy values for either flag (e.g. 1, "true") -> no_op_unauthorized
  - both True, valid decision_class -> a descriptor with would_emit=True
    (but still no actual side effect; the action is a *descriptor*)
  - both True, unknown decision_class -> no_op_unknown_decision_class
  - the module does NOT import any provider/BFCL/scorer
  - the assert_wire_invariants_hold() self-test passes
"""
from __future__ import annotations
import ast
import importlib.util
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WIRE_STUB = REPO / "scripts/abhe_v0_runtime_slot_controller_v3_wire_stub.py"

sys.path.insert(0, str(REPO))
from scripts.abhe_v0_runtime_slot_controller_v3_wire_stub import (  # noqa: E402
    VALID_DECISION_CLASSES,
    VALID_PROXY_ACTION_KINDS,
    v3_decision_to_proxy_action,
    assert_wire_invariants_hold,
)


def test_default_call_returns_no_op_unauthorized():
    r = v3_decision_to_proxy_action({"decision": "allow_valid_tool_call"})
    assert r["wire_stub_action_kind"] == "no_op_unauthorized"
    assert r["would_emit_proxy_action"] is False
    assert r["wire_authorized_effective"] is False
    assert r["policy_enabled_effective"] is False


def test_only_wire_authorized_true_is_still_no_op():
    r = v3_decision_to_proxy_action(
        {"decision": "allow_valid_tool_call"},
        wire_authorized=True,
        policy_enabled=False,
    )
    assert r["wire_stub_action_kind"] == "no_op_unauthorized"
    assert r["would_emit_proxy_action"] is False


def test_only_policy_enabled_true_is_still_no_op():
    r = v3_decision_to_proxy_action(
        {"decision": "allow_valid_tool_call"},
        wire_authorized=False,
        policy_enabled=True,
    )
    assert r["wire_stub_action_kind"] == "no_op_unauthorized"
    assert r["would_emit_proxy_action"] is False


def test_truthy_non_bool_does_not_count_as_authorized():
    """Defense against `if x:` -> True semantics. Stub demands x is True."""
    for wa, pe in [(1, 1), ("true", "true"), ([1], [1]), ({1}, {1})]:
        r = v3_decision_to_proxy_action(
            {"decision": "allow_valid_tool_call"},
            wire_authorized=wa,
            policy_enabled=pe,
        )
        assert r["wire_stub_action_kind"] == "no_op_unauthorized", (
            f"truthy-non-bool {wa}/{pe} leaked past authorization gate"
        )
        assert r["would_emit_proxy_action"] is False


def test_both_flags_true_with_valid_decision_emits_descriptor_only():
    """Even when authorized, the function only emits a descriptor dict.
    There is no provider/BFCL/scorer call here."""
    for dc in VALID_DECISION_CLASSES:
        r = v3_decision_to_proxy_action(
            {"decision": dc},
            wire_authorized=True,
            policy_enabled=True,
        )
        assert r["wire_authorized_effective"] is True
        assert r["policy_enabled_effective"] is True
        assert r["would_emit_proxy_action"] is True
        assert r["wire_stub_action_kind"] in VALID_PROXY_ACTION_KINDS
        assert r["wire_stub_action_kind"] != "no_op_unauthorized"
        assert r["decision_class_seen"] == dc


def test_both_flags_true_unknown_decision_class_is_no_op_unknown():
    r = v3_decision_to_proxy_action(
        {"decision": "unmapped_class_for_test"},
        wire_authorized=True,
        policy_enabled=True,
    )
    assert r["wire_stub_action_kind"] == "no_op_unknown_decision_class"
    assert r["would_emit_proxy_action"] is False


def test_observed_decision_class_field_also_recognised():
    """v3 skeleton artifact uses observed_decision_class as key name."""
    r = v3_decision_to_proxy_action(
        {"observed_decision_class": "allow_valid_tool_call"},
        wire_authorized=True,
        policy_enabled=True,
    )
    assert r["wire_stub_action_kind"] == "proxy_action_pass_through"
    assert r["would_emit_proxy_action"] is True


def test_non_dict_decision_record_is_no_op():
    r = v3_decision_to_proxy_action(None, wire_authorized=True, policy_enabled=True)
    assert r["wire_stub_action_kind"] == "no_op_unknown_decision_class"
    assert r["would_emit_proxy_action"] is False


def test_decision_class_mapping_covers_all_v2_outputs():
    """Every decision class produced by runtime_slot_controller_v2 must
    have a mapping (when authorized). Otherwise wiring would silently
    no-op valid decisions."""
    expected = {
        "allow_valid_tool_call":              "proxy_action_pass_through",
        "bind_recovered_slots_then_call":     "proxy_action_substitute_bound_args",
        "call_prerequisite_lookup":           "proxy_action_invoke_prerequisite",
        "ask_or_insufficient_due_ambiguity":  "proxy_action_request_clarification",
        "ask_or_insufficient":                "proxy_action_abstain",
    }
    for dc, action_kind in expected.items():
        r = v3_decision_to_proxy_action(
            {"decision": dc},
            wire_authorized=True,
            policy_enabled=True,
        )
        assert r["wire_stub_action_kind"] == action_kind, (
            f"unexpected_mapping:{dc}->{r['wire_stub_action_kind']}_expected_{action_kind}"
        )


def test_self_test_invariants_pass():
    rep = assert_wire_invariants_hold()
    assert rep["all_unauthorized_paths_are_no_op"] is True
    assert rep["would_emit_proxy_action_seen_outside_authorized"] is False
    # 5 decision classes x 3 unauthorized flag combos = 15 paths
    assert rep["no_op_unauthorized_paths_total"] == 15
    assert rep["no_op_unauthorized_paths_no_op"] == 15


def test_module_does_not_import_provider_or_bfcl_or_scorer():
    """Static analysis of the wire stub module: assert no import of any
    provider client / BFCL runner / scorer module."""
    tree = ast.parse(WIRE_STUB.read_text(encoding="utf-8"))
    forbidden_substrings = (
        "provider_client", "rashe_source_provider_client",
        "bfcl_eval_runner", "bfcl_run_evaluation",
        "scorer", "scorer_diff", "openai", "requests", "httpx",
        "urllib", "socket",
    )
    imported_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imported_names.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            imported_names.append(node.module or "")
            for n in node.names:
                imported_names.append(node.module + "." + n.name if node.module else n.name)
    for name in imported_names:
        for f in forbidden_substrings:
            assert f not in name.lower(), (
                f"forbidden_import_in_wire_stub:{name}_contains_{f}"
            )


def test_wire_stub_imports_only_stdlib_safe_modules():
    """Only stdlib safe modules (no provider/BFCL/scorer/network).
    typing + __future__ for the module API; json + sys are used
    only inside `if __name__ == "__main__"` for the self-test report."""
    tree = ast.parse(WIRE_STUB.read_text(encoding="utf-8"))
    ALLOWED_TOP_LEVEL_MODULES = {"typing", "__future__", "json", "sys"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                top = n.name.split(".")[0]
                assert top in ALLOWED_TOP_LEVEL_MODULES, (
                    f"unexpected_import:{n.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            assert top in ALLOWED_TOP_LEVEL_MODULES, (
                f"unexpected_from_import:{node.module}"
            )


def test_wire_stub_runs_as_main_emits_passing_report():
    """Running the module as a script prints the self-test report."""
    import subprocess
    p = subprocess.run(
        [sys.executable, str(WIRE_STUB)],
        capture_output=True, text=True,
        env={"PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin"},
    )
    assert p.returncode == 0
    import json
    report = json.loads(p.stdout)
    assert report["all_unauthorized_paths_are_no_op"] is True
