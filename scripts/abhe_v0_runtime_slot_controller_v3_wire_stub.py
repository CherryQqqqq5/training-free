#!/usr/bin/env python3
"""
abhe_v0_runtime_slot_controller_v3_wire_stub
=============================================

A *stub* function that translates a v3 skeleton decision record into a
proxy action — BUT returns no-op for every input unless BOTH:

  - wire_authorized = True (must be passed by the caller; defaults False)
  - policy_enabled  = True (must be passed by the caller; defaults False)

Until a signed P1.5b approval packet AND a separate wire-step PR flips
these flags, this function is provably a no-op for all inputs.

This module:
  - does NOT call any provider
  - does NOT call BFCL generate/evaluate
  - does NOT call any scorer
  - does NOT import any provider client
  - does NOT read any prompt / gold / expected / argument-value
  - does NOT modify any artifact

It is exclusively for unit-tested defense-in-depth: when someone later
wires the v3 controller to the proxy, the wiring goes through *this*
single function, and the boundary discipline (no-op unless both flags
True) is enforced and tested in one place.
"""
from __future__ import annotations
from typing import Any, Dict, Optional


# Frozen valid decision class set (mirrors v2 controller outputs)
VALID_DECISION_CLASSES = frozenset({
    "allow_valid_tool_call",
    "bind_recovered_slots_then_call",
    "call_prerequisite_lookup",
    "ask_or_insufficient_due_ambiguity",
    "ask_or_insufficient",
})


# Action shapes the stub *would* emit if/when authorized. Currently NEVER
# returned (every path returns no_op_unauthorized while flags are False).
VALID_PROXY_ACTION_KINDS = frozenset({
    "no_op_unauthorized",
    "no_op_unknown_decision_class",
    "proxy_action_pass_through",            # would mean: emit the tool call as-is
    "proxy_action_substitute_bound_args",   # would mean: rewrite args with bound values
    "proxy_action_invoke_prerequisite",     # would mean: call lookup tool first
    "proxy_action_request_clarification",   # would mean: switch to clarification path
    "proxy_action_abstain",                 # would mean: emit empty response (record-only)
})


def _stub_action_when_authorized(decision_class: str) -> Dict[str, Any]:
    """Pure mapping from decision_class to action kind. Never invoked
    unless both wire_authorized and policy_enabled are True (which they
    are not by default). Kept as a separate function so unit tests can
    verify the mapping table without enabling the wire."""
    table = {
        "allow_valid_tool_call":              "proxy_action_pass_through",
        "bind_recovered_slots_then_call":     "proxy_action_substitute_bound_args",
        "call_prerequisite_lookup":           "proxy_action_invoke_prerequisite",
        "ask_or_insufficient_due_ambiguity":  "proxy_action_request_clarification",
        "ask_or_insufficient":                "proxy_action_abstain",
    }
    if decision_class not in table:
        return {
            "wire_stub_action_kind": "no_op_unknown_decision_class",
            "would_emit_proxy_action": False,
            "wire_authorized_effective": True,
            "policy_enabled_effective": True,
            "decision_class_seen": decision_class,
        }
    return {
        "wire_stub_action_kind": table[decision_class],
        "would_emit_proxy_action": True,
        "wire_authorized_effective": True,
        "policy_enabled_effective": True,
        "decision_class_seen": decision_class,
    }


def v3_decision_to_proxy_action(
    decision_record: Dict[str, Any],
    wire_authorized: bool = False,
    policy_enabled: bool = False,
) -> Dict[str, Any]:
    """Translate a v3 skeleton per-case decision record into a proxy
    action descriptor.

    Boundary discipline (the heart of this stub):
      - If wire_authorized is not True or policy_enabled is not True,
        the returned dict has wire_stub_action_kind='no_op_unauthorized'
        and would_emit_proxy_action=False. No further branching occurs.
      - If both flags are True, the action kind is looked up from the
        frozen table in _stub_action_when_authorized(). Even then, this
        function emits ONLY a descriptor dict; it never calls a provider,
        BFCL, or scorer.

    Args:
        decision_record: a dict produced by runtime_slot_controller_v2
                         (e.g. observed_decision_class field) OR a
                         skeleton case record from the v3 artifact.
        wire_authorized: bool, defaults False. MUST be flipped to True
                         by a signed authorisation packet before any
                         caller can get a non-no-op result.
        policy_enabled:  bool, defaults False. Same gate as above; the
                         backoff policy must independently be enabled.

    Returns:
        dict with keys:
          - wire_stub_action_kind: str (one of VALID_PROXY_ACTION_KINDS)
          - would_emit_proxy_action: bool
          - wire_authorized_effective: bool
          - policy_enabled_effective: bool
          - decision_class_seen: str | None
    """
    # Defensive: even if caller passes truthy non-bool, demand exactly True
    if wire_authorized is not True or policy_enabled is not True:
        decision_class_seen = None
        if isinstance(decision_record, dict):
            for key in ("decision", "observed_decision_class"):
                v = decision_record.get(key)
                if isinstance(v, str):
                    decision_class_seen = v
                    break
        return {
            "wire_stub_action_kind": "no_op_unauthorized",
            "would_emit_proxy_action": False,
            "wire_authorized_effective": False,
            "policy_enabled_effective": False,
            "decision_class_seen": decision_class_seen,
        }

    # Authorized path — still only a descriptor; never an actual call.
    decision_class = None
    if isinstance(decision_record, dict):
        for key in ("decision", "observed_decision_class"):
            v = decision_record.get(key)
            if isinstance(v, str):
                decision_class = v
                break
    if decision_class is None:
        return {
            "wire_stub_action_kind": "no_op_unknown_decision_class",
            "would_emit_proxy_action": False,
            "wire_authorized_effective": True,
            "policy_enabled_effective": True,
            "decision_class_seen": None,
        }
    return _stub_action_when_authorized(decision_class)


def assert_wire_invariants_hold() -> Dict[str, Any]:
    """Self-test utility: verifies the stub's structural invariants
    over the entire frozen decision-class set without enabling the
    wire. Returns a report dict suitable for being asserted by tests
    or by a checker."""
    report = {
        "valid_decision_classes_size": len(VALID_DECISION_CLASSES),
        "valid_proxy_action_kinds_size": len(VALID_PROXY_ACTION_KINDS),
        "no_op_unauthorized_paths_total": 0,
        "no_op_unauthorized_paths_no_op": 0,
        "would_emit_proxy_action_seen_outside_authorized": False,
    }
    for dc in VALID_DECISION_CLASSES:
        # Without authorization, every decision must be a no-op.
        for wa in (False, True):
            for pe in (False, True):
                if wa is True and pe is True:
                    continue  # only checking unauthorized combos here
                report["no_op_unauthorized_paths_total"] += 1
                r = v3_decision_to_proxy_action(
                    {"decision": dc}, wire_authorized=wa, policy_enabled=pe
                )
                if r["wire_stub_action_kind"] == "no_op_unauthorized" and r["would_emit_proxy_action"] is False:
                    report["no_op_unauthorized_paths_no_op"] += 1
                else:
                    report["would_emit_proxy_action_seen_outside_authorized"] = True
    report["all_unauthorized_paths_are_no_op"] = (
        report["no_op_unauthorized_paths_total"] == report["no_op_unauthorized_paths_no_op"]
        and report["would_emit_proxy_action_seen_outside_authorized"] is False
    )
    return report


if __name__ == "__main__":
    import json as _json
    print(_json.dumps(assert_wire_invariants_hold(), indent=2))
