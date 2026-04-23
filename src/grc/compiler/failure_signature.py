from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Iterable

from pydantic import BaseModel, Field


class FailureSignature(BaseModel):
    stage: str
    type: str
    tool_schema_hash: str = "*"
    literals_pattern: str = "unknown"


class SignatureSummary(BaseModel):
    signature: FailureSignature
    count: int
    share: float
    failure_labels: list[str] = Field(default_factory=list)


def tool_schema_hash(tool_schema_snapshot: Any) -> str:
    if not tool_schema_snapshot:
        return "*"
    encoded = json.dumps(tool_schema_snapshot, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def literals_pattern(failure_case: Any) -> str:
    request_literals = getattr(failure_case, "request_literals", None)
    if request_literals:
        return "explicit_context_literals"
    predicates = set(getattr(failure_case, "request_predicates", None) or [])
    evidence = getattr(failure_case, "predicate_evidence", None) or {}
    if "prior_tool_outputs_present" in predicates or evidence.get("tool_output_sufficient"):
        return "prior_tool_outputs"
    if "prior_explicit_literals_present" in predicates or evidence.get("has_sufficient_literals"):
        return "explicit_context_literals"
    return "no_explicit_literals"


def signature_from_failure(failure_case: Any, trace_payload: dict[str, Any] | None = None) -> FailureSignature:
    trace_payload = trace_payload or {}
    schema_snapshot = trace_payload.get("tool_schema_snapshot")
    stage = getattr(failure_case, "stage", None) or "UNKNOWN"
    failure_type = getattr(failure_case, "failure_type", None) or getattr(failure_case, "error_type", "UNKNOWN")
    return FailureSignature(
        stage=str(stage),
        type=str(failure_type),
        tool_schema_hash=tool_schema_hash(schema_snapshot),
        literals_pattern=literals_pattern(failure_case),
    )


def top_k_signatures(failures: Iterable[Any], k: int = 5) -> list[SignatureSummary]:
    items = list(failures)
    counts: Counter[tuple[str, str, str, str]] = Counter()
    labels: dict[tuple[str, str, str, str], set[str]] = {}
    for failure in items:
        signature = signature_from_failure(failure)
        key = (
            signature.stage,
            signature.type,
            signature.tool_schema_hash,
            signature.literals_pattern,
        )
        counts[key] += 1
        label = getattr(failure, "failure_label", None)
        labels.setdefault(key, set())
        if label:
            labels[key].add(str(label))

    total = len(items)
    summaries: list[SignatureSummary] = []
    for key, count in counts.most_common(k):
        summaries.append(
            SignatureSummary(
                signature=FailureSignature(
                    stage=key[0],
                    type=key[1],
                    tool_schema_hash=key[2],
                    literals_pattern=key[3],
                ),
                count=count,
                share=(count / total if total else 0.0),
                failure_labels=sorted(labels.get(key, set())),
            )
        )
    return summaries
