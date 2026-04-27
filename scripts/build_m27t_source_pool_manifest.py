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
EXCLUDED_CATEGORIES = {"web_search"}
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


def _installed_bfcl_categories(data_root: Path | None = None) -> list[str]:
    root = data_root or _bfcl_data_root()
    categories: set[str] = set()
    for path in root.glob("BFCL_v4_*.json"):
        name = path.name
        if name.startswith("BFCL_v4_") and name.endswith(".json"):
            categories.add(name[len("BFCL_v4_") : -len(".json")])
    return sorted(categories)


def _is_low_risk_source_category(category: str) -> bool:
    if category in EXCLUDED_CATEGORIES:
        return False
    return not any(category.startswith(prefix) for prefix in EXCLUDED_CATEGORY_PREFIXES)


def discover_source_categories(seed_categories: list[str] | None = None, data_root: Path | None = None) -> tuple[list[str], dict[str, Any]]:
    installed = _installed_bfcl_categories(data_root)
    seeds = list(seed_categories or DEFAULT_SEED_CATEGORIES)
    usable = {cat for cat in installed if _category_has_case_ids(cat, data_root)}
    candidates = sorted(({cat for cat in usable if _is_low_risk_source_category(cat)} | set(seeds)).intersection(usable))
    excluded = sorted(cat for cat in installed if cat not in candidates)
    return candidates, {
        "category_discovery_source": "installed_bfcl_data",
        "installed_category_count": len(installed),
        "installed_categories": installed,
        "candidate_source_category_count": len(candidates),
        "candidate_source_categories": candidates,
        "excluded_category_count": len(excluded),
        "excluded_categories": excluded,
        "excluded_category_policy": {
            "excluded_prefixes": list(EXCLUDED_CATEGORY_PREFIXES),
            "excluded_categories": sorted(EXCLUDED_CATEGORIES),
            "reason": "avoid live/external-search or non-case-list source collection for low-risk offline slice planning",
        },
    }


def _ids_from_records(records: Any, limit: int) -> list[str]:
    ids: list[str] = []
    if isinstance(records, list):
        iterator = records
    else:
        iterator = []
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


def _load_category_ids(category: str, limit: int, data_root: Path | None = None) -> list[str]:
    path = (data_root or _bfcl_data_root()) / f"BFCL_v4_{category}.json"
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            # Some BFCL helper files are maps of other categories and are not directly runnable categories.
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


def _category_has_case_ids(category: str, data_root: Path | None = None) -> bool:
    try:
        return bool(_load_category_ids(category, 1, data_root=data_root))
    except Exception:
        return False


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
        installed = _installed_bfcl_categories(data_root) if data_root is not None else []
        discovery = {
            "category_discovery_source": "explicit_categories_arg",
            "installed_category_count": len(installed),
            "installed_categories": installed,
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
        id_path = None
        if not ready:
            selected_ids = _load_category_ids(cat, cases_per_category, data_root=data_root)
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
