#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

DEFAULT_DEV_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUT_ROOT = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
CATEGORIES = ["multi_turn_base", "multi_turn_miss_func", "multi_turn_long_context"]
MODEL = "gpt-4o-mini-2024-07-18-FC"
DEFAULT_CASES_PER_CATEGORY = 30


def _j(p: Path, default: Any = None):
    if not p.exists():
        if default is not None:
            return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())


def _w(p: Path, d: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")


def _bfcl_data_root() -> Path:
    spec = importlib.util.find_spec("bfcl_eval")
    if not spec or not spec.origin:
        raise RuntimeError("bfcl_eval package is not importable")
    return Path(spec.origin).parent / "data"


def _load_category_ids(category: str, limit: int) -> list[str]:
    path = _bfcl_data_root() / f"BFCL_v4_{category}.json"
    ids: list[str] = []
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            case_id = str(row.get("id") or "")
            if case_id:
                ids.append(case_id)
            if len(ids) >= limit:
                break
    return ids


def _has_source(root: Path, cat: str) -> bool:
    return bool(
        list((root / "bfcl").glob(f"**/BFCL_v4_{cat}_score.json"))
        and list((root / "bfcl").glob(f"**/BFCL_v4_{cat}_result.json"))
    )


def _baseline_command(repo: Path, out_root: Path, cat: str, port: int, runtime: Path) -> str:
    return " ".join(
        [
            "bash",
            str(repo / "scripts/run_bfcl_v4_baseline.sh"),
            MODEL,
            str(out_root / cat / "baseline"),
            str(port),
            cat,
            str(runtime),
        ]
    )


def _write_run_ids(out_root: Path, category: str, selected_ids: list[str]) -> Path:
    id_path = out_root / category / "baseline" / "bfcl" / "test_case_ids_to_generate.json"
    _w(id_path, {category: selected_ids})
    return id_path


def build_source_pool_manifest(
    dev_root: Path = DEFAULT_DEV_ROOT,
    out_root: Path = DEFAULT_OUT_ROOT,
    repo_root: Path = Path.cwd(),
    categories: list[str] | None = None,
    cases_per_category: int = DEFAULT_CASES_PER_CATEGORY,
) -> dict[str, Any]:
    dev = _j(dev_root / "paired_subset_manifest.json")
    dev_source_root = Path(str(dev.get("source_run_root") or ""))
    cats = categories or CATEGORIES
    runtime = Path(str(dev.get("runtime_config") or "configs/runtime_bfcl_structured.yaml"))
    if not runtime.is_absolute():
        runtime = repo_root / runtime

    rows: list[dict[str, Any]] = []
    commands: list[str] = []
    for i, cat in enumerate(cats):
        candidate_roots = [dev_source_root, out_root / cat / "baseline"]
        existing = [str(root) for root in candidate_roots if _has_source(root, cat)]
        ready = bool(existing)
        cmd = None
        selected_ids: list[str] = []
        id_path = None
        if not ready:
            selected_ids = _load_category_ids(cat, cases_per_category)
            id_path = _write_run_ids(out_root, cat, selected_ids)
            cmd = _baseline_command(repo_root, out_root, cat, 8070 + i, runtime)
            commands.append(cmd)
        rows.append(
            {
                "category": cat,
                "source_artifacts_available": ready,
                "existing_source_roots": existing,
                "baseline_source_collection_required": not ready,
                "selected_case_count": len(selected_ids),
                "selected_case_ids": selected_ids,
                "test_case_ids_path": str(id_path) if id_path else None,
                "planned_source_collection_command": cmd,
            }
        )

    return {
        "report_scope": "m2_7t_source_pool_manifest",
        "artifact_root": str(out_root),
        "dev_subset_root": str(dev_root),
        "categories": cats,
        "cases_per_category": cases_per_category,
        "category_status": rows,
        "planned_source_collection_commands": commands,
        "planned_commands": commands,
        "candidate_commands": [],
        "source_collection_only": True,
        "m27t_source_pool_ready": all(r["source_artifacts_available"] for r in rows),
        "diagnostic": {
            "baseline_only": True,
            "no_candidate_rules": True,
            "not_performance_evidence": True,
            "requires_grc_bfcl_use_run_ids": True,
        },
    }


def md(r: dict[str, Any]) -> str:
    lines = [
        "# M2.7t Source Pool Manifest",
        "",
        f"- Ready: `{r['m27t_source_pool_ready']}`",
        f"- Source collection commands: `{len(r['planned_source_collection_commands'])}`",
        f"- Cases per missing category: `{r['cases_per_category']}`",
        "",
        "| Category | Available | Needs Collection | Selected Cases | Run IDs File |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for x in r["category_status"]:
        lines.append(
            f"| `{x['category']}` | `{x['source_artifacts_available']}` | "
            f"`{x['baseline_source_collection_required']}` | `{x['selected_case_count']}` | "
            f"`{x['test_case_ids_path']}` |"
        )
    lines += ["", "## Planned Baseline-Only Commands"]
    lines += [f"```bash\n{cmd}\n```" for cmd in r["planned_source_collection_commands"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-root", type=Path, default=DEFAULT_DEV_ROOT)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    ap.add_argument("--repo-root", type=Path, default=Path.cwd())
    ap.add_argument("--cases-per-category", type=int, default=DEFAULT_CASES_PER_CATEGORY)
    ap.add_argument("--compact", action="store_true")
    a = ap.parse_args()
    r = build_source_pool_manifest(a.dev_root, a.out_root, a.repo_root, cases_per_category=a.cases_per_category)
    a.out_root.mkdir(parents=True, exist_ok=True)
    _w(a.out_root / "source_collection_manifest.json", r)
    (a.out_root / "source_collection_manifest.md").write_text(md(r))
    if a.compact:
        print(
            json.dumps(
                {
                    k: r.get(k)
                    for k in [
                        "m27t_source_pool_ready",
                        "planned_source_collection_commands",
                        "candidate_commands",
                    ]
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
