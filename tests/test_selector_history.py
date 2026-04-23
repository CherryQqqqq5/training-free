from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from grc.selector.history import append_history_record, retrieve


class SelectorHistoryTests(unittest.TestCase):
    def test_appends_and_retrieves_by_failure_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_dir = root / "candidate"
            candidate_dir.mkdir()
            (candidate_dir / "policy_unit.yaml").write_text(
                """
policy_units:
  - name: policy_demo
    trigger:
      error_types: [actionable_no_tool_decision]
      request_predicates: [tools_available]
    source_failure_signature:
      stage: PRE_TOOL
      type: ACTIONABLE_NO_TOOL_DECISION
      tool_schema_hash: "*"
      literals_pattern: explicit_context_literals
""",
                encoding="utf-8",
            )
            history_path = candidate_dir / "history.jsonl"

            record = append_history_record(
                history_path,
                {"decision_code": "retained", "accept": False, "target_delta": 3.0, "candidate": {"acc": 40.0}},
                str(candidate_dir),
            )
            matches = retrieve(
                history_path,
                {"stage": "PRE_TOOL", "type": "ACTIONABLE_NO_TOOL_DECISION"},
            )
            history_text = history_path.read_text(encoding="utf-8")

        self.assertEqual(record["decision_code"], "retained")
        self.assertEqual(record["error_families"], ["actionable_no_tool_decision"])
        self.assertEqual(len(matches), 1)
        self.assertEqual(json.loads(history_text)["decision_code"], "retained")
