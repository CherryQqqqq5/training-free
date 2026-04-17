from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

_INJECTED_YAML_STUB = False
try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    sys.modules["yaml"] = types.SimpleNamespace(
        safe_dump=lambda data, **_: json.dumps(data, ensure_ascii=False, indent=2),
        safe_load=json.loads,
    )
    _INJECTED_YAML_STUB = True

from grc.compiler.trace_to_patch import compile_patch

if _INJECTED_YAML_STUB:
    sys.modules.pop("yaml", None)


def _load_bundle(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml

        return yaml.safe_load(text)
    except ModuleNotFoundError:
        return json.loads(text)


class TraceToPatchTests(unittest.TestCase):
    def test_compile_patch_emits_global_hallucinated_completion_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text(
                json.dumps(
                    {
                        "trace_id": "trace_1",
                        "turn_index": 0,
                        "tool_name": "__none__",
                        "error_type": "hallucinated_completion",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            compile_patch(str(failure_path), str(out_path), patch_id="patch_hallucinated_v1")
            bundle = _load_bundle(out_path)

        self.assertEqual(bundle["patch_id"], "patch_hallucinated_v1")
        self.assertEqual(bundle["source_failure_count"], 1)
        self.assertEqual(len(bundle["rules"]), 1)

        rule = bundle["rules"][0]
        self.assertEqual(rule["rule_id"], "rule_global_tool_guard_v1")
        self.assertEqual(
            rule["action"]["fallback_router"]["strategy"],
            "assistant_message",
        )
        self.assertEqual(
            rule["action"]["fallback_router"]["on_issue_kinds"],
            ["hallucinated_completion"],
        )
        self.assertIn(
            "Do not claim that work has already started or completed",
            rule["action"]["prompt_fragments"][0],
        )


if __name__ == "__main__":
    unittest.main()
