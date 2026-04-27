#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

DEFAULT_DEV_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUT_ROOT = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
DEFAULT_SEED_CATEGORIES = ["multi_turn_base", "multi_turn_miss_func", "multi_turn_long_context"]
EXCLUDED_CATEGORY_PREFIXES = ("live_",)
EXCLUDED_CATEGORIES = {"format_sensitivity", "memory", "web_search", "web_search_base", "web_search_no_snippet"}
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


def _raw_bfcl_categories(data_root: Path | None = None) -> list[str]:
    root = data_root or _bfcl_data_root()
    categories: set[str] = set()
    for path in root.glob("BFCL_v4_*.json"):
        name = path.name
        if name.startswith("BFCL_v4_") and name.endswith(".json"):
            categories.add(name[len("BFCL_v4_") : -len(".json")])
    return sorted(categories)


def _bfcl_runnable_categories() -> list[str]:
    try:
        from bfcl_eval.constants.category_mapping import ALL_CATEGORIES
    except Exception:
        return []
    return sorted(str(category) for category in ALL_CATEGORIES)


def _is_low_risk_source_category(category: str) -> bool:
    if category in EXCLUDED_CATEGORIES:
        return False
    return not any(category.startswith(prefix) for prefix in EXCLUDED_CATEGORY_PREFIXES)


def _ids_from_records(records: Any, limit: int) -> list[str]:
    ids: list[str] = []
    iterator = records if isinstance(records, list) else []
    for row in iterator:
        if isinstance(row, dict):
            case_id = str(row.get("id") or "")
        elif isinstance(row, str):
            case_id = row
        else:
            case_id = ""
        if case_id:
            ids.append(case_id)
        if len(ids) >= limit:
            break
    return ids


def _load_category_ids_from_bfcl_api(category: str, limit: int) -> list[str]:
    try:
        from bfcl_eval.utils import load_dataset_entry
    except Exception:
        return []
    try:
        records = load_dataset_entry(category, include_prereq=False)
    except Exception:
        return []
    return _ids_from_records(records, limit)


def _load_category_ids_from_raw_file(category: str, limit: int, data_root: Path | None = None) -> list[str]:
    path = (data_root or _bfcl_data_root()) / f"BFCL_v4_{category}.json"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            # Helper mapping files are not directly runnable categories.
            return [str(data["id"])] if isinstance(data.get("id"), str) else []
        return _ids_from_records(data, limit)
    except json.JSONDecodeError:
        ids: list[str] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            case_id = str(row.get("id") or "") if isinstance(row, dict) else ""
            if case_id:
                ids.append(case_id)
            if len(ids) >= limit:
                break
        return ids


def _load_category_ids(category: str, limit: int, data_root: Path | None = None) -> tuple[list[str], str | None]:
    # Test fixtures can pass an explicit data_root; prefer raw files there so tests do not depend on installed BFCL.
    if data_root is None:
        ids = _load_category_ids_from_bfcl_api(category, limit)
        if ids:
            return ids, "bfcl_dataset_api"
    ids = _load_category_ids_from_raw_file(category, limit, data_root=data_root)
    if ids:
        return ids, "raw_category_file"
    return [], None


def _category_has_case_ids(category: str, data_root: Path | None = None) -> bool:
    try:
        ids, _source = _load_category_ids(category, 1, data_root=data_root)
        return bool(ids)
    except Exception:
        return False


def discover_source_categories(seed_categories: list[str] | None = None, data_root: Path | None = None) -> tuple[list[str], dict[str, Any]]:
    raw_categories = _raw_bfcl_categories(data_root)
    runnable_categories = [] if data_root is not None else _bfcl_runnable_categories()
    seeds = list(seed_categories or DEFAULT_SEED_CATEGORIES)
    discovered = set(raw_categories) | set(runnable_categories) | set(seeds)
    candidates = sorted(
        category
        for category in discovered
        if _is_low_risk_source_category(category) and _category_has_case_ids(category, data_root=data_root)
    )
    excluded = sorted(category for category in discovered if category not in candidates)
    return candidates, {
        "category_discovery_source": "bfcl_runnable_categories_plus_raw_files",
        "raw_category_count": len(raw_categories),
        "raw_categories": raw_categories,
        "bfcl_runnable_category_count": len(runnable_categories),
        "bfcl_runnable_categories": runnable_categories,
        "candidate_source_category_count": len(candidates),
        "candidate_source_categories": candidates,
        "excluded_category_count": len(excluded),
        "excluded_categories": excluded,
        "excluded_category_policy": {
            "excluded_prefixes": list(EXCLUDED_CATEGORY_PREFIXES),
            "excluded_categories": sorted(EXCLUDED_CATEGORIES),
            "reason": "avoid live/web-search and non-runnable generic memory categories for low-risk offline slice planning",
        },
    }


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
    data_root: Path | None = None,
) -> dict[str, Any]:
    dev = _j(dev_root / "paired_subset_manifest.json")
    dev_source_root = Path(str(dev.get("source_run_root") or ""))
    if categories is None:
        cats, discovery = discover_source_categories(data_root=data_root)
    else:
        cats = categories
        raw_categories = _raw_bfcl_categories(data_root) if data_root is not None else []
        discovery = {
            "category_discovery_source": "explicit_categories_arg",
            "raw_category_count": len(raw_categories),
            "raw_categories": raw_categories,
            "bfcl_runnable_category_count": 0,
            "bfcl_runnable_categories": [],
            "candidate_source_category_count": len(cats),
            "candidate_source_categories": cats,
            "excluded_category_count": 0,
            "excluded_categories": [],
        }
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
        selected_id_source = None
        id_path = None
        if not ready:
            selected_ids, selected_id_source = _load_category_ids(cat, cases_per_category, data_root=data_root)
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
                "selected_case_id_source": selected_id_source,
                "test_case_ids_path": str(id_path) if id_path else None,
                "planned_source_collection_command": cmd,
                "source_collection_only": True,
                "no_candidate_rules": True,
            }
        )

    missing = [r["category"] for r in rows if r["baseline_source_collection_required"]]
    ready_categories = [r["category"] for r in rows if r["source_artifacts_available"]]
    return {
        "report_scope": "m2_7t_source_pool_manifest",
        "artifact_root": str(out_root),
        "dev_subset_root": str(dev_root),
        "categories": cats,
        "cases_per_category": cases_per_category,
        "category_status": rows,
        "ready_categories": ready_categories,
        "missing_source_categories": missing,
        "planned_source_collection_commands": commands,
        "planned_commands": commands,
        "candidate_commands": [],
        "source_collection_only": True,
        "no_candidate_rules": True,
        "m27t_source_pool_ready": all(r["source_artifacts_available"] for r in rows),
        "source_collection_expansion_ready": bool(commands),
        "diagnostic": {
            **discovery,
            "baseline_only": True,
            "no_candidate_rules": True,
            "not_performance_evidence": True,
            "requires_grc_bfcl_use_run_ids": True,
            "does_not_authorize_scorer": True,
        },
    }


def md(r: dict[str, Any]) -> str:
    diagnostic = r.get("diagnostic") or {}
    lines = [
        "# M2.7t Source Pool Manifest",
        "",
        f"- Ready: `{r['m27t_source_pool_ready']}`",
        f"- Source collection commands: `{len(r['planned_source_collection_commands'])}`",
        f"- Cases per missing category: `{r['cases_per_category']}`",
        f"- Discovery source: `{diagnostic.get('category_discovery_source')}`",
        f"- Candidate source categories: `{diagnostic.get('candidate_source_category_count')}`",
        "",
        "| Category | Available | Needs Collection | Selected Cases | ID Source | Run IDs File |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for x in r["category_status"]:
        lines.append(
            f"| `{x['category']}` | `{x['source_artifacts_available']}` | "
            f"`{x['baseline_source_collection_required']}` | `{x['selected_case_count']}` | "
            f"`{x['selected_case_id_source']}` | `{x['test_case_ids_path']}` |"
        )
    lines += ["", "## Planned Baseline-Only Commands"]
    lines += [f"```bash\n{cmd}\n```" for cmd in r["planned_source_collection_commands"]]
    lines += ["", "No candidate commands are emitted. Source collection results are not performance evidence.", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-root", type=Path, default=DEFAULT_DEV_ROOT)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    ap.add_argument("--repo-root", type=Path, default=Path.cwd())
    ap.add_argument("--cases-per-category", type=int, default=DEFAULT_CASES_PER_CATEGORY)
    ap.add_argument("--category", action="append", dest="categories")
    ap.add_argument("--compact", action="store_true")
    a = ap.parse_args()
    r = build_source_pool_manifest(
        a.dev_root,
        a.out_root,
        a.repo_root,
        categories=a.categories,
        cases_per_category=a.cases_per_category,
    )
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
                        "ready_categories",
                        "missing_source_categories",
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
