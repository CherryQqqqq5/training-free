from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict


class TraceStore:
    def __init__(self, trace_dir: str):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def write(self, payload: Dict[str, Any]) -> str:
        trace_id = payload.get("trace_id") or str(uuid.uuid4())
        payload["trace_id"] = trace_id
        path = self.trace_dir / f"{trace_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return trace_id

