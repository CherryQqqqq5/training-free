from __future__ import annotations

import ast
import json
import re
from typing import Any


def strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_loose_json(text: str) -> Any:
    text = strip_code_fence(text)
    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        return ast.literal_eval(text)
    except Exception:
        pass

    raise ValueError(f"cannot parse arguments as JSON-like object: {text[:200]}")

