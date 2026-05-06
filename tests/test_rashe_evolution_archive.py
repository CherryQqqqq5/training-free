from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_evolution_archive import DEFAULT_ARCHIVE, validate_archive

CHECKER = Path("scripts/check_rashe_evolution_archive.py")
ARCHIVE_ROOT = DEFAULT_ARCHIVE.parent


def copy_archive(tmp_path: Path) -> Path:
    root = tmp_path / "rashe_evolution_archive"
    shutil.copytree(ARCHIVE_ROOT, root)
    return root / "archive_index.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_portable(index_path: Path, index: dict) -> dict:
    root = index_path.parent
    for item in index["entries"]:
        item["entry_path"] = str(root / "entries" / f"{item['entry_id']}.json")
    return index


def test_archive_checker_passes_current_artifacts() -> None:
    result = subprocess.run([sys.executable, str(CHECKER), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_evolution_archive_passed"] is True
    assert summary["entry_count"] == 3
    assert summary["proposal_ready_entry_count"] == 2
    assert summary["performance_evidence"] is False
    assert summary["scorer_authorized"] is False
    assert summary["candidate_pool_ready"] is False


def test_archive_rejects_authorization_or_performance_flips(tmp_path: Path) -> None:
    index_path = copy_archive(tmp_path)
    index = make_portable(index_path, load(index_path))
    index["performance_evidence"] = True
    index["scorer_authorized"] = True
    first_entry_path = Path(index["entries"][0]["entry_path"])
    entry = load(first_entry_path)
    entry["boundary_flags"]["candidate_pool_ready"] = True
    write(first_entry_path, entry)
    blockers = validate_archive(index, base_path=Path("."))
    joined = "\n".join(blockers)
    assert "index_performance_evidence_not_false:True" in joined
    assert "index_scorer_authorized_not_false:True" in joined
    assert "candidate_pool_ready_not_false" in joined


def test_archive_requires_entry_contract_fields(tmp_path: Path) -> None:
    index_path = copy_archive(tmp_path)
    index = make_portable(index_path, load(index_path))
    entry_path = Path(index["entries"][1]["entry_path"])
    entry = load(entry_path)
    del entry["feedback_slots"]
    write(entry_path, entry)
    blockers = validate_archive(index, base_path=Path("."))
    assert any("entry_required_fields_missing" in blocker and "feedback_slots" in blocker for blocker in blockers)


def test_archive_rejects_bfcl_subset_bound_candidate_name(tmp_path: Path) -> None:
    index_path = copy_archive(tmp_path)
    index = make_portable(index_path, load(index_path))
    item = dict(index["entries"][0])
    item["entry_id"] = "multi_turn_miss_param_skill_v0"
    item["entry_path"] = str(index_path.parent / "entries" / "multi_turn_miss_param_skill_v0.json")
    entry = load(Path(index["entries"][0]["entry_path"]))
    entry["entry_id"] = item["entry_id"]
    write(Path(item["entry_path"]), entry)
    index["entries"].append(item)
    blockers = validate_archive(index, base_path=Path("."))
    assert any("category_bound" in blocker for blocker in blockers)


def test_archive_rejects_forbidden_material_outside_forbidden_inputs(tmp_path: Path) -> None:
    index_path = copy_archive(tmp_path)
    index = make_portable(index_path, load(index_path))
    entry_path = Path(index["entries"][0]["entry_path"])
    entry = load(entry_path)
    entry["source_evidence"]["raw_trace"] = "redacted"
    entry["notes"] = "candidate output text must never be persisted here"
    write(entry_path, entry)
    blockers = validate_archive(index, base_path=Path("."))
    joined = "\n".join(blockers)
    assert "forbidden_key" in joined
    assert "forbidden_value" in joined


def test_archive_rejects_dev_score_before_run(tmp_path: Path) -> None:
    index_path = copy_archive(tmp_path)
    index = make_portable(index_path, load(index_path))
    entry_path = Path(index["entries"][0]["entry_path"])
    entry = load(entry_path)
    entry["dev_score_status"] = "passed"
    write(entry_path, entry)
    blockers = validate_archive(index, base_path=Path("."))
    assert any("dev_score_status_not_not_run" in blocker for blocker in blockers)
