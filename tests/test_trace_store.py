from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from grc.runtime.trace_store import TraceStore


class TraceStoreTests(unittest.TestCase):
    def test_write_recreates_missing_trace_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            trace_dir = Path(tmpdir) / "traces"
            store = TraceStore(str(trace_dir))
            trace_dir.rmdir()

            trace_id = store.write({"status_code": 200})

            payload = json.loads((trace_dir / f"{trace_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["trace_id"], trace_id)
            self.assertEqual(payload["status_code"], 200)


if __name__ == "__main__":
    unittest.main()
