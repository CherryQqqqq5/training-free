from __future__ import annotations

import unittest

from grc.compiler.failure_signature import signature_from_failure, tool_schema_hash, top_k_signatures
from grc.types import FailureCase


class FailureSignatureTests(unittest.TestCase):
    def test_tool_schema_hash_is_deterministic(self) -> None:
        payload = {"a": 1, "b": {"x": True}}
        self.assertEqual(tool_schema_hash(payload), tool_schema_hash({"b": {"x": True}, "a": 1}))

    def test_signature_uses_literals_pattern(self) -> None:
        failure = FailureCase(
            trace_id="t1",
            turn_index=0,
            tool_name="__none__",
            error_type="actionable_no_tool_decision",
            stage="PRE_TOOL",
            failure_type="ACTIONABLE_NO_TOOL_DECISION",
            request_literals=["report.txt"],
        )
        signature = signature_from_failure(failure)
        self.assertEqual(signature.literals_pattern, "explicit_context_literals")

    def test_top_k_signatures_aggregates(self) -> None:
        failures = [
            FailureCase(trace_id="t1", turn_index=0, tool_name="__none__", error_type="x", stage="PRE_TOOL", failure_type="ACTIONABLE_NO_TOOL_DECISION", failure_label="(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)"),
            FailureCase(trace_id="t2", turn_index=0, tool_name="__none__", error_type="x", stage="PRE_TOOL", failure_type="ACTIONABLE_NO_TOOL_DECISION", failure_label="(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)"),
        ]
        summaries = top_k_signatures(failures, k=1)
        self.assertEqual(summaries[0].count, 2)
        self.assertEqual(summaries[0].failure_labels, ["(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)"])
