from __future__ import annotations

import argparse
import subprocess
import sys

FORBIDDEN_MARKERS = (
    "/traces/",
    "/bfcl/.file_locks/",
    "/bfcl/result/",
    "/bfcl/score/",
)
ALLOWED_PREFIXES = (
    "outputs/artifacts/",
    "outputs/README.md",
)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "outputs"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def forbidden_outputs(paths: list[str]) -> list[str]:
    bad: list[str] = []
    for path in paths:
        if path.startswith(ALLOWED_PREFIXES):
            continue
        if any(marker in path for marker in FORBIDDEN_MARKERS):
            bad.append(path)
    return bad


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail if raw benchmark artifacts are tracked in git.")
    parser.add_argument("--max-print", type=int, default=50)
    args = parser.parse_args()
    bad = forbidden_outputs(tracked_files())
    if bad:
        print("raw benchmark artifacts are tracked; remove them with git rm --cached", file=sys.stderr)
        for path in bad[: args.max_print]:
            print(path, file=sys.stderr)
        if len(bad) > args.max_print:
            print(f"... {len(bad) - args.max_print} more", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
