from __future__ import annotations

import ast
import re
from typing import Any, Dict, List


_CALL_BLOCK_RE = re.compile(r"\[(.*)\]", re.DOTALL)


def _split_top_level(text: str, sep: str = ",") -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    in_str = False
    quote = ""
    escaped = False
    for ch in text:
        if in_str:
            current.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                in_str = False
            continue
        if ch in ("'", '"'):
            in_str = True
            quote = ch
            current.append(ch)
            continue
        if ch in "([{":
            depth += 1
            current.append(ch)
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            current.append(ch)
            continue
        if ch == sep and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if not raw:
        return ""
    try:
        return ast.literal_eval(raw)
    except Exception:
        return raw.strip("'\"")


def parse_text_tool_calls(content: str) -> List[Dict[str, Any]]:
    if not isinstance(content, str):
        return []
<<<<<<< HEAD
    m = _CALL_BLOCK_RE.search(content.strip())
    if not m:
        return []
    inner = m.group(1).strip()
=======
    match = _CALL_BLOCK_RE.search(content.strip())
    if not match:
        return []
    inner = match.group(1).strip()
>>>>>>> exp-results
    if not inner:
        return []

    calls: List[Dict[str, Any]] = []
    for call_expr in _split_top_level(inner, sep=","):
        call_expr = call_expr.strip()
        if "(" not in call_expr or not call_expr.endswith(")"):
            continue
        name, args_part = call_expr.split("(", 1)
        tool_name = name.strip()
        args_part = args_part[:-1].strip()
        if not tool_name:
            continue

        args_obj: Dict[str, Any] = {}
        if args_part:
            for arg_expr in _split_top_level(args_part, sep=","):
                if "=" not in arg_expr:
                    continue
                key, value = arg_expr.split("=", 1)
                key = key.strip()
                if not key:
                    continue
                args_obj[key] = _parse_value(value)

        calls.append(
            {
                "id": f"textcall_{len(calls)}",
                "type": "function",
                "function": {"name": tool_name, "arguments": args_obj},
            }
        )
    return calls


def looks_like_terminal_natural_language(content: str) -> bool:
    if not isinstance(content, str):
        return False
    lowered = content.strip().lower()
    if not lowered:
        return False
    terminal_markers = (
        "i'm done",
        "i am done",
        "task is complete",
        "completed",
        "no further functions",
        "no more functions",
        "nothing else to do",
    )
    return any(marker in lowered for marker in terminal_markers)
