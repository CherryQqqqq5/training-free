from __future__ import annotations

import unittest

from grc.compiler.failure_taxonomy import (
    FailureStage,
    FailureType,
    classify_error_type,
    classify_no_tool_failure,
    has_sufficient_literals,
    is_clarification,
    tool_output_sufficient,
)


class FailureTaxonomyTests(unittest.TestCase):
    def test_classifies_actionable_pre_tool_no_tool_decision(self) -> None:
        classification = classify_no_tool_failure(
            base_kind="empty_tool_call",
            content="The file exists.",
            tools_available=True,
            literal_evidence=True,
            tool_output_evidence=False,
        )

        self.assertEqual(classification.stage, FailureStage.PRE_TOOL)
        self.assertEqual(classification.failure_type, FailureType.ACTIONABLE_NO_TOOL_DECISION)
        self.assertEqual(classification.error_type, "actionable_no_tool_decision")
        self.assertEqual(classification.label, "(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)")

    def test_classifies_post_tool_prose_context_as_post_tool_actionable(self) -> None:
        classification = classify_no_tool_failure(
            base_kind="natural_language_termination",
            content="I found the file and it contains the requested data.",
            tools_available=True,
            literal_evidence=False,
            tool_output_evidence=True,
        )

        self.assertEqual(classification.stage, FailureStage.POST_TOOL)
        self.assertEqual(classification.failure_type, FailureType.ACTIONABLE_NO_TOOL_DECISION)
        self.assertIn("prior_tool_outputs_present", classification.request_predicates)

    def test_clarification_predicate_requires_question_and_missing_info_request(self) -> None:
        self.assertTrue(is_clarification("Could you please provide the file name?"))
        self.assertFalse(is_clarification("I found the file."))

    def test_literal_and_tool_output_predicates_are_reproducible(self) -> None:
        context = [{"role": "user", "content": "Read report.txt in data/input."}]
        output = [{"role": "tool", "content": "{\"path\":\"report.txt\"}"}]

        self.assertTrue(has_sufficient_literals(context))
        self.assertTrue(tool_output_sufficient(output))

    def test_maps_schema_failures_to_mid_tool_taxonomy(self) -> None:
        self.assertEqual(classify_error_type("missing_required").failure_type, FailureType.ARG_UNDERSPECIFIED)
        self.assertEqual(classify_error_type("type_mismatch").failure_type, FailureType.MALFORMED_CALL)
        self.assertEqual(classify_error_type("type_mismatch").stage, FailureStage.MID_TOOL)
