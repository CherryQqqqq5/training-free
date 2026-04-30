#!/usr/bin/env python3
"""Offline checker for the RASHE StepTraceBuffer skeleton."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_FIXTURE_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/fixtures/step_trace_buffer")
RUNTIME_MODULE_PREFIXES = ("grc.runtime", "grc.runtime.proxy", "grc.runtime.engine")


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def runtime_modules_loaded() -> list[str]:
    return sorted(name for name in sys.modules if name in RUNTIME_MODULE_PREFIXES or name.startswith("grc.runtime."))


def fixture_paths(root: Path) -> list[Path]:
    explicit = sorted(root.glob("step_trace_*.json"))
    if explicit:
        return explicit
    return sorted(p for p in root.glob("*.json") if p.name != "aggregate_verifier_report.json")


def check(root: Path = DEFAULT_FIXTURE_ROOT) -> dict[str, Any]:
    before = set(runtime_modules_loaded())
    from grc.skills.trace_buffer import StepTraceBuffer

    imported_runtime = set(runtime_modules_loaded()) - before
    blockers: list[str] = []
    if imported_runtime:
        blockers.append("ruleengine_proxy_active_path_imported")
    paths = fixture_paths(root)
    if not paths:
        blockers.append("trace_fixtures_missing")
    buffer = StepTraceBuffer()
    for path in paths:
        trace = load_json(path)
        if not isinstance(trace, dict):
            blockers.append(f"trace_not_object:{path}")
            continue
        record = buffer.append(trace)
        expected_status = trace.get("expected_buffer_status")
        expected_reject = trace.get("expected_buffer_reject_reason")
        if expected_status == "accepted":
            if record.rejected:
                blockers.append(f"trace_unexpected_reject:{path.name}:{record.reject_reason}")
        elif expected_status == "rejected":
            if not record.rejected:
                blockers.append(f"trace_unexpected_accept:{path.name}")
            elif expected_reject and record.reject_reason != expected_reject:
                blockers.append(f"trace_reject_reason_mismatch:{path.name}:{record.reject_reason}")
        else:
            blockers.append(f"trace_expected_buffer_status_missing:{path.name}")
    summary = {
        "report_scope": "rashe_step_trace_buffer_check",
        "offline_only": True,
        "enabled": False,
        "runtime_behavior_authorized": False,
        "ruleengine_proxy_active_path_imported": bool(imported_runtime),
        **buffer.summary(),
        "step_trace_buffer_offline_passed": not blockers,
        "blockers": blockers,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.fixture_root)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["step_trace_buffer_offline_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
