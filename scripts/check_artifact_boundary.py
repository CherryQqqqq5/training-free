from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

OUTPUT_ROOT = Path("outputs")

FORBIDDEN_DIR_MARKERS = (
    "/traces/",
    "/bfcl/.file_locks/",
    "/bfcl/result/",
    "/bfcl/score/",
    "/logs/",
)
FORBIDDEN_FILENAMES = {
    ".env",
    "repairs.jsonl",
}
FORBIDDEN_SUFFIXES = (
    "_repair_records.jsonl",
    ".log",
)


def _norm(path: str | Path) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def tracked_files(root: str = "outputs") -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", root],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def filesystem_files(root: Path = OUTPUT_ROOT) -> list[str]:
    if not root.exists():
        return []
    return [_norm(path) for path in root.rglob("*") if path.is_file()]


def is_forbidden_output(path: str | Path) -> bool:
    normalized = _norm(path)
    if not normalized.startswith("outputs/"):
        return False
    name = normalized.rsplit("/", 1)[-1]
    if name in FORBIDDEN_FILENAMES:
        return True
    if any(name.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
        return True
    return any(marker in f"/{normalized}" for marker in FORBIDDEN_DIR_MARKERS)


def forbidden_outputs(paths: list[str]) -> list[str]:
    return sorted({path for path in paths if is_forbidden_output(path)})


def collect_output_paths(*, tracked_only: bool = False) -> list[str]:
    paths = set(tracked_files("outputs"))
    if not tracked_only:
        paths.update(filesystem_files(OUTPUT_ROOT))
    return sorted(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail if tracked or workspace output artifacts contain raw benchmark files, secrets, or repair records."
    )
    parser.add_argument("--max-print", type=int, default=50)
    parser.add_argument(
        "--tracked-only",
        action="store_true",
        help="Only inspect git-tracked outputs. Delivery gates should not use this mode.",
    )
    args = parser.parse_args(argv)
    bad = forbidden_outputs(collect_output_paths(tracked_only=args.tracked_only))
    if bad:
        print("forbidden benchmark artifacts found under outputs; remove or move them outside the delivery tree", file=sys.stderr)
        for path in bad[: args.max_print]:
            print(path, file=sys.stderr)
        if len(bad) > args.max_print:
            print(f"... {len(bad) - args.max_print} more", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
