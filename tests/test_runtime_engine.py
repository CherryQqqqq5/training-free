from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

_INJECTED_YAML_STUB = False
try:
    import yaml as _yaml  # noqa: F401
except ModuleNotFoundError:
    sys.modules["yaml"] = types.SimpleNamespace(safe_load=lambda _: {})
    _INJECTED_YAML_STUB = True

from grc.runtime.engine import RuleEngine
from grc.types import FallbackRoutingSpec, MatchSpec, PatchScope, Rule, RuleAction, VerificationContract

if _INJECTED_YAML_STUB:
    sys.modules.pop("yaml", None)


class RuntimeEngineTests(unittest.TestCase):
    @unittest.skipIf(_INJECTED_YAML_STUB, "PyYAML unavailable")
    def test_rule_loader_ignores_policy_unit_metadata_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir_raw:
            rules_dir = Path(rules_dir_raw)
            (rules_dir / "policy_unit.yaml").write_text(
                """
policy_units:
  - name: avoid_premature_termination
    trigger:
      - tools_available
    request_predicates:
      - tools_available
""".strip(),
                encoding="utf-8",
            )
            (rules_dir / "rule.yaml").write_text(
                """
rule_id: runtime_rule
priority: 7
enabled: true
trigger:
  error_types:
    - actionable_no_tool_decision
scope:
  patch_sites:
    - policy_executor
action:
  decision_policy:
    forbidden_terminations:
      - prose_only_no_tool_termination
""".strip(),
                encoding="utf-8",
            )

            engine = RuleEngine(rules_dir_raw)

        self.assertEqual([rule.rule_id for rule in engine.rules], ["runtime_rule"])

    def _make_move_file_request(self, *, messages=None) -> dict:
        return {
            "model": "demo-model",
            "messages": messages or [{"role": "user", "content": "Move 'report.txt' into the archive."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "move_file",
                        "parameters": {
                            "type": "object",
                            "properties": {"file_name": {"type": "string"}},
                            "required": ["file_name"],
                        },
                    },
                }
            ],
        }

    def _trajectory_candidate(self, candidate: dict, *, postcondition_kind: str | None = None) -> dict:
        enriched = dict(candidate)
        tool = str(enriched.get("tool") or (enriched.get("recommended_tools") or [""])[0])
        args = enriched.get("args") if isinstance(enriched.get("args"), dict) else {}
        target_arg = next(iter(args), "path")
        kind_by_tool = {
            "cat": "file_content",
            "touch": "file_exists",
            "mkdir": "directory_exists",
            "move_file": "target_path_changed",
            "copy_file": "target_path_changed",
            "mv": "target_path_changed",
            "cp": "target_path_changed",
            "grep": "matches",
            "find": "matches",
        }
        kind = postcondition_kind or kind_by_tool.get(tool, "target_path_changed")
        expected_state_key = "file_content" if kind == "file_content" else "current_directory_content"
        if kind == "matches":
            expected_state_key = "matches"
        enriched.setdefault(
            "postcondition",
            {"kind": kind, "expected_state_key": expected_state_key, "target_arg": target_arg, "confidence": 0.8},
        )
        enriched.setdefault("trajectory_risk_score", 2 if tool in {"cat", "touch", "mkdir"} else 0)
        enriched.setdefault("trajectory_risk_flags", ["trajectory_sensitive_tool"] if tool in {"cat", "touch", "mkdir"} else [])
        enriched.setdefault("binding_type", "file" if tool in {"cat", "touch"} else "path")
        enriched.setdefault("intervention_mode", "guidance")
        return enriched

    def _next_tool_rule(
        self,
        *,
        recommended_tools=None,
        request_predicates=None,
        activation_predicates=None,
        action_candidates=None,
    ) -> Rule:
        recommended_tools = list(recommended_tools or [])
        request_predicates = list(request_predicates or ["tools_available", "prior_explicit_literals_present"])
        activation_predicates = list(activation_predicates or request_predicates)
        action_candidates = [self._trajectory_candidate(candidate) for candidate in list(action_candidates or [])]
        return Rule(
            rule_id="rule_next_tool_policy",
            trigger=MatchSpec(
                error_types=["actionable_no_tool_decision"],
                request_predicates=request_predicates,
            ),
            scope=PatchScope(patch_sites=["prompt_injector", "policy_executor"]),
            action=RuleAction(
                decision_policy={
                    "request_predicates": request_predicates,
                    "recommended_tools": recommended_tools,
                    "action_candidates": list(action_candidates or []),
                    "next_tool_policy": {
                        "activation_predicates": activation_predicates,
                        "recommended_tools": recommended_tools,
                        "tool_choice_mode": "required",
                        "confidence": 0.8,
                    },
                }
            ),
        )

    def _make_text_response(self, content: str | None) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": content,
                    }
                }
            ]
        }

    @staticmethod
    def _expected_empty_repair(issue_kind: str) -> list[dict]:
        return [
            {
                "kind": "coerce_no_tool_text_to_empty",
                "issue_kind": issue_kind,
                "reason": "assistant emitted text-only content on a tool-enabled turn; coerced to empty response for structured tool clients",
            }
        ]

    def _make_post_tool_summary_request(self) -> dict:
        return {
            "model": "demo-model",
            "messages": [
                {"role": "user", "content": "Check the fuel level."},
                {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
                {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"fuelLevel": 10.0})},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "convert_gallon_to_liter",
                        "parameters": {
                            "type": "object",
                            "properties": {"gallon": {"type": "number"}},
                            "required": ["gallon"],
                        },
                    },
                }
            ],
        }

    def _run_no_tool_response(
        self,
        *,
        rules: list[Rule] | None = None,
        request: dict | None = None,
        response: dict | None = None,
        runtime_policy: dict | None = None,
    ) -> tuple[dict, list[dict], object]:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy=runtime_policy)
            engine.rules = list(rules or [])
            final_response, repairs, validation = engine.apply_response(
                request or self._make_move_file_request(),
                response or self._make_text_response("I'll move report.txt into the archive now."),
            )
        return final_response, repairs, validation

    def _make_actionable_policy_rule(
        self,
        *,
        request_predicates=None,
        forbidden_terminations=None,
        evidence_requirements=None,
    ) -> Rule:
        request_predicates = (
            ["tools_available", "prior_explicit_literals_present"]
            if request_predicates is None
            else request_predicates
        )
        forbidden_terminations = (
            ["prose_only_no_tool_termination"]
            if forbidden_terminations is None
            else forbidden_terminations
        )
        evidence_requirements = (
            list(request_predicates)
            if evidence_requirements is None
            else evidence_requirements
        )
        return Rule(
            rule_id="rule_global_no_tool_actionable_v1",
            trigger=MatchSpec(
                error_types=["actionable_no_tool_decision"],
                request_predicates=request_predicates,
            ),
            scope=PatchScope(tool_names=[], patch_sites=["prompt_injector", "policy_executor", "fallback_router"]),
            action=RuleAction(
                prompt_injection={"fragments": ["Emit the next tool call instead of prose-only termination."]},
                decision_policy={
                    "request_predicates": request_predicates,
                    "forbidden_terminations": forbidden_terminations,
                    "evidence_requirements": evidence_requirements,
                },
                fallback_router=FallbackRoutingSpec(
                    strategy="record_only",
                    on_issue_kinds=["actionable_no_tool_decision"],
                ),
            ),
            validation_contract=VerificationContract(),
        )

    def _make_compatibility_actionable_rule(
        self,
        *,
        request_predicates=None,
        forbidden_terminations=None,
        evidence_requirements=None,
    ) -> Rule:
        request_predicates = (
            ["tools_available", "prior_explicit_literals_present"]
            if request_predicates is None
            else request_predicates
        )
        forbidden_terminations = (
            ["prose_only_no_tool_termination"]
            if forbidden_terminations is None
            else forbidden_terminations
        )
        evidence_requirements = (
            list(request_predicates)
            if evidence_requirements is None
            else evidence_requirements
        )
        contract = VerificationContract(
            require_known_tool=False,
            require_object_args=False,
            require_required_fields=False,
            require_known_fields=False,
            require_type_match=False,
            forbidden_terminations=forbidden_terminations,
            evidence_requirements=evidence_requirements,
        )
        return Rule(
            rule_id="rule_global_no_tool_actionable_compat_v1",
            trigger=MatchSpec(
                error_types=["actionable_no_tool_decision"],
                request_predicates=request_predicates,
            ),
            scope=PatchScope(tool_names=[], patch_sites=["prompt_injector", "verification_hook", "fallback_router"]),
            action=RuleAction(
                prompt_injection={"fragments": ["Emit the next tool call instead of prose-only termination."]},
                verification=contract,
                fallback_router=FallbackRoutingSpec(
                    strategy="record_only",
                    on_issue_kinds=["actionable_no_tool_decision"],
                ),
            ),
            validation_contract=contract,
        )

    def test_apply_request_does_not_inject_global_prompts_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_global_no_tool_empty_tool_call_v1",
                    trigger=MatchSpec(error_types=["empty_tool_call"]),
                    scope=PatchScope(tool_names=[], patch_sites=["prompt_injector"]),
                    action=RuleAction(
                        prompt_fragments=["Emit the next tool call instead of explanatory prose."],
                    ),
                )
            ]
            request = {
                "model": "demo-model",
                "messages": [{"role": "user", "content": "What's the weather in Shanghai?"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }

            patched, request_patches = engine.apply_request(request)

        self.assertEqual(patched["messages"], request["messages"])
        self.assertEqual(request_patches, [])

    def test_apply_request_can_opt_in_global_prompt_injection(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"allow_global_prompt_injection": True})
            engine.rules = [
                Rule(
                    rule_id="rule_global_no_tool_empty_tool_call_v1",
                    trigger=MatchSpec(error_types=["empty_tool_call"]),
                    scope=PatchScope(tool_names=[], patch_sites=["prompt_injector"]),
                    action=RuleAction(
                        prompt_injection={"fragments": ["Emit the next tool call instead of explanatory prose."]},
                    ),
                )
            ]
            request = {
                "model": "demo-model",
                "messages": [{"role": "user", "content": "What's the weather in Shanghai?"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }

            patched, request_patches = engine.apply_request(request)

        self.assertEqual(patched["messages"][0]["role"], "system")
        self.assertIn("Emit the next tool call instead of explanatory prose.", patched["messages"][0]["content"])
        self.assertEqual(
            request_patches,
            ["prompt_injector:Emit the next tool call instead of explanatory prose."],
        )

    def test_apply_request_injects_predicate_gated_global_prompt_without_global_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_global_no_tool_actionable_v1",
                    trigger=MatchSpec(
                        error_types=["actionable_no_tool_decision"],
                        request_predicates=["tools_available", "prior_explicit_literals_present"],
                    ),
                    scope=PatchScope(tool_names=[], patch_sites=["prompt_injector"]),
                    action=RuleAction(
                        prompt_injection={
                            "fragments": ["Reuse explicit literals and emit the next tool call instead of stopping."]
                        },
                    ),
                )
            ]
            request = {
                "model": "demo-model",
                "messages": [{"role": "user", "content": "Move 'report.txt' into the archive."}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "move_file",
                            "parameters": {
                                "type": "object",
                                "properties": {"file_name": {"type": "string"}},
                                "required": ["file_name"],
                            },
                        },
                    }
                ],
            }

            patched, request_patches = engine.apply_request(request)

        self.assertEqual(patched["messages"][0]["role"], "system")
        self.assertIn("Reuse explicit literals and emit the next tool call instead of stopping.", patched["messages"][0]["content"])
        self.assertEqual(
            request_patches,
            ["prompt_injector:Reuse explicit literals and emit the next tool call instead of stopping."],
        )

    def test_apply_request_uses_decision_policy_predicates_when_trigger_predicates_are_empty(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_global_no_tool_actionable_v2",
                    trigger=MatchSpec(error_types=["actionable_no_tool_decision"]),
                    scope=PatchScope(tool_names=[], patch_sites=["prompt_injector"]),
                    action=RuleAction(
                        prompt_injection={
                            "fragments": ["Continue with the next grounded tool call."]
                        },
                        decision_policy={
                            "request_predicates": ["tools_available", "prior_explicit_literals_present"],
                            "forbidden_terminations": ["prose_only_no_tool_termination"],
                            "evidence_requirements": ["tools_available", "prior_explicit_literals_present"],
                        },
                    ),
                )
            ]
            request = {
                "model": "demo-model",
                "messages": [{"role": "user", "content": "Move 'report.txt' into the archive."}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "move_file",
                            "parameters": {
                                "type": "object",
                                "properties": {"file_name": {"type": "string"}},
                                "required": ["file_name"],
                            },
                        },
                    }
                ],
            }

            patched, request_patches = engine.apply_request(request)

        self.assertEqual(patched["messages"][0]["role"], "system")
        self.assertIn("Continue with the next grounded tool call.", patched["messages"][0]["content"])
        self.assertEqual(
            request_patches,
            ["prompt_injector:Continue with the next grounded tool call."],
        )


    def test_apply_request_injects_recommended_policy_tool_bias(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_global_no_tool_actionable_recommended_v1",
                    trigger=MatchSpec(error_types=["actionable_no_tool_decision"]),
                    scope=PatchScope(tool_names=[], patch_sites=["prompt_injector", "policy_executor"]),
                    action=RuleAction(
                        decision_policy={
                            "request_predicates": ["tools_available", "prior_explicit_literals_present"],
                            "recommended_tools": ["move_file"],
                            "forbidden_terminations": ["prose_only_no_tool_termination"],
                            "evidence_requirements": ["tools_available", "prior_explicit_literals_present"],
                        },
                    ),
                    validation_contract=VerificationContract(),
                )
            ]

            patched, request_patches = engine.apply_request(self._make_move_file_request())

        self.assertEqual(patched["messages"][0]["role"], "system")
        self.assertIn("Policy next-tool recommendation: prefer `move_file`", patched["messages"][0]["content"])
        self.assertIn("prompt_injector:Policy next-tool recommendation: prefer `move_file`", request_patches[0])
        self.assertIsNone(patched.get("tool_choice"))

    def test_apply_response_uses_decision_policy_contract_when_validation_contract_is_empty(self) -> None:
        _, _, validation = self._run_no_tool_response(
            rules=[self._make_actionable_policy_rule()],
        )

        self.assertEqual(
            [issue.kind for issue in validation.issues],
            ["actionable_no_tool_decision", "termination_inadmissible"],
        )

    def test_apply_response_does_not_infer_termination_from_compatibility_only_actionable_rule(self) -> None:
        _, _, validation = self._run_no_tool_response(
            rules=[self._make_compatibility_actionable_rule()],
        )

        self.assertEqual([issue.kind for issue in validation.issues], ["actionable_no_tool_decision"])

    def test_apply_response_does_not_add_termination_when_policy_evidence_is_unmet(self) -> None:
        _, _, validation = self._run_no_tool_response(
            rules=[
                self._make_actionable_policy_rule(
                    evidence_requirements=["tools_available", "prior_explicit_literals_present", "prior_tool_outputs_present"]
                )
            ],
        )

        self.assertEqual([issue.kind for issue in validation.issues], ["actionable_no_tool_decision"])

    def test_apply_response_does_not_add_termination_when_policy_forbidden_termination_is_absent(self) -> None:
        _, _, validation = self._run_no_tool_response(
            rules=[self._make_actionable_policy_rule(forbidden_terminations=[])],
        )

        self.assertEqual([issue.kind for issue in validation.issues], ["actionable_no_tool_decision"])

    def test_post_tool_prose_summary_requires_policy_rule_to_add_termination(self) -> None:
        _, _, validation = self._run_no_tool_response(
            rules=[
                self._make_compatibility_actionable_rule(
                    request_predicates=["tools_available", "prior_tool_outputs_present"],
                )
            ],
            request=self._make_post_tool_summary_request(),
            response=self._make_text_response("The current fuel level in your car is approximately 37.85 liters."),
        )

        self.assertEqual([issue.kind for issue in validation.issues], ["post_tool_prose_summary"])

    def test_apply_response_falls_back_to_compatibility_rules_when_no_decision_policy_exists(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(
                rules_dir,
                runtime_policy={"coerce_no_tool_response_to_empty_kinds": ["clarification_request"]},
            )
            engine.rules = [
                Rule(
                    rule_id="rule_global_no_tool_clarification_v1",
                    trigger=MatchSpec(error_types=["clarification_request"]),
                    scope=PatchScope(tool_names=[], patch_sites=["fallback_router"]),
                    action=RuleAction(
                        fallback_router=FallbackRoutingSpec(
                            strategy="record_only",
                            on_issue_kinds=["clarification_request"],
                        )
                    ),
                )
            ]
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Could you please specify which city you'd like me to check?",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(final_response["choices"][0]["message"]["content"], "")
        self.assertEqual([issue.kind for issue in validation.issues], ["clarification_request"])
        self.assertEqual(repairs[0]["kind"], "coerce_no_tool_text_to_empty")

    def test_apply_request_does_not_proactively_escalate_tool_choice_for_actionable_continuation_turn(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_global_no_tool_actionable_v1",
                    trigger=MatchSpec(
                        error_types=["actionable_no_tool_decision"],
                        request_predicates=["tools_available", "prior_tool_outputs_present"],
                    ),
                    scope=PatchScope(tool_names=[], patch_sites=["prompt_injector", "verification_hook", "fallback_router"]),
                    action=RuleAction(
                        prompt_injection={
                            "fragments": ["Emit the next tool call instead of stopping in prose."]
                        },
                    ),
                    validation_contract=VerificationContract(
                        require_known_tool=False,
                        require_object_args=False,
                        require_required_fields=False,
                        require_known_fields=False,
                        require_type_match=False,
                        forbidden_terminations=["prose_only_no_tool_termination"],
                        evidence_requirements=["tools_available", "prior_tool_outputs_present"],
                    ),
                )
            ]
            request = {
                "model": "demo-model",
                "messages": [
                    {"role": "user", "content": "Create a report."},
                    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
                    {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"file_name": "report.txt"})},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "touch",
                            "parameters": {
                                "type": "object",
                                "properties": {"file_name": {"type": "string"}},
                                "required": ["file_name"],
                            },
                        },
                    }
                ],
            }

            patched, request_patches = engine.apply_request(request)

        self.assertIsNone(patched.get("tool_choice"))
        self.assertNotIn("tool_choice:required(actionable_continuation)", request_patches)

    def test_apply_request_does_not_escalate_tool_choice_without_prior_tool_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_global_no_tool_actionable_v1",
                    trigger=MatchSpec(
                        error_types=["actionable_no_tool_decision"],
                        request_predicates=["tools_available", "prior_explicit_literals_present"],
                    ),
                    scope=PatchScope(tool_names=[], patch_sites=["prompt_injector", "verification_hook", "fallback_router"]),
                    action=RuleAction(
                        prompt_injection={"fragments": ["Reuse literals and continue with a tool call."]},
                    ),
                    validation_contract=VerificationContract(
                        require_known_tool=False,
                        require_object_args=False,
                        require_required_fields=False,
                        require_known_fields=False,
                        require_type_match=False,
                        forbidden_terminations=["prose_only_no_tool_termination"],
                        evidence_requirements=["tools_available", "prior_explicit_literals_present"],
                    ),
                )
            ]
            request = {
                "model": "demo-model",
                "messages": [{"role": "user", "content": "Move 'report.txt' into the archive."}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "move_file",
                            "parameters": {
                                "type": "object",
                                "properties": {"file_name": {"type": "string"}},
                                "required": ["file_name"],
                            },
                        },
                    }
                ],
            }

            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        self.assertNotIn("tool_choice:required(actionable_continuation)", request_patches)

    def test_apply_request_ignores_rules_without_prompt_injector_patch_site(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_lookup_weather_verification_only_v1",
                    trigger=MatchSpec(tool_names=["lookup_weather"]),
                    scope=PatchScope(tool_names=["lookup_weather"], patch_sites=["verification_hook"]),
                    action=RuleAction(
                        prompt_fragments=["This prompt should not be injected."],
                    ),
                )
            ]
            request = {
                "model": "demo-model",
                "messages": [{"role": "user", "content": "What's the weather in Shanghai?"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }

            patched, request_patches = engine.apply_request(request)

        self.assertEqual(patched["messages"], request["messages"])
        self.assertEqual(request_patches, [])

    def test_apply_request_can_inject_structured_tool_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(
                rules_dir,
                runtime_policy={
                    "inject_structured_tool_guidance": True,
                    "inject_context_literal_hints": True,
                },
            )
            request = {
                "model": "demo-model",
                "messages": [
                    {"role": "user", "content": "Create a file named 'Annual_Report_2023.docx' inside 'communal'."}
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "touch",
                            "parameters": {
                                "type": "object",
                                "properties": {"file_name": {"type": "string"}},
                                "required": ["file_name"],
                            },
                        },
                    }
                ],
            }

            patched, request_patches = engine.apply_request(request)

        self.assertEqual(patched["messages"][0]["role"], "system")
        system_text = patched["messages"][0]["content"]
        self.assertIn("emit the next tool call instead of explanatory prose", system_text)
        self.assertIn("Known explicit context values you can reuse exactly if relevant", system_text)
        self.assertIn("Annual_Report_2023.docx", system_text)
        self.assertTrue(any(patch.startswith("prompt_injector:For tool-enabled turns") for patch in request_patches))

    def test_collect_context_literals_ignores_json_keys_and_only_keeps_values(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(
                rules_dir,
                runtime_policy={
                    "inject_structured_tool_guidance": True,
                    "inject_context_literal_hints": True,
                },
            )
            request = {
                "model": "demo-model",
                "messages": [
                    {"role": "user", "content": "Search for files under '/workspace/document'."},
                    {
                        "role": "tool",
                        "content": json.dumps(
                            {
                                "matches": [
                                    "./workspace/document/TeamNotes.txt",
                                    "./workspace/document/FreshIdeasTracker.txt",
                                ],
                                "current_working_directory": "/workspace",
                                "message": "done",
                            }
                        ),
                    },
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "find",
                            "parameters": {
                                "type": "object",
                                "properties": {"path": {"type": "string"}},
                                "required": ["path"],
                            },
                        },
                    }
                ],
            }

            patched, request_patches = engine.apply_request(request)

        system_text = patched["messages"][0]["content"]
        hint_line = next(
            line for line in system_text.splitlines() if "Known explicit context values you can reuse exactly if relevant:" in line
        )
        self.assertIn("TeamNotes.txt", system_text)
        self.assertIn("FreshIdeasTracker.txt", system_text)
        self.assertNotIn("matches", hint_line)
        self.assertNotIn("current_working_directory", hint_line)
        self.assertNotIn("message", hint_line)
        self.assertTrue(any(patch.startswith("prompt_injector:Known explicit context values") for patch in request_patches))

    def test_engine_strips_narration_when_tool_calls_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I'll fetch the weather now.",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "lookup_weather",
                                        "arguments": json.dumps({"city": "Shanghai"}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(final_response["choices"][0]["message"]["content"], "")
        self.assertEqual(
            repairs,
            [
                {
                    "kind": "strip_assistant_content_with_tool_calls",
                    "reason": "assistant narration removed because the same message already emits tool calls",
                }
            ],
        )
        self.assertEqual(validation.repairs, repairs)

    def test_hallucinated_completion_recovery_rule_overrides_record_only_default(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_global_hallucinated_completion_v1",
                    trigger=MatchSpec(error_types=["hallucinated_completion"]),
                    scope=PatchScope(tool_names=[], patch_sites=["fallback_router"]),
                    action=RuleAction(
                        fallback_router=FallbackRoutingSpec(
                            strategy="assistant_message",
                            assistant_message="No tool call was emitted. Emit the required tool call before claiming progress.",
                            on_issue_kinds=["hallucinated_completion"],
                        )
                    ),
                )
            ]
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I've already initiated a weather lookup. Once I have the results, I'll let you know.",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertTrue(validation.fallback_applied)
        self.assertEqual([issue.kind for issue in validation.issues], ["hallucinated_completion"])
        self.assertEqual(
            final_response["choices"][0]["message"]["content"],
            "No tool call was emitted. Emit the required tool call before claiming progress.",
        )

    def test_no_tool_text_can_be_coerced_to_empty_for_structured_clients(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(
                rules_dir,
                runtime_policy={"coerce_no_tool_response_to_empty_kinds": ["clarification_request"]},
            )
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Could you please specify which city you'd like me to check?",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(final_response["choices"][0]["message"]["content"], "")
        self.assertEqual(
            repairs,
            [
                {
                    "kind": "coerce_no_tool_text_to_empty",
                    "issue_kind": "clarification_request",
                    "reason": "assistant emitted text-only content on a tool-enabled turn; coerced to empty response for structured tool clients",
                }
            ],
        )
        self.assertEqual([issue.kind for issue in validation.issues], ["clarification_request"])
        self.assertFalse(validation.fallback_applied)

    def test_actionable_no_tool_decision_can_be_coerced_to_empty_for_structured_clients(self) -> None:
        final_response, repairs, validation = self._run_no_tool_response(
            rules=[self._make_actionable_policy_rule()],
            response=self._make_text_response("I've moved the file into the archive."),
            runtime_policy={"coerce_no_tool_response_to_empty_kinds": ["actionable_no_tool_decision"]},
        )

        self.assertEqual(final_response["choices"][0]["message"]["content"], "")
        self.assertEqual(
            [issue.kind for issue in validation.issues],
            ["actionable_no_tool_decision", "termination_inadmissible"],
        )
        self.assertEqual(repairs, self._expected_empty_repair("actionable_no_tool_decision"))
        self.assertFalse(validation.fallback_applied)

    def test_post_tool_prose_summary_is_coerced_and_reuses_actionable_contract(self) -> None:
        final_response, repairs, validation = self._run_no_tool_response(
            rules=[
                self._make_actionable_policy_rule(
                    request_predicates=["tools_available", "prior_tool_outputs_present"],
                )
            ],
            request=self._make_post_tool_summary_request(),
            response=self._make_text_response("The current fuel level in your car is approximately 37.85 liters."),
            runtime_policy={"coerce_no_tool_response_to_empty_kinds": ["post_tool_prose_summary"]},
        )

        self.assertEqual(final_response["choices"][0]["message"]["content"], "")
        self.assertEqual(
            [issue.kind for issue in validation.issues],
            ["post_tool_prose_summary", "termination_inadmissible"],
        )
        self.assertEqual(repairs, self._expected_empty_repair("post_tool_prose_summary"))

    def test_post_tool_prose_summary_requires_recent_tool_output(self) -> None:
        _, _, validation = self._run_no_tool_response(
            request=self._make_move_file_request(),
            response=self._make_text_response("I've moved the file into the archive."),
        )

        self.assertEqual([issue.kind for issue in validation.issues], ["actionable_no_tool_decision"])

    def test_actionable_rule_does_not_fire_without_matching_predicates(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [self._make_actionable_policy_rule()]
            request = {
                "model": "demo-model",
                "messages": [{"role": "user", "content": "Check the weather."}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I will look into that.",
                        }
                    }
                ]
            }

            patched, request_patches = engine.apply_request(request)
            _, _, validation = engine.apply_response(request, response)

        self.assertEqual(patched["messages"], request["messages"])
        self.assertEqual(request_patches, [])
        self.assertEqual([issue.kind for issue in validation.issues], ["empty_tool_call"])

    def test_blank_no_tool_response_stays_empty_tool_call_even_with_actionable_predicates(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [self._make_actionable_policy_rule()]
            request = self._make_move_file_request()
            response = self._make_text_response("")

            _, _, validation = engine.apply_response(request, response)

        self.assertEqual([issue.kind for issue in validation.issues], ["empty_tool_call"])

    def test_null_no_tool_completion_is_recorded_separately_and_keeps_post_tool_context(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [self._make_actionable_policy_rule(request_predicates=["tools_available", "prior_tool_outputs_present"])]
            request = self._make_post_tool_summary_request()
            response = {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": None,
                        },
                    }
                ],
                "usage": {"completion_tokens": 0},
            }

            _, _, validation = engine.apply_response(request, response)

        self.assertEqual([issue.kind for issue in validation.issues], ["empty_completion"])
        self.assertEqual(validation.request_predicates, ["prior_tool_outputs_present", "tools_available"])
        self.assertEqual(validation.last_observed_role, "tool")
        self.assertEqual(validation.response_shapes, ["empty_completion"])
        self.assertEqual(validation.failure_labels, ["(POST_TOOL,EMPTY_TOOL_CALL)"])

    def test_explicit_no_tool_recovery_takes_precedence_over_empty_coercion(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(
                rules_dir,
                runtime_policy={"coerce_no_tool_response_to_empty_kinds": ["clarification_request"]},
            )
            engine.rules = [
                Rule(
                    rule_id="rule_global_clarification_request_v1",
                    trigger=MatchSpec(error_types=["clarification_request"]),
                    scope=PatchScope(tool_names=[], patch_sites=["fallback_router"]),
                    action=RuleAction(
                        fallback_router=FallbackRoutingSpec(
                            strategy="assistant_message",
                            assistant_message="Provide the next tool call instead of asking again.",
                            on_issue_kinds=["clarification_request"],
                        )
                    ),
                )
            ]
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Could you please specify which city you'd like me to check?",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(
            final_response["choices"][0]["message"]["content"],
            "Provide the next tool call instead of asking again.",
        )
        self.assertEqual(repairs, [])
        self.assertTrue(validation.fallback_applied)

    def test_contextual_string_arg_resolution_reuses_prior_file_literal(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(
                rules_dir,
                runtime_policy={"resolve_contextual_string_args": True},
            )
            request = {
                "model": "demo-model",
                "messages": [
                    {"role": "user", "content": "Please create 'Annual_Report_2023.docx' in the communal folder."},
                    {"role": "user", "content": "Now count words in the file I previously mentioned."},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "wc",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "file_name": {
                                        "type": "string",
                                        "description": "Name of the file to inspect.",
                                    },
                                    "mode": {"type": "string"},
                                },
                                "required": ["file_name", "mode"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "wc",
                                        "arguments": json.dumps(
                                            {"file_name": "the file I previously mentioned", "mode": "w"}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(
            json.loads(final_response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]),
            {"file_name": "Annual_Report_2023.docx", "mode": "w"},
        )
        self.assertIn(
            {
                "kind": "resolve_contextual_string_arg",
                "field": "file_name",
                "from": "the file I previously mentioned",
                "to": "Annual_Report_2023.docx",
                "tool_name": "wc",
            },
            repairs,
        )
        self.assertEqual(validation.issues, [])

    def test_no_tool_recovery_uses_matching_global_rule_only(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_global_empty_tool_call_v1",
                    trigger=MatchSpec(error_types=["empty_tool_call"]),
                    scope=PatchScope(tool_names=[], patch_sites=["fallback_router"]),
                    action=RuleAction(
                        fallback_router=FallbackRoutingSpec(
                            strategy="assistant_message",
                            assistant_message="Emit the next tool call.",
                            on_issue_kinds=["empty_tool_call"],
                        )
                    ),
                ),
                Rule(
                    rule_id="rule_global_nl_termination_v1",
                    trigger=MatchSpec(error_types=["natural_language_termination"]),
                    scope=PatchScope(tool_names=[], patch_sites=["fallback_router"]),
                    action=RuleAction(
                        fallback_router=FallbackRoutingSpec(
                            strategy="assistant_message",
                            assistant_message="Do not terminate early.",
                            on_issue_kinds=["natural_language_termination"],
                        )
                    ),
                ),
            ]
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Task is complete.",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertTrue(validation.fallback_applied)
        self.assertEqual([issue.kind for issue in validation.issues], ["natural_language_termination"])
        self.assertEqual(final_response["choices"][0]["message"]["content"], "Do not terminate early.")

    def test_hallucinated_completion_is_record_only_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I've already initiated a weather lookup. Once I have the results, I'll let you know.",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertFalse(validation.fallback_applied)
        self.assertEqual([issue.kind for issue in validation.issues], ["hallucinated_completion"])
        self.assertEqual(
            final_response["choices"][0]["message"]["content"],
            "I've already initiated a weather lookup. Once I have the results, I'll let you know.",
        )

    def test_tool_specific_fallback_uses_matching_issue_rule_only(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_lookup_weather_invalid_json_v1",
                    trigger=MatchSpec(tool_names=["lookup_weather"], error_types=["invalid_json_args"]),
                    scope=PatchScope(tool_names=["lookup_weather"], patch_sites=["fallback_router"]),
                    action=RuleAction(
                        fallback_router=FallbackRoutingSpec(
                            strategy="assistant_message",
                            assistant_message="Arguments must be valid JSON.",
                            on_issue_kinds=["invalid_json_args"],
                        )
                    ),
                ),
                Rule(
                    rule_id="rule_lookup_weather_missing_required_v1",
                    trigger=MatchSpec(tool_names=["lookup_weather"], error_types=["missing_required"]),
                    scope=PatchScope(tool_names=["lookup_weather"], patch_sites=["fallback_router"]),
                    action=RuleAction(
                        fallback_router=FallbackRoutingSpec(
                            strategy="assistant_message",
                            assistant_message="Missing required fields.",
                            on_issue_kinds=["missing_required"],
                        )
                    ),
                ),
            ]
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "city": {"type": "string"},
                                    "days": {"type": "integer"},
                                },
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "lookup_weather",
                                        "arguments": json.dumps({"days": 3}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertTrue(validation.fallback_applied)
        self.assertEqual([issue.kind for issue in validation.issues], ["missing_required"])
        self.assertEqual(final_response["choices"][0]["message"]["content"], "Missing required fields.")

    def test_natural_language_termination_is_record_only_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Task is complete.",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertFalse(validation.fallback_applied)
        self.assertEqual([issue.kind for issue in validation.issues], ["natural_language_termination"])
        self.assertEqual(final_response["choices"][0]["message"]["content"], "Task is complete.")

    def test_engine_normalizes_tool_schema_types_from_request_tools(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "dict",
                                "properties": {"days": {"type": "int"}},
                                "required": [],
                            },
                        },
                    }
                ],
            }

            schema_map = engine._tool_schema_map(request)

        self.assertEqual(schema_map["lookup_weather"]["type"], "object")
        self.assertEqual(schema_map["lookup_weather"]["properties"]["days"]["type"], "integer")

    def test_unsupported_request_is_not_marked_as_empty_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I can't directly complete that because there is no function available to do it.",
                        }
                    }
                ]
            }

            _, _, validation = engine.apply_response(request, response)

        self.assertEqual([issue.kind for issue in validation.issues], ["unsupported_request"])

    def test_malformed_output_is_not_marked_as_empty_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "<",
                        }
                    }
                ]
            }

            _, _, validation = engine.apply_response(request, response)

        self.assertEqual([issue.kind for issue in validation.issues], ["malformed_output"])

    def test_json_action_block_is_parsed_into_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "city": {"type": "string"},
                                    "days": {"type": "integer"},
                                },
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "action": "lookup_weather",
                                    "action_input": {"city": "Shanghai", "days": 3},
                                }
                            ),
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertEqual(validation.issues, [])
        tool_calls = final_response["choices"][0]["message"]["tool_calls"]
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["function"]["name"], "lookup_weather")
        self.assertEqual(tool_calls[0]["function"]["arguments"], json.dumps({"city": "Shanghai", "days": 3}))

    def test_multiple_json_action_blocks_are_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lockDoors",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "unlock": {"type": "boolean"},
                                    "door": {"type": "array"},
                                },
                                "required": ["unlock", "door"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "setHeadlights",
                            "parameters": {
                                "type": "object",
                                "properties": {"mode": {"type": "string"}},
                                "required": ["mode"],
                            },
                        },
                    },
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{\n  "action": "lockDoors",\n  "action_input": {\n    "unlock": true,\n'
                                '    "door": ["driver", "passenger"]\n  }\n}\n'
                                '{\n  "action": "setHeadlights",\n  "action_input": {\n    "mode": "on"\n  }\n}'
                            ),
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertEqual(validation.issues, [])
        tool_calls = final_response["choices"][0]["message"]["tool_calls"]
        self.assertEqual([call["function"]["name"] for call in tool_calls], ["lockDoors", "setHeadlights"])

    def test_clarification_request_is_not_marked_as_empty_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Could you please provide the city before I look up the weather?",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertFalse(validation.fallback_applied)
        self.assertEqual([issue.kind for issue in validation.issues], ["clarification_request"])
        self.assertEqual(
            final_response["choices"][0]["message"]["content"],
            "Could you please provide the city before I look up the weather?",
        )

    def test_required_next_tool_choice_is_config_gated(self) -> None:
        rule = self._next_tool_rule(recommended_tools=["move_file"])
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(self._make_move_file_request())

        self.assertNotIn("tool_choice", patched)
        self.assertIn("policy_next_tool:selected=move_file", request_patches)
        self.assertIn("policy_hit:rule_next_tool_policy", request_patches)

        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(self._make_move_file_request())

        self.assertEqual(patched["tool_choice"], "required")
        self.assertIn("tool_choice:required(policy_next_tool)", request_patches)

    def test_next_tool_plan_records_no_tools_available(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {"model": "demo-model", "messages": [{"role": "user", "content": "hello"}]}
            response = {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}
            patched, request_patches = engine.apply_request(request)
            _, _, validation = engine.apply_response(patched, response, request_patches=request_patches)

        self.assertTrue(validation.next_tool_plan_attempted)
        self.assertFalse(validation.next_tool_plan_activated)
        self.assertEqual(validation.next_tool_plan_blocked_reason, "no_tools_available")
        self.assertEqual(validation.available_tools, [])

    def test_next_tool_plan_records_request_predicates_unmet(self) -> None:
        rule = self._next_tool_rule(recommended_tools=["move_file"])
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [rule]
            request = self._make_move_file_request(messages=[{"role": "user", "content": "Move it."}])
            response = {"choices": [{"message": {"role": "assistant", "content": "Done"}}]}
            patched, request_patches = engine.apply_request(request)
            _, _, validation = engine.apply_response(patched, response, request_patches=request_patches)

        self.assertTrue(validation.next_tool_plan_attempted)
        self.assertFalse(validation.next_tool_plan_activated)
        self.assertEqual(validation.next_tool_plan_blocked_reason, "request_predicates_unmet")
        self.assertEqual(validation.candidate_recommended_tools, ["move_file"])
        self.assertFalse(validation.activation_predicate_status["prior_explicit_literals_present"])

    def test_next_tool_plan_records_activation_predicates_unmet(self) -> None:
        rule = self._next_tool_rule(
            recommended_tools=["move_file"],
            request_predicates=["tools_available"],
            activation_predicates=["tools_available", "prior_tool_outputs_present"],
        )
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [rule]
            response = {"choices": [{"message": {"role": "assistant", "content": "Done"}}]}
            patched, request_patches = engine.apply_request(self._make_move_file_request())
            _, _, validation = engine.apply_response(patched, response, request_patches=request_patches)

        self.assertFalse(validation.next_tool_plan_activated)
        self.assertEqual(validation.next_tool_plan_blocked_reason, "activation_predicates_unmet")
        self.assertTrue(validation.activation_predicate_status["tools_available"])
        self.assertFalse(validation.activation_predicate_status["prior_tool_outputs_present"])

    def test_next_tool_plan_records_empty_recommended_tools(self) -> None:
        rule = self._next_tool_rule(
            recommended_tools=[],
            request_predicates=["tools_available"],
            activation_predicates=["tools_available"],
        )
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [rule]
            response = {"choices": [{"message": {"role": "assistant", "content": "Done"}}]}
            patched, request_patches = engine.apply_request(self._make_move_file_request())
            _, _, validation = engine.apply_response(patched, response, request_patches=request_patches)

        self.assertFalse(validation.next_tool_plan_activated)
        self.assertEqual(validation.next_tool_plan_blocked_reason, "recommended_tools_empty")
        self.assertEqual(validation.candidate_recommended_tools, [])

    def test_next_tool_plan_records_recommended_tools_not_in_schema(self) -> None:
        rule = self._next_tool_rule(
            recommended_tools=["copy_file"],
            request_predicates=["tools_available"],
            activation_predicates=["tools_available"],
        )
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [rule]
            response = {"choices": [{"message": {"role": "assistant", "content": "Done"}}]}
            patched, request_patches = engine.apply_request(self._make_move_file_request())
            _, _, validation = engine.apply_response(patched, response, request_patches=request_patches)

        self.assertFalse(validation.next_tool_plan_activated)
        self.assertEqual(validation.next_tool_plan_blocked_reason, "recommended_tools_not_in_schema")
        self.assertEqual(validation.candidate_recommended_tools, ["copy_file"])
        self.assertEqual(validation.matched_recommended_tools, [])

    def test_next_tool_conversion_fields_are_recorded(self) -> None:
        request = self._make_move_file_request()
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": "move_file", "arguments": "{\"file_name\":\"report.txt\"}"},
                            }
                        ],
                    }
                }
            ]
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            _, _, validation = engine.apply_response(
                request,
                response,
                request_patches=[
                    "policy_next_tool:activated",
                    "policy_next_tool:selected=move_file",
                    "policy_next_tool:recommended=move_file",
                    "policy_hit:rule_next_tool_policy",
                ],
            )

        self.assertEqual(validation.policy_hits, ["rule_next_tool_policy"])
        self.assertEqual(validation.recommended_tools, ["move_file"])
        self.assertEqual(validation.selected_next_tool, "move_file")
        self.assertTrue(validation.next_tool_emitted)
        self.assertTrue(validation.next_tool_matches_recommendation)

    def test_next_tool_plan_activation_diagnostics_are_recorded(self) -> None:
        rule = self._next_tool_rule(recommended_tools=["move_file"])
        request = self._make_move_file_request()
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": "move_file", "arguments": "{\"file_name\":\"report.txt\"}"},
                            }
                        ],
                    }
                }
            ]
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)
            _, _, validation = engine.apply_response(patched, response, request_patches=request_patches)

        self.assertEqual(patched["tool_choice"], "required")
        self.assertTrue(validation.next_tool_plan_attempted)
        self.assertTrue(validation.next_tool_plan_activated)
        self.assertEqual(validation.next_tool_plan_blocked_reason, "activated")
        self.assertEqual(validation.available_tools, ["move_file"])
        self.assertEqual(validation.candidate_recommended_tools, ["move_file"])
        self.assertEqual(validation.matched_recommended_tools, ["move_file"])
        self.assertEqual(validation.selected_next_tool, "move_file")
        self.assertEqual(validation.tool_choice_mode, "required")
        self.assertTrue(validation.next_tool_emitted)
        self.assertTrue(validation.next_tool_matches_recommendation)


    def test_next_tool_guard_allows_high_confidence_explicit_binding(self) -> None:
        action_candidate = {
            "tool": "move_file",
            "args": {"file_name": "report.txt"},
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "report.txt"}},
            "recommended_tools": ["move_file"],
        }
        rule = self._next_tool_rule(recommended_tools=["move_file"], action_candidates=[action_candidate])
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(self._make_move_file_request())

        self.assertEqual(patched["tool_choice"], "required")
        self.assertIn("policy_next_tool:selected=move_file", request_patches)
        self.assertTrue(request_patches.next_tool_plan["action_candidate_guard"]["accepted"])
        self.assertEqual(request_patches.next_tool_plan["action_candidate_guard"]["reason"], "strong_explicit_literal_binding")

    def test_next_tool_guard_blocks_stale_explicit_literal_candidate(self) -> None:
        action_candidate = {
            "tool": "move_file",
            "args": {"file_name": "stale.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "stale.txt"}},
            "recommended_tools": ["move_file"],
        }
        rule = self._next_tool_rule(recommended_tools=["move_file"], action_candidates=[action_candidate])
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            _, request_patches = engine.apply_request(self._make_move_file_request())

        self.assertEqual(request_patches.next_tool_plan["blocked_reason"], "action_candidate_guard_rejected")
        guard = request_patches.next_tool_plan["rejected_action_candidates"][0]["guard"]
        self.assertFalse(guard["accepted"])
        self.assertEqual(guard["reason"], "explicit_literal_not_in_current_state")

    def test_next_tool_guard_blocks_legacy_candidate_missing_postcondition(self) -> None:
        action_candidate = {
            "tool": "move_file",
            "args": {"file_name": "report.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "report.txt"}},
            "recommended_tools": ["move_file"],
        }
        rule = self._next_tool_rule(recommended_tools=["move_file"], action_candidates=[])
        rule.action.decision_policy.action_candidates = [action_candidate]
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(self._make_move_file_request())

        self.assertNotIn("tool_choice", patched)
        self.assertFalse(request_patches.next_tool_plan["activated"])
        self.assertEqual(request_patches.next_tool_plan["blocked_reason"], "action_candidate_guard_rejected")
        guard = request_patches.next_tool_plan["rejected_action_candidates"][0]["guard"]
        self.assertFalse(guard["accepted"])
        self.assertEqual(guard["reason"], "intervention_mode_record_only")
        self.assertIn("intervention_mode_record_only", guard["risk_flags"])

    def test_next_tool_guard_blocks_weak_generic_prior_output_candidate(self) -> None:
        action_candidate = {
            "tool": "touch",
            "args": {"file_name": "marker.txt"},
            "binding_source": "prior_tool_output.cwd_or_listing",
            "arg_bindings": {
                "file_name": {
                    "source": "prior_tool_output.cwd_or_listing",
                    "value": "marker.txt",
                    "evidence": {"prior_output_keys": ["current_working_directory", "disk_usage"]},
                }
            },
            "recommended_tools": ["touch"],
        }
        rule = self._next_tool_rule(
            recommended_tools=["touch"],
            request_predicates=["tools_available", "prior_tool_outputs_present"],
            activation_predicates=["tools_available", "prior_tool_outputs_present"],
            action_candidates=[action_candidate],
        )
        request = {
            "model": "demo-model",
            "messages": [
                {"role": "user", "content": "Continue from the current directory."},
                {"role": "tool", "content": json.dumps({"current_working_directory": "/tmp", "disk_usage": "10B"})},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "touch",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        self.assertFalse(request_patches.next_tool_plan["activated"])
        self.assertEqual(request_patches.next_tool_plan["blocked_reason"], "action_candidate_guard_rejected")
        guard = request_patches.next_tool_plan["rejected_action_candidates"][0]["guard"]
        self.assertFalse(guard["accepted"])
        self.assertIn("weak_cwd_or_listing_binding", guard["risk_flags"])

    def test_next_tool_guard_blocks_cat_when_write_intent_is_stronger(self) -> None:
        action_candidate = {
            "tool": "cat",
            "args": {"file_name": "ProjectOverview.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "ProjectOverview.txt"}},
            "recommended_tools": ["cat"],
        }
        rule = self._next_tool_rule(recommended_tools=["cat"], action_candidates=[action_candidate])
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Modify ProjectOverview.txt by putting Hello into it."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "cat",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        self.assertFalse(request_patches.next_tool_plan["activated"])
        guard = request_patches.next_tool_plan["rejected_action_candidates"][0]["guard"]
        self.assertIn("cat_competing_intent", guard["risk_flags"])

    def test_action_candidate_literal_score_does_not_match_filename_substrings(self) -> None:
        engine = RuleEngine("/tmp/nonexistent-rules")
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Create project_summary.txt in the current directory."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "touch",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                }
            ],
        }
        components = engine._action_candidate_score_components(
            {
                "tool": "touch",
                "args": {"file_name": "summary.txt"},
                "binding_source": "explicit_literal",
                "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "summary.txt"}},
            },
            request_json=request,
            request_tool_name_set={"touch"},
            recommended=["touch"],
            confidence=0.8,
            index=0,
        )

        self.assertEqual(components["literal_score"], 0)
        self.assertEqual(components["arg_binding_score"], 0)

    def test_next_tool_guard_blocks_touch_literal_without_create_intent(self) -> None:
        action_candidate = {
            "tool": "touch",
            "args": {"file_name": "summary.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "summary.txt"}},
            "recommended_tools": ["touch"],
        }
        rule = self._next_tool_rule(recommended_tools=["touch"], action_candidates=[action_candidate])
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Inspect summary.txt and report what it says."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "touch",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        self.assertFalse(request_patches.next_tool_plan["activated"])
        guard = request_patches.next_tool_plan["rejected_action_candidates"][0]["guard"]
        self.assertIn("write_intent_unconfirmed", guard["risk_flags"])

    def test_next_tool_guard_blocks_repeated_generic_tool_without_new_evidence(self) -> None:
        action_candidate = {
            "tool": "touch",
            "args": {"file_name": "project_summary.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "project_summary.txt"}},
            "recommended_tools": ["touch"],
        }
        rule = self._next_tool_rule(
            recommended_tools=["touch"],
            request_predicates=["tools_available", "prior_explicit_literals_present", "prior_tool_outputs_present"],
            activation_predicates=["tools_available", "prior_explicit_literals_present", "prior_tool_outputs_present"],
            action_candidates=[action_candidate],
        )
        request = {
            "model": "demo-model",
            "messages": [
                {"role": "user", "content": "Create an empty file named 'project_summary.txt'."},
                {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "touch", "arguments": "{\"file_name\":\"project_summary.txt\"}"}}]},
                {"role": "tool", "tool_call_id": "c1", "content": "None"},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "touch",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        self.assertFalse(request_patches.next_tool_plan["activated"])
        guard = request_patches.next_tool_plan["rejected_action_candidates"][0]["guard"]
        self.assertIn("repeat_same_tool_without_new_evidence", guard["risk_flags"])

    def test_next_tool_guard_allows_prior_match_binding_without_request_literal(self) -> None:
        action_candidate = {
            "tool": "cat",
            "args": {"file_name": "notes.txt"},
            "binding_source": "prior_tool_output.matches[0]|basename",
            "arg_bindings": {"file_name": {"source": "prior_tool_output.matches[0]|basename", "value": "notes.txt"}},
            "recommended_tools": ["cat"],
        }
        rule = self._next_tool_rule(
            recommended_tools=["cat"],
            request_predicates=["tools_available", "prior_tool_outputs_present"],
            activation_predicates=["tools_available", "prior_tool_outputs_present"],
            action_candidates=[action_candidate],
        )
        request = {
            "model": "demo-model",
            "messages": [
                {"role": "user", "content": "Read the matching file."},
                {"role": "tool", "name": "find", "content": json.dumps({"matches": ["/workspace/other.txt"]})},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "cat",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertEqual(patched["tool_choice"], "required")
        self.assertEqual(request_patches.next_tool_plan["action_candidate_guard"]["reason"], "strong_prior_output_match_binding")

    def test_next_tool_guard_allows_clean_cwd_listing_binding(self) -> None:
        action_candidate = {
            "tool": "touch",
            "args": {"file_name": "marker.txt"},
            "binding_source": "prior_tool_output.cwd_or_listing",
            "arg_bindings": {"file_name": {"source": "prior_tool_output.cwd_or_listing", "value": "marker.txt"}},
            "recommended_tools": ["touch"],
        }
        rule = self._next_tool_rule(
            recommended_tools=["touch"],
            request_predicates=["tools_available", "prior_tool_outputs_present"],
            activation_predicates=["tools_available", "prior_tool_outputs_present"],
            action_candidates=[action_candidate],
        )
        request = {
            "model": "demo-model",
            "messages": [
                {"role": "user", "content": "Continue from the clean directory listing."},
                {"role": "tool", "name": "ls", "content": json.dumps({"current_directory_content": ["new_folder"]})},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "touch",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertEqual(patched["tool_choice"], "required")
        self.assertEqual(request_patches.next_tool_plan["action_candidate_guard"]["reason"], "clean_cwd_listing_binding")

    def test_next_tool_guard_blocks_repeated_prior_match_binding(self) -> None:
        action_candidate = {
            "tool": "cat",
            "args": {"file_name": "notes.txt"},
            "binding_source": "prior_tool_output.matches[0]|basename",
            "arg_bindings": {"file_name": {"source": "prior_tool_output.matches[0]|basename", "value": "notes.txt"}},
            "recommended_tools": ["cat"],
        }
        rule = self._next_tool_rule(
            recommended_tools=["cat"],
            request_predicates=["tools_available", "prior_tool_outputs_present"],
            activation_predicates=["tools_available", "prior_tool_outputs_present"],
            action_candidates=[action_candidate],
        )
        request = {
            "model": "demo-model",
            "messages": [
                {"role": "user", "content": "Read the matching file."},
                {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "cat", "arguments": "{\"file_name\":\"old.txt\"}"}}]},
                {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"matches": ["/workspace/other.txt"]})},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "cat",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        guard = request_patches.next_tool_plan["rejected_action_candidates"][0]["guard"]
        self.assertIn("repeat_same_tool_without_new_evidence", guard["risk_flags"])

    def test_next_tool_guard_blocks_post_search_literal_cat_intervention(self) -> None:
        action_candidate = {
            "tool": "cat",
            "args": {"file_name": "summary_2024.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "summary_2024.txt"}},
            "recommended_tools": ["cat"],
        }
        rule = self._next_tool_rule(
            recommended_tools=["cat"],
            request_predicates=["tools_available", "prior_explicit_literals_present", "prior_tool_outputs_present"],
            activation_predicates=["tools_available", "prior_explicit_literals_present", "prior_tool_outputs_present"],
            action_candidates=[action_candidate],
        )
        request = {
            "model": "demo-model",
            "messages": [
                {"role": "user", "content": "Search summary_2024.txt for the specific term."},
                {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "grep", "arguments": "{\"file_name\":\"summary_2024.txt\",\"pattern\":\"term\"}"}}]},
                {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"matching_lines": []})},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "cat",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        guard = request_patches.next_tool_plan["rejected_action_candidates"][0]["guard"]
        self.assertIn("post_search_literal_cat_intervention", guard["risk_flags"])

    def test_next_tool_arg_binding_validation_records_match(self) -> None:
        action_candidate = {
            "tool": "move_file",
            "args": {"file_name": "report.txt"},
            "arg_bindings": {
                "file_name": {
                    "source": "explicit_literal",
                    "value": "report.txt",
                }
            },
            "recommended_tools": ["move_file"],
        }
        rule = self._next_tool_rule(recommended_tools=["move_file"], action_candidates=[action_candidate])
        request = self._make_move_file_request()
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": "move_file", "arguments": "{\"file_name\":\"report.txt\"}"},
                            }
                        ],
                    }
                }
            ]
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)
            _, _, validation = engine.apply_response(patched, response, request_patches=request_patches)

        self.assertTrue(validation.next_tool_plan_activated)
        self.assertEqual(validation.selected_action_candidate["tool"], "move_file")
        self.assertTrue(validation.next_tool_args_emitted)
        self.assertTrue(validation.next_tool_args_match_binding)
        self.assertTrue(validation.next_tool_args_match_binding_normalized)
        self.assertTrue(validation.next_tool_final_args_match_binding)
        self.assertTrue(validation.next_tool_final_args_match_binding_normalized)
        row = validation.arg_binding_validation["file_name"]
        self.assertEqual(row["expected"], "report.txt")
        self.assertEqual(row["observed"], "report.txt")
        self.assertEqual(row["source"], "explicit_literal")
        self.assertTrue(row["match"])
        self.assertTrue(row["key_match"])
        self.assertFalse(row["key_mismatch"])
        self.assertTrue(row["value_match"])
        self.assertTrue(row["required_pair_complete"])
        self.assertEqual(validation.final_arg_binding_validation, validation.arg_binding_validation)

    def test_next_tool_arg_binding_keeps_raw_match_when_contextual_repair_changes_final_arg(self) -> None:
        action_candidate = {
            "tool": "cat",
            "args": {"file_name": "notes.txt"},
            "arg_bindings": {
                "file_name": {
                    "source": "prior_tool_output.matches[0]|basename",
                    "value": "notes.txt",
                }
            },
            "recommended_tools": ["cat"],
        }
        rule = self._next_tool_rule(
            recommended_tools=["cat"],
            request_predicates=["tools_available", "prior_tool_outputs_present"],
            activation_predicates=["tools_available", "prior_tool_outputs_present"],
            action_candidates=[action_candidate],
        )
        request = {
            "model": "demo-model",
            "messages": [
                {"role": "user", "content": "Read the first matching file."},
                {"role": "tool", "name": "find", "content": "{\"matches\":[\"/workspace/notes.txt\"]}"},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "cat",
                        "parameters": {
                            "type": "object",
                            "properties": {"file_name": {"type": "string"}},
                            "required": ["file_name"],
                        },
                    },
                }
            ],
        }
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": "cat", "arguments": "{\"file_name\":\"notes.txt\"}"},
                            }
                        ],
                    }
                }
            ]
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(
                rules_dir,
                runtime_policy={
                    "enable_required_next_tool_choice": True,
                    "resolve_contextual_string_args": True,
                },
            )
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)
            final_response, repairs, validation = engine.apply_response(
                patched,
                response,
                request_patches=request_patches,
            )

        self.assertEqual(repairs[0]["kind"], "resolve_contextual_string_arg")
        self.assertIn("/workspace/notes.txt", final_response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
        self.assertTrue(validation.next_tool_args_emitted)
        self.assertTrue(validation.next_tool_args_match_binding)
        self.assertTrue(validation.next_tool_args_match_binding_normalized)
        self.assertFalse(validation.next_tool_final_args_match_binding)
        self.assertTrue(validation.next_tool_final_args_match_binding_normalized)
        self.assertEqual(validation.arg_binding_validation["file_name"]["observed"], "notes.txt")
        self.assertTrue(validation.arg_binding_validation["file_name"]["match"])
        self.assertEqual(validation.final_arg_binding_validation["file_name"]["observed"], "/workspace/notes.txt")
        self.assertFalse(validation.final_arg_binding_validation["file_name"]["match"])
        self.assertTrue(validation.final_normalized_arg_binding_validation["file_name"]["match"])
        self.assertEqual(validation.final_normalized_arg_binding_validation["file_name"]["normalization"], "path_basename")

    def test_next_tool_arg_binding_validation_records_mismatch(self) -> None:
        action_candidate = {
            "tool": "move_file",
            "args": {"file_name": "report.txt"},
            "arg_bindings": {
                "file_name": {
                    "source": "explicit_literal",
                    "value": "report.txt",
                }
            },
            "recommended_tools": ["move_file"],
        }
        rule = self._next_tool_rule(recommended_tools=["move_file"], action_candidates=[action_candidate])
        request = self._make_move_file_request()
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": "move_file", "arguments": "{\"file_name\":\"wrong.txt\"}"},
                            }
                        ],
                    }
                }
            ]
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)
            _, _, validation = engine.apply_response(patched, response, request_patches=request_patches)

        self.assertTrue(validation.next_tool_args_emitted)
        self.assertFalse(validation.next_tool_args_match_binding)
        self.assertFalse(validation.next_tool_args_match_binding_normalized)
        self.assertEqual(validation.arg_binding_validation["file_name"]["observed"], "wrong.txt")
        self.assertFalse(validation.arg_binding_validation["file_name"]["match"])

    def test_next_tool_arg_binding_normalizes_path_equivalent_values(self) -> None:
        cases = [
            ("notes.txt", "/workspace/notes.txt", "file_name"),
            ("q1.txt", "./reports/q1.txt", "file_name"),
            ("goal.txt", "./goal.txt", "path"),
            ("archive", "/workspace/project/archive", "dir_name"),
        ]
        for expected, observed, field in cases:
            with self.subTest(expected=expected, observed=observed, field=field):
                rows = RuleEngine._validate_action_candidate_args_normalized(
                    {
                        "args": {field: expected},
                        "arg_bindings": {field: {"source": "fixture", "value": expected}},
                    },
                    {field: observed},
                )

                self.assertTrue(rows[field]["match"])
                self.assertFalse(rows[field]["strict_match"])
                self.assertEqual(rows[field]["normalization"], "path_basename")

    def test_next_tool_arg_binding_normalization_does_not_fuzz_non_path_fields(self) -> None:
        rows = RuleEngine._validate_action_candidate_args_normalized(
            {
                "args": {"id": "123"},
                "arg_bindings": {"id": {"source": "explicit_literal", "value": "123"}},
            },
            {"id": "abc/123"},
        )

        self.assertFalse(rows["id"]["match"])
        self.assertEqual(rows["id"]["normalization"], "unsupported_field")


    def test_next_tool_plan_ranks_action_candidates_by_request_literals(self) -> None:
        rule = self._next_tool_rule(
            recommended_tools=["mkdir", "cat"],
            request_predicates=["tools_available", "prior_explicit_literals_present"],
            activation_predicates=["tools_available", "prior_explicit_literals_present"],
            action_candidates=[
                {"tool": "mkdir", "args": {"dir_name": "archive"}, "recommended_tools": ["mkdir"]},
                {"tool": "cat", "args": {"file_name": "report.txt"}, "recommended_tools": ["cat"]},
            ],
        )
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Please read 'report.txt' and show me the contents."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "mkdir",
                        "parameters": {"type": "object", "properties": {"dir_name": {"type": "string"}}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "cat",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                },
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [rule]
            _, request_patches = engine.apply_request(request)

        self.assertIn("policy_next_tool:selected=cat", request_patches)
        self.assertIn("policy_next_tool:recommended=mkdir,cat", request_patches)


    def test_next_tool_plan_prefers_exact_arg_binding_over_generic_cat_intent(self) -> None:
        rule = self._next_tool_rule(
            recommended_tools=["cat", "mkdir"],
            request_predicates=["tools_available", "prior_explicit_literals_present"],
            activation_predicates=["tools_available", "prior_explicit_literals_present"],
            action_candidates=[
                {
                    "tool": "cat",
                    "args": {"file_name": "notes.txt"},
                    "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "notes.txt"}},
                    "recommended_tools": ["cat"],
                },
                {
                    "tool": "mkdir",
                    "args": {"dir_name": "archive"},
                    "arg_bindings": {"dir_name": {"source": "explicit_literal", "value": "archive"}},
                    "recommended_tools": ["mkdir"],
                },
            ],
        )
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Create a directory named 'archive' for the file content later."}],
            "tools": [
                {"type": "function", "function": {"name": "cat", "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}}}},
                {"type": "function", "function": {"name": "mkdir", "parameters": {"type": "object", "properties": {"dir_name": {"type": "string"}}}}},
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [rule]
            _, request_patches = engine.apply_request(request)

        self.assertIn("policy_next_tool:selected=mkdir", request_patches)

    def test_next_tool_plan_penalizes_prior_output_candidate_without_matching_state_keys(self) -> None:
        rule = self._next_tool_rule(
            recommended_tools=["cat", "mkdir"],
            request_predicates=["tools_available", "prior_tool_outputs_present"],
            activation_predicates=["tools_available", "prior_tool_outputs_present"],
            action_candidates=[
                {
                    "tool": "cat",
                    "args": {"file_name": "result.txt"},
                    "arg_bindings": {
                        "file_name": {
                            "source": "prior_tool_output.matches[0]|basename",
                            "value": "result.txt",
                            "evidence": {"prior_output_keys": ["matches"]},
                        }
                    },
                    "recommended_tools": ["cat"],
                },
                {
                    "tool": "mkdir",
                    "args": {"dir_name": "archive"},
                    "arg_bindings": {"dir_name": {"source": "explicit_literal", "value": "archive"}},
                    "recommended_tools": ["mkdir"],
                },
            ],
        )
        request = {
            "model": "demo-model",
            "messages": [
                {"role": "user", "content": "Create folder 'archive'."},
                {"role": "tool", "content": json.dumps({"current_working_directory": "/tmp"})},
            ],
            "tools": [
                {"type": "function", "function": {"name": "cat", "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}}}},
                {"type": "function", "function": {"name": "mkdir", "parameters": {"type": "object", "properties": {"dir_name": {"type": "string"}}}}},
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [rule]
            _, request_patches = engine.apply_request(request)

        self.assertIn("policy_next_tool:selected=mkdir", request_patches)

    def test_next_tool_plan_source_trace_style_requests_select_multiple_tools(self) -> None:
        rule = self._next_tool_rule(
            recommended_tools=["cat", "mkdir", "touch"],
            request_predicates=["tools_available", "prior_explicit_literals_present"],
            activation_predicates=["tools_available", "prior_explicit_literals_present"],
            action_candidates=[
                {"tool": "cat", "args": {"file_name": "report.txt"}, "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "report.txt"}}, "recommended_tools": ["cat"]},
                {"tool": "mkdir", "args": {"dir_name": "archive"}, "arg_bindings": {"dir_name": {"source": "explicit_literal", "value": "archive"}}, "recommended_tools": ["mkdir"]},
                {"tool": "touch", "args": {"file_name": "todo.txt"}, "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "todo.txt"}}, "recommended_tools": ["touch"]},
            ],
        )
        requests = [
            "Read 'report.txt' and show me the content.",
            "Create a directory named 'archive'.",
            "Create an empty file named 'todo.txt'.",
        ]
        selected = []
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [rule]
            for content in requests:
                request = {
                    "model": "demo-model",
                    "messages": [{"role": "user", "content": content}],
                    "tools": [
                        {"type": "function", "function": {"name": "cat", "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}}}},
                        {"type": "function", "function": {"name": "mkdir", "parameters": {"type": "object", "properties": {"dir_name": {"type": "string"}}}}},
                        {"type": "function", "function": {"name": "touch", "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}}}},
                    ],
                }
                _, request_patches = engine.apply_request(request)
                selected.append(next(item.split("=", 1)[1] for item in request_patches if item.startswith("policy_next_tool:selected=")))

        self.assertEqual(set(selected), {"cat", "mkdir", "touch"})

    def test_true_empty_tool_call_still_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                        }
                    }
                ]
            }

            _, _, validation = engine.apply_response(request, response)

        self.assertEqual([issue.kind for issue in validation.issues], ["empty_tool_call"])



    def test_guidance_only_adds_action_specific_guidance_without_exact_tool_choice(self) -> None:
        action_candidate = {
            "tool": "move_file",
            "args": {"file_name": "report.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "report.txt"}},
            "recommended_tools": ["move_file"],
        }
        rule = self._next_tool_rule(recommended_tools=["move_file"], action_candidates=[action_candidate])
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"exact_next_tool_choice_mode": "guidance_only"})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(self._make_move_file_request())

        self.assertNotIn("tool_choice", patched)
        self.assertNotIn("tool_choice:function(policy_next_tool)=move_file", request_patches)
        system_text = patched["messages"][0]["content"]
        self.assertIn("Policy selected next tool: call `move_file` next", system_text)
        self.assertIn('"file_name": "report.txt"', system_text)
        self.assertIn("binding sources: explicit_literal", system_text)
        self.assertTrue(any(str(patch).startswith("prompt_injector:Policy selected next tool:") for patch in request_patches))

    def test_off_mode_skips_action_specific_guidance_and_exact_tool_choice(self) -> None:
        action_candidate = {
            "tool": "move_file",
            "args": {"file_name": "report.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "report.txt"}},
            "recommended_tools": ["move_file"],
        }
        rule = self._next_tool_rule(recommended_tools=["move_file"], action_candidates=[action_candidate])
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"exact_next_tool_choice_mode": "off"})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(self._make_move_file_request())

        self.assertNotIn("tool_choice", patched)
        self.assertNotIn("tool_choice:function(policy_next_tool)=move_file", request_patches)
        self.assertFalse(any(str(patch).startswith("prompt_injector:Policy selected next tool:") for patch in request_patches))
        self.assertNotIn("Policy selected next tool: call `move_file` next", patched["messages"][0]["content"])

    def test_conditional_exact_next_tool_choice_requires_low_trajectory_risk(self) -> None:
        action_candidate = {
            "tool": "move_file",
            "args": {"file_name": "report.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "report.txt"}},
            "recommended_tools": ["move_file"],
        }
        rule = self._next_tool_rule(recommended_tools=["move_file"], action_candidates=[action_candidate])
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"exact_next_tool_choice_mode": "exact_tool_when_single_step_confident"})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(self._make_move_file_request())

        self.assertEqual(patched["tool_choice"], {"type": "function", "function": {"name": "move_file"}})
        self.assertIn("tool_choice:function(policy_next_tool)=move_file", request_patches)
        self.assertTrue(any(str(patch).startswith("prompt_injector:Policy selected next tool:") for patch in request_patches))

    def test_conditional_exact_next_tool_choice_downgrades_trajectory_sensitive_tools(self) -> None:
        action_candidate = {
            "tool": "cat",
            "args": {"file_name": "report.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "report.txt"}},
            "recommended_tools": ["cat"],
        }
        rule = self._next_tool_rule(recommended_tools=["cat"], action_candidates=[action_candidate])
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Show 'report.txt'."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "cat",
                        "parameters": {
                            "type": "object",
                            "properties": {"file_name": {"type": "string"}},
                            "required": ["file_name"],
                        },
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"exact_next_tool_choice_mode": "exact_tool_when_single_step_confident"})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        self.assertIn("tool_choice:function(policy_next_tool):skipped=cat", request_patches)
        self.assertTrue(any(str(patch).startswith("prompt_injector:Policy selected next tool:") for patch in request_patches))

    def test_action_specific_guidance_is_not_added_for_guard_rejected_candidate(self) -> None:
        action_candidate = {
            "tool": "touch",
            "args": {"file_name": "marker.txt"},
            "binding_source": "prior_tool_output.cwd_or_listing",
            "arg_bindings": {"file_name": {"source": "prior_tool_output.cwd_or_listing", "value": "marker.txt"}},
            "recommended_tools": ["touch"],
        }
        rule = self._next_tool_rule(
            recommended_tools=["touch"],
            request_predicates=["tools_available"],
            activation_predicates=["tools_available"],
            action_candidates=[action_candidate],
        )
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Create a marker when appropriate."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "touch",
                        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}},
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"exact_next_tool_choice_mode": "guidance_only"})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        self.assertFalse(any(str(patch).startswith("prompt_injector:Policy selected next tool:") for patch in request_patches))
        self.assertEqual(request_patches.next_tool_plan["blocked_reason"], "action_candidate_guard_rejected")

    def test_exact_next_tool_choice_preserves_existing_tool_choice(self) -> None:
        action_candidate = {
            "tool": "move_file",
            "args": {"file_name": "report.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "report.txt"}},
            "recommended_tools": ["move_file"],
        }
        rule = self._next_tool_rule(recommended_tools=["move_file"], action_candidates=[action_candidate])
        request = self._make_move_file_request()
        request["tool_choice"] = "auto"
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"exact_next_tool_choice_mode": "exact_tool_when_single_step_confident"})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertEqual(patched["tool_choice"], "auto")
        self.assertNotIn("tool_choice:function(policy_next_tool)=move_file", request_patches)
        self.assertTrue(any(str(patch).startswith("prompt_injector:Policy selected next tool:") for patch in request_patches))


    def test_scorer_feedback_downgrades_matching_candidate_to_record_only(self) -> None:
        action_candidate = {
            "tool": "cat",
            "args": {"file_name": "a.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "a.txt"}},
            "recommended_tools": ["cat"],
        }
        rule = self._next_tool_rule(recommended_tools=["cat"], action_candidates=[action_candidate])
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Read 'a.txt'."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "cat",
                        "parameters": {
                            "type": "object",
                            "properties": {"file_name": {"type": "string"}},
                            "required": ["file_name"],
                        },
                    },
                }
            ],
        }
        feedback = {
            "m27y_scorer_feedback_ready": True,
            "blocked_candidate_signatures": [{"tool": "cat", "args": {"file_name": "a.txt"}}],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(
                rules_dir,
                runtime_policy={"exact_next_tool_choice_mode": "guidance_only", "scorer_feedback": feedback},
            )
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        self.assertFalse(any(str(patch).startswith("prompt_injector:Policy selected next tool:") for patch in request_patches))
        self.assertEqual(request_patches.next_tool_plan["blocked_reason"], "action_candidate_guard_rejected")
        rejected = request_patches.next_tool_plan["rejected_action_candidates"][0]
        self.assertEqual(rejected["guard"]["intervention_mode"], "record_only")
        self.assertIn("scorer_feedback_record_only", rejected["guard"]["risk_flags"])


    def test_scorer_feedback_pattern_downgrades_matching_candidate(self) -> None:
        action_candidate = {
            "tool": "cat",
            "args": {"file_name": "b.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "b.txt"}},
            "postcondition": {"kind": "file_content"},
            "recommended_tools": ["cat"],
        }
        rule = self._next_tool_rule(recommended_tools=["cat"], action_candidates=[action_candidate])
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Read 'b.txt'."}],
            "tools": [{"type": "function", "function": {"name": "cat", "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}, "required": ["file_name"]}}}],
        }
        feedback = {
            "m27y_scorer_feedback_ready": True,
            "blocked_regression_patterns": [
                {
                    "selected_tool_family": "read_content",
                    "postcondition_family": "read_content",
                    "binding_source": "explicit_literal",
                    "trajectory_risk_flags": ["trajectory_sensitive_tool"],
                    "action": "record_only",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"exact_next_tool_choice_mode": "guidance_only", "scorer_feedback": feedback})
            engine.rules = [rule]
            patched, request_patches = engine.apply_request(request)

        self.assertNotIn("tool_choice", patched)
        self.assertFalse(any(str(patch).startswith("prompt_injector:Policy selected next tool:") for patch in request_patches))
        rejected = request_patches.next_tool_plan["rejected_action_candidates"][0]
        self.assertEqual(rejected["guard"]["intervention_mode"], "record_only")
        self.assertIn("scorer_feedback_record_only", rejected["guard"]["risk_flags"])
        self.assertEqual(rejected["tool"], "cat")
        self.assertTrue(rejected["scorer_feedback_pattern_matched"])
        self.assertEqual(rejected["matched_regression_guard_key"], None)
        self.assertEqual(rejected["scorer_feedback_pattern_action"], "record_only")
        self.assertEqual(rejected["scorer_feedback_reason"], "m27aa_pattern_regression_guard")


    def test_scorer_feedback_diagnostic_pattern_observes_without_blocking(self) -> None:
        action_candidate = {
            "tool": "cat",
            "args": {"file_name": "b.txt"},
            "binding_source": "explicit_literal",
            "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "b.txt"}},
            "postcondition": {"kind": "file_content"},
            "recommended_tools": ["cat"],
        }
        rule = self._next_tool_rule(recommended_tools=["cat"], action_candidates=[action_candidate])
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Read 'b.txt'."}],
            "tools": [{"type": "function", "function": {"name": "cat", "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}, "required": ["file_name"]}}}],
        }
        feedback = {
            "m27y_scorer_feedback_ready": True,
            "blocked_regression_patterns": [
                {
                    "selected_tool_family": "read_content",
                    "postcondition_family": "read_content",
                    "binding_source": "explicit_literal",
                    "trajectory_risk_flags": ["trajectory_sensitive_tool"],
                    "action": "diagnostic_only",
                    "regression_guard_key": "pattern-key",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"exact_next_tool_choice_mode": "guidance_only", "scorer_feedback": feedback})
            engine.rules = [rule]
            _, request_patches = engine.apply_request(request)

        self.assertTrue(request_patches.next_tool_plan["activated"])
        selected = request_patches.next_tool_plan["selected_action_candidate"]
        self.assertEqual(selected["tool"], "cat")
        self.assertTrue(selected["scorer_feedback_pattern_matched"])
        self.assertEqual(selected["matched_regression_guard_key"], "pattern-key")
        self.assertEqual(selected["scorer_feedback_pattern_action"], "diagnostic_only")

    def test_scorer_feedback_pattern_does_not_block_non_matching_candidate(self) -> None:
        action_candidate = {
            "tool": "cp",
            "args": {"source": "a.txt", "destination": "b.txt"},
            "binding_source": "explicit_literal_pair",
            "arg_bindings": {
                "source": {"source": "explicit_literal_pair", "value": "a.txt"},
                "destination": {"source": "explicit_literal_pair", "value": "b.txt"},
            },
            "postcondition": {"kind": "target_path_changed"},
            "trajectory_risk_flags": [],
            "pending_goal_family": "move_or_copy",
            "recommended_tools": ["cp"],
        }
        rule = self._next_tool_rule(recommended_tools=["cp"], action_candidates=[action_candidate])
        request = {
            "model": "demo-model",
            "messages": [{"role": "user", "content": "Copy 'a.txt' to 'b.txt'."}],
            "tools": [{"type": "function", "function": {"name": "cp", "parameters": {"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}, "required": ["source", "destination"]}}}],
        }
        feedback = {"m27y_scorer_feedback_ready": True, "blocked_regression_patterns": [{"selected_tool_family": "read_content", "postcondition_family": "read_content", "binding_source": "explicit_literal"}]}
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir, runtime_policy={"exact_next_tool_choice_mode": "guidance_only", "scorer_feedback": feedback})
            engine.rules = [rule]
            _, request_patches = engine.apply_request(request)

        self.assertTrue(any(str(patch).startswith("prompt_injector:Policy selected next tool:") for patch in request_patches))
        self.assertEqual(request_patches.next_tool_plan["selected_action_candidate"]["tool"], "cp")

if __name__ == "__main__":
    unittest.main()
