"""Offline-only sanitized step trace buffer for RASHE skeleton tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schema import PATH_INDICATORS, find_forbidden_fields, has_raw_case_id

REQUIRED_ZERO_TRACE_KEYS = (
    "provider_call_count",
    "scorer_call_count",
    "source_collection_call_count",
)

REQUIRED_V0_2_TRACE_FIELDS = (
    "trace_hash",
    "category",
    "step_index",
    "state_signature",
    "action_shape",
    "outcome_local",
    "skill_tags",
    "source_scope",
)

ALLOWED_SOURCE_SCOPES = {"synthetic", "approved_compact"}
REJECTED_SOURCE_SCOPES = {"dev_only_future"}


@dataclass(frozen=True)
class TraceBufferRecord:
    trace_hash: str | None
    category: str | None
    step_index: int | None
    state_signature: str | None
    action_shape: str | None
    outcome_local: str | None
    skill_tags: tuple[str, ...]
    source_scope: str | None
    trace_id: str
    case_hash: str | None
    signals: tuple[str, ...]
    rejected: bool
    reject_reason: str | None
    provider_call_count: int = 0
    scorer_call_count: int = 0
    source_collection_call_count: int = 0


@dataclass
class StepTraceBuffer:
    """In-memory buffer for committed synthetic or approved compact traces only.

    The buffer never reads BFCL source/result/score files and never stores raw
    case IDs, raw traces, provider payloads, scorer diffs, or candidate output.
    """

    records: list[TraceBufferRecord] = field(default_factory=list)
    rejected_records: list[TraceBufferRecord] = field(default_factory=list)
    case_hash_allowed_count: int = 0
    raw_case_id_rejected_count: int = 0
    forbidden_field_rejected_count: int = 0
    path_indicator_rejected_count: int = 0
    required_field_missing_rejected_count: int = 0
    source_scope_rejected_count: int = 0
    approved_compact_trace_count: int = 0
    synthetic_trace_count: int = 0
    provider_call_count: int = 0
    scorer_call_count: int = 0
    source_collection_call_count: int = 0

    def append(self, trace: dict[str, Any]) -> TraceBufferRecord:
        forbidden_hits = find_forbidden_fields(trace)
        raw_case_id = has_raw_case_id(trace)
        path_hits = find_path_indicators(trace)
        missing_required = missing_v0_2_fields(trace)
        source_scope = trace.get("source_scope") if isinstance(trace.get("source_scope"), str) else None
        nonzero_call_keys = [key for key in REQUIRED_ZERO_TRACE_KEYS if int(trace.get(key) or 0) != 0]
        self.provider_call_count += int(trace.get("provider_call_count") or 0)
        self.scorer_call_count += int(trace.get("scorer_call_count") or 0)
        self.source_collection_call_count += int(trace.get("source_collection_call_count") or 0)

        reject_reason = _reject_reason(trace, forbidden_hits, raw_case_id, path_hits, missing_required, source_scope, nonzero_call_keys)
        record = TraceBufferRecord(
            trace_hash=trace.get("trace_hash") if isinstance(trace.get("trace_hash"), str) else None,
            category=trace.get("category") if isinstance(trace.get("category"), str) else None,
            step_index=trace.get("step_index") if isinstance(trace.get("step_index"), int) else None,
            state_signature=trace.get("state_signature") if isinstance(trace.get("state_signature"), str) else None,
            action_shape=trace.get("action_shape") if isinstance(trace.get("action_shape"), str) else None,
            outcome_local=trace.get("outcome_local") if isinstance(trace.get("outcome_local"), str) else None,
            skill_tags=tuple(str(tag) for tag in trace.get("skill_tags") or []),
            source_scope=source_scope,
            trace_id=str(trace.get("trace_id") or ""),
            case_hash=trace.get("case_hash") if isinstance(trace.get("case_hash"), str) and not raw_case_id else None,
            signals=tuple(str(signal) for signal in trace.get("signals") or []),
            rejected=reject_reason is not None,
            reject_reason=reject_reason,
            provider_call_count=int(trace.get("provider_call_count") or 0),
            scorer_call_count=int(trace.get("scorer_call_count") or 0),
            source_collection_call_count=int(trace.get("source_collection_call_count") or 0),
        )
        if reject_reason is None:
            self.records.append(record)
            if record.case_hash:
                self.case_hash_allowed_count += 1
            if source_scope == "synthetic":
                self.synthetic_trace_count += 1
            elif source_scope == "approved_compact":
                self.approved_compact_trace_count += 1
        else:
            self.rejected_records.append(record)
            if raw_case_id:
                self.raw_case_id_rejected_count += 1
            if forbidden_hits:
                self.forbidden_field_rejected_count += 1
            if path_hits:
                self.path_indicator_rejected_count += 1
            if missing_required:
                self.required_field_missing_rejected_count += 1
            if reject_reason in {"dev_only_future_scope_disabled", "source_scope_not_allowed", "source_scope_missing"}:
                self.source_scope_rejected_count += 1
        return record

    def summary(self) -> dict[str, Any]:
        return {
            "trace_fixture_count": len(self.records) + len(self.rejected_records),
            "accepted_trace_count": len(self.records),
            "rejected_trace_count": len(self.rejected_records),
            "case_hash_allowed_count": self.case_hash_allowed_count,
            "raw_case_id_rejected_count": self.raw_case_id_rejected_count,
            "forbidden_field_rejected_count": self.forbidden_field_rejected_count,
            "path_indicator_rejected_count": self.path_indicator_rejected_count,
            "required_field_missing_rejected_count": self.required_field_missing_rejected_count,
            "source_scope_rejected_count": self.source_scope_rejected_count,
            "synthetic_trace_count": self.synthetic_trace_count,
            "approved_compact_trace_count": self.approved_compact_trace_count,
            "provider_call_count": self.provider_call_count,
            "scorer_call_count": self.scorer_call_count,
            "source_collection_call_count": self.source_collection_call_count,
            "candidate_generation_authorized": False,
            "performance_evidence": False,
            "required_v0_2_fields": list(REQUIRED_V0_2_TRACE_FIELDS),
        }


def missing_v0_2_fields(trace: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_V0_2_TRACE_FIELDS:
        value = trace.get(key)
        if key == "step_index":
            if not isinstance(value, int):
                missing.append(key)
        elif key == "skill_tags":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                missing.append(key)
        elif not isinstance(value, str) or not value:
            missing.append(key)
    return missing


def find_path_indicators(obj: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            next_path = f"{path}.{key}" if path else str(key)
            hits.extend(find_path_indicators(value, next_path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(find_path_indicators(value, f"{path}[{index}]"))
    elif isinstance(obj, str):
        value_l = obj.lower()
        for indicator in PATH_INDICATORS:
            if indicator in value_l:
                hits.append(path or "<string>")
                break
    return hits


def _reject_reason(
    trace: dict[str, Any],
    forbidden_hits: list[str],
    raw_case_id: bool,
    path_hits: list[str],
    missing_required: list[str],
    source_scope: str | None,
    nonzero_call_keys: list[str],
) -> str | None:
    if trace.get("offline_only") is not True:
        return "offline_only_missing"
    if trace.get("synthetic_fixture") is not True:
        return "synthetic_fixture_missing"
    if raw_case_id:
        return "raw_case_id"
    if path_hits:
        return "path_indicator"
    if forbidden_hits:
        return "forbidden_field"
    if missing_required:
        return "required_field_missing"
    if source_scope is None:
        return "source_scope_missing"
    if source_scope in REJECTED_SOURCE_SCOPES:
        return "dev_only_future_scope_disabled"
    if source_scope not in ALLOWED_SOURCE_SCOPES:
        return "source_scope_not_allowed"
    if nonzero_call_keys:
        return "call_count_nonzero"
    return None
