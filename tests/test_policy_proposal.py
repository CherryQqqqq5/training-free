from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from grc.compiler.policy_proposal import generate_proposals


class PolicyProposalTests(unittest.TestCase):
    def test_generates_fresh_and_reuse_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failures = root / "failures.jsonl"
            history = root / "history.jsonl"
            out_dir = root / "out"
            failures.write_text(
                json.dumps(
                    {
                        "trace_id": "trace_1",
                        "turn_index": 0,
                        "tool_name": "__none__",
                        "error_type": "actionable_no_tool_decision",
                        "stage": "PRE_TOOL",
                        "failure_type": "ACTIONABLE_NO_TOOL_DECISION",
                        "failure_label": "(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)",
                        "request_predicates": ["tools_available"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            history.write_text(
                json.dumps(
                    {
                        "patch_id": "patch_old",
                        "reusable_for_search": True,
                        "request_predicates": ["tools_available"],
                        "policy_fingerprints": ["fp1"],
                        "error_families": ["actionable_no_tool_decision"],
                        "failure_signatures": [{"stage": "PRE_TOOL", "type": "ACTIONABLE_NO_TOOL_DECISION", "tool_schema_hash": "*", "literals_pattern": "no_explicit_literals"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            summary = generate_proposals(failures, history, out_dir)
            self.assertGreaterEqual(summary["proposal_count"], 2)
            self.assertTrue((out_dir / "fresh_00" / "proposal_metadata.json").exists())
            self.assertTrue((out_dir / "reuse_00_patch_old" / "proposal_metadata.json").exists())
            self.assertTrue((out_dir / "reuse_00_patch_old" / "rule.yaml").exists())
            self.assertEqual(
                json.loads((out_dir / "reuse_00_patch_old" / "compile_status.json").read_text(encoding="utf-8"))["status"],
                "actionable_patch",
            )
            self.assertTrue((out_dir / "specialize_00_patch_old" / "rule.yaml").exists())
            self.assertEqual(
                json.loads((out_dir / "specialize_00_patch_old" / "compile_status.json").read_text(encoding="utf-8"))["status"],
                "actionable_patch",
            )
