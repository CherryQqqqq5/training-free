from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
