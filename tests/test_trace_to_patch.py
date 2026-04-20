from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from unittest.mock import patch

from grc.compiler.trace_to_patch import compile_patch


class TraceToPatchTests(unittest.TestCase):
    def test_compile_patch_no_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text("", encoding="utf-8")

            status = compile_patch(str(failure_path), str(out_path), patch_id="patch_none", candidate_dir=str(root / "cand"))

            self.assertEqual(status["status"], "no_failure_evidence")
            compile_status = json.loads((root / "cand" / "compile_status.json").read_text(encoding="utf-8"))
            self.assertEqual(compile_status["status"], "no_failure_evidence")

    def test_compile_patch_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text(
                json.dumps({"trace_id": "t1", "turn_index": 0, "tool_name": "demo_tool", "error_type": "missing_required", "field_name": "id", "expected_type": "string"}) + "\n",
                encoding="utf-8",
            )

            status = compile_patch(str(failure_path), str(out_path), patch_id="patch_ok", candidate_dir=str(root / "cand"))

            self.assertEqual(status["status"], "actionable_patch")
            self.assertGreater(status["rule_count"], 0)

    def test_compile_patch_uncompilable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text(
                json.dumps({"trace_id": "t1", "turn_index": 0, "tool_name": "demo_tool", "error_type": "missing_required", "field_name": "id", "expected_type": "string"}) + "\n",
                encoding="utf-8",
            )

            with patch("grc.compiler.trace_to_patch._build_failure_ir", return_value=[]):
                status = compile_patch(str(failure_path), str(out_path), patch_id="patch_uncompilable", candidate_dir=str(root / "cand"))

            self.assertEqual(status["status"], "uncompilable_failure_evidence")
            self.assertIn("missing_required", status["high_value_error_types"])

    def test_compile_patch_compile_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text("not-json\n", encoding="utf-8")

            status = compile_patch(str(failure_path), str(out_path), patch_id="patch_fail", candidate_dir=str(root / "cand"))

            self.assertEqual(status["status"], "compile_failed")


if __name__ == "__main__":
    unittest.main()
