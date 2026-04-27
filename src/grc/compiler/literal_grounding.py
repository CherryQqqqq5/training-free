"""Literal grounding helpers for theory-guided argument completion.

These helpers intentionally distinguish observable prompt/observation evidence
from source-result tool args. A source-result value can be used as the target to
audit, but it is retain-eligible only when the same value is grounded in current
request/observation text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CURRENT_CONTEXT_SOURCES = {"current_request", "current_observation", "current_request_or_current_observation"}
FILE_LIKE_RE = re.compile(r"\b[\w.-]+\.(?:txt|pdf|csv|json|py|java|js|md|log|xml|ya?ml|docx?)\b", re.IGNORECASE)


@dataclass(frozen=True)
class LiteralGrounding:
    candidate_literals: list[str]
    selected_literal: str | None
    literal_source: str | None
    source_span: str | None
    disambiguation_cue: str | None
    why_rejected: str | None
    schema_type_match: bool
    literal_uniqueness: bool

    @property
    def retain_prior_candidate(self) -> bool:
        return self.selected_literal is not None and self.schema_type_match and self.literal_uniqueness and self.literal_source in CURRENT_CONTEXT_SOURCES


def scalar(value: Any) -> str | None:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        text = str(value).strip()
        return text if text else None
    return None


def schema_type(schema: dict[str, Any]) -> str:
    return str(schema.get("type") or "string").lower()


def schema_type_match(value: Any, schema: dict[str, Any]) -> bool:
    text = scalar(value)
    if text is None:
        return False
    typ = schema_type(schema)
    if typ == "integer":
        return re.fullmatch(r"-?\d+", text) is not None
    if typ == "number":
        return re.fullmatch(r"-?\d+(?:\.\d+)?", text) is not None
    if typ == "boolean":
        return text.lower() in {"true", "false", "yes", "no"}
    if typ in {"array", "object"}:
        return False
    return True


def contains_literal(text: str, literal: str) -> bool:
    if not literal:
        return False
    if re.fullmatch(r"-?\d+(?:\.\d+)?", literal) or not any(ch in literal for ch in ".-/"):
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(literal) + r"(?![A-Za-z0-9_])"
    else:
        pattern = r"(?<![\w.-])" + re.escape(literal) + r"(?![\w.-])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def number_literals(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z0-9_])-?\d+(?:\.\d+)?(?![A-Za-z0-9_])", text)


def quoted_literals(text: str) -> list[str]:
    return [m.group(1) or m.group(2) for m in re.finditer(r"'([^']+)'|\"([^\"]+)\"", text)]


def file_like_literals(text: str) -> list[str]:
    return FILE_LIKE_RE.findall(text)


def _bare_identifier_literals(text: str) -> list[str]:
    # Directory/tool benchmarks often use unquoted CamelCase or snake_case names.
    values = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b", text)
    stop = {"the", "and", "for", "with", "into", "from", "file", "directory", "folder", "please", "move", "copy", "create", "search", "grep", "sort", "compare"}
    return [value for value in values if value.lower() not in stop]


def typed_literals(text: str, schema: dict[str, Any], literal_value: str | None = None, *, required_arg: str | None = None) -> list[str]:
    typ = schema_type(schema)
    if typ in {"integer", "number"}:
        candidates = number_literals(text)
    elif typ == "boolean":
        raw = re.findall(r"\b(?:true|false|yes|no)\b", text, flags=re.IGNORECASE)
        candidates = ["true" if item.lower() in {"true", "yes"} else "false" for item in raw]
    else:
        candidates = quoted_literals(text) + file_like_literals(text)
        if _is_directory_arg(required_arg or ""):
            candidates += [value for value in _bare_identifier_literals(text) if "." not in value]
    if literal_value and contains_literal(text, literal_value):
        candidates.append(literal_value)
    unique: list[str] = []
    for value in candidates:
        text_value = str(value).strip()
        if text_value and text_value not in unique:
            unique.append(text_value)
    return unique


def _is_file_arg(arg: str) -> bool:
    return arg in {"file", "file_name", "filename", "source", "src", "from"} or arg.endswith("_file")


def _is_directory_arg(arg: str) -> bool:
    return arg in {"folder", "dir", "dir_name", "directory", "path", "destination", "dest", "target", "to"}


def _cue_for_known_literal(text: str, literal: str, required_arg: str, tool: str) -> str | None:
    if not contains_literal(text, literal):
        return None
    arg = required_arg.lower()
    window = 70
    escaped = re.escape(literal)
    if arg in {"file_name", "filename", "file"} and FILE_LIKE_RE.fullmatch(literal):
        return "file_name_exact_prompt_literal"
    if arg in {"source", "src", "from"} and FILE_LIKE_RE.fullmatch(literal):
        return "source_file_exact_prompt_literal"
    if arg in {"destination", "dest", "target", "to"}:
        if re.search(r"\b(?:to|into|as|rename(?:d)? to|move(?:d)? to|copy(?:ied)? to)\b[^.\n]{0,%d}%s" % (window, escaped), text, flags=re.IGNORECASE):
            return "destination_cue_exact_prompt_literal"
        if contains_literal(text, literal):
            return "destination_exact_prompt_literal"
    if arg in {"folder", "dir", "dir_name", "directory", "path"}:
        if re.search(r"\b(?:folder|directory|path|cd|within|inside|into)\b[^.\n]{0,%d}%s" % (window, escaped), text, flags=re.IGNORECASE):
            return "directory_cue_exact_prompt_literal"
        return "directory_exact_prompt_literal"
    if arg in {"pattern", "query", "term", "name"}:
        if re.search(r"(?:'|\")" + escaped + r"(?:'|\")", text):
            return "quoted_pattern_exact_prompt_literal"
        if re.search(r"\b(?:pattern|term|search|grep|find|named?)\b[^.\n]{0,%d}%s" % (window, escaped), text, flags=re.IGNORECASE):
            return "pattern_cue_exact_prompt_literal"
    if re.search(re.escape(required_arg) + r"\D{0,30}" + escaped, text, flags=re.IGNORECASE):
        return "schema_arg_name_near_literal"
    if re.fullmatch(r"-?\d+(?:\.\d+)?", literal):
        return None
    if contains_literal(text, literal):
        return "exact_prompt_literal"
    return None


def _select_by_arg_cue(candidates: list[str], text: str, required_arg: str) -> tuple[str | None, str | None]:
    arg = required_arg.lower()
    if not candidates:
        return None, None
    if len(candidates) == 1:
        return candidates[0], "single_typed_literal"
    if arg in {"file_name", "filename", "file", "source", "src", "from"}:
        files = [value for value in candidates if FILE_LIKE_RE.fullmatch(value)]
        return (files[0], "single_file_like_literal") if len(files) == 1 else (None, None)
    if arg in {"folder", "dir", "dir_name", "directory", "path"}:
        dirs = [value for value in candidates if not FILE_LIKE_RE.fullmatch(value)]
        if len(dirs) == 1:
            return dirs[0], "single_directory_like_literal"
    if arg in {"pattern", "query", "term", "name"}:
        quoted = [value for value in quoted_literals(text) if value in candidates]
        if len(quoted) == 1:
            return quoted[0], "single_quoted_pattern_literal"
    # Numeric/schema-name cue: choose literal closest after the arg name.
    for value in candidates:
        if re.search(re.escape(required_arg) + r"\D{0,30}" + re.escape(value), text, flags=re.IGNORECASE):
            return value, "schema_arg_name_near_literal"
    return None, None


def ground_literal(
    request_text: str,
    observation_text: str,
    schema: dict[str, Any],
    required_arg: str,
    tool: str,
    literal_value: Any | None = None,
    *,
    exclude_values: set[str] | None = None,
) -> LiteralGrounding:
    literal = scalar(literal_value)
    schema_ok = schema_type_match(literal, schema) if literal is not None else True
    request_candidates = typed_literals(request_text, schema, literal, required_arg=required_arg)
    observation_candidates = typed_literals(observation_text, schema, literal, required_arg=required_arg)
    excluded = exclude_values or set()
    candidates = [value for value in request_candidates + observation_candidates if value not in excluded]
    unique_candidates: list[str] = []
    for value in candidates:
        if value not in unique_candidates:
            unique_candidates.append(value)

    if literal is not None:
        if not schema_ok:
            return LiteralGrounding(unique_candidates, None, None, None, None, "schema_mismatch", False, False)
        cue = _cue_for_known_literal(request_text, literal, required_arg.lower(), tool.lower())
        source = "current_request" if cue else None
        if not cue:
            obs_cue = _cue_for_known_literal(observation_text, literal, required_arg.lower(), tool.lower())
            if obs_cue:
                cue = obs_cue
                source = "current_observation"
        if cue and source:
            return LiteralGrounding(unique_candidates, literal, source, source, cue, None, True, True)
        if literal in unique_candidates:
            return LiteralGrounding(unique_candidates, None, None, None, None, "ambiguous", True, False)
        return LiteralGrounding(unique_candidates, None, None, None, None, "source_result_only", True, False)

    selected, cue = _select_by_arg_cue(unique_candidates, request_text + "\n" + observation_text, required_arg)
    if selected:
        source = "current_request" if selected in request_candidates else "current_observation"
        return LiteralGrounding(unique_candidates, selected, source, source, cue, None, True, True)
    reason = "ambiguous" if unique_candidates else "no_prompt_literal"
    return LiteralGrounding(unique_candidates, None, None, None, None, reason, True, False)
