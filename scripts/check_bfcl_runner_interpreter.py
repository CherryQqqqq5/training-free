#!/usr/bin/env python3
"""Check BFCL shell runners do not use unqualified bare python commands."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_SCRIPT = Path("scripts/run_bfcl_v4_baseline.sh")
BARE_PYTHON_RE = re.compile(r"(^|[\s;(])python($|[\s;<|&)])")


def check_script(path: Path = DEFAULT_SCRIPT) -> dict:
    blockers: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {
            "report_scope": "bfcl_runner_interpreter_check",
            "script": str(path),
            "bfcl_runner_interpreter_passed": False,
            "blockers": [f"runner_interpreter_script_read_failed:{exc}"],
        }
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if BARE_PYTHON_RE.search(line):
            blockers.append(f"bare_python_invocation:{path}:{lineno}")
    text = "\n".join(lines)
    if 'GRC_PYTHON="${GRC_PYTHON:-${REPO_ROOT}/.venv/bin/python}"' not in text:
        blockers.append("runner_interpreter_default_missing")
    if '[[ ! -x "${GRC_PYTHON}" ]]' not in text:
        blockers.append("runner_interpreter_executable_guard_missing")
    return {
        "report_scope": "bfcl_runner_interpreter_check",
        "script": str(path),
        "interpreter_default": "${REPO_ROOT}/.venv/bin/python",
        "bfcl_runner_interpreter_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check_script(args.script)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_runner_interpreter_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
