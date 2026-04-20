#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def upsert(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    replaced = False
    output: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            output.append(f"{key}={value}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        if output and output[-1] != "":
            output.append("")
        output.append(f"{key}={value}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize BFCL fixture .env with the current local proxy endpoint."
    )
    parser.add_argument("--bfcl-root", required=True)
    parser.add_argument("--openai-base-url", required=True)
    parser.add_argument("--local-server-endpoint", required=True)
    parser.add_argument("--local-server-port", required=True)
    parser.add_argument("--openai-api-key", required=True)
    args = parser.parse_args()

    bfcl_root = Path(args.bfcl_root)
    bfcl_root.mkdir(parents=True, exist_ok=True)
    env_path = bfcl_root / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    lines = upsert(lines, "OPENAI_BASE_URL", args.openai_base_url)
    lines = upsert(lines, "LOCAL_SERVER_ENDPOINT", args.local_server_endpoint)
    lines = upsert(lines, "LOCAL_SERVER_PORT", str(args.local_server_port))
    lines = upsert(lines, "OPENAI_API_KEY", args.openai_api_key)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
