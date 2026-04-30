"""Static SkillBank loader for the inert RASHE skeleton."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import EXPECTED_SKILL_IDS, Skill, find_forbidden_fields

DEFAULT_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/skillbank_manifest.json")


class SkillStore:
    """Load only committed sanitized seed skills from the SkillBank manifest."""

    def __init__(self, skills: dict[str, Skill], blockers: list[str] | None = None) -> None:
        self.skills = skills
        self.blockers = blockers or []

    @classmethod
    def load_manifest(cls, manifest_path: Path = DEFAULT_MANIFEST) -> "SkillStore":
        blockers: list[str] = []
        manifest = _load_json(manifest_path)
        _require(manifest, "schema_version", "rashe_skillbank_manifest_v0_1", blockers, "manifest")
        _require(manifest, "offline_only", True, blockers, "manifest")
        _require(manifest, "enabled", False, blockers, "manifest")
        _require(manifest, "runtime_authorized", False, blockers, "manifest")
        _require(manifest, "provider_call_count", 0, blockers, "manifest")
        _require(manifest, "scorer_call_count", 0, blockers, "manifest")
        _require(manifest, "source_collection_call_count", 0, blockers, "manifest")
        _require(manifest, "candidate_generation_authorized", False, blockers, "manifest")
        entries = manifest.get("skills")
        if not isinstance(entries, list):
            return cls({}, blockers + ["manifest_skills_missing"])
        root = Path(".") if not manifest_path.is_absolute() else manifest_path.parents[5]
        skills: dict[str, Skill] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                blockers.append("manifest_entry_not_object")
                continue
            entry_id = entry.get("skill_id")
            prefix = "manifest_" + str(entry_id)
            _require(entry, "enabled", False, blockers, prefix)
            _require(entry, "offline_only", True, blockers, prefix)
            _require(entry, "runtime_authorized", False, blockers, prefix)
            source_path = entry.get("source_path")
            if not isinstance(source_path, str):
                blockers.append(prefix + "_source_path_missing")
                continue
            skill_path = Path(source_path)
            if not skill_path.is_absolute():
                skill_path = root / skill_path
            skill, skill_blockers = load_skill(skill_path)
            blockers.extend(skill_blockers)
            if skill is not None:
                skills[skill.skill_id] = skill
        if set(skills) != EXPECTED_SKILL_IDS:
            blockers.append("skill_ids_mismatch")
        if manifest.get("skill_count") != len(skills):
            blockers.append("skill_count_mismatch")
        return cls(skills, blockers)

    def is_valid(self) -> bool:
        return not self.blockers


def load_skill(path: Path) -> tuple[Skill | None, list[str]]:
    blockers: list[str] = []
    data = _load_json(path)
    if not isinstance(data, dict):
        return None, [f"skill_not_object:{path}"]
    _require(data, "schema_version", "rashe_skill_v0", blockers, path.stem)
    _require(data, "offline_only", True, blockers, path.stem)
    _require(data, "enabled", False, blockers, path.stem)
    _require(data, "runtime_authorized", False, blockers, path.stem)
    _require(data, "training_free", True, blockers, path.stem)
    forbidden = find_forbidden_fields(data)
    if forbidden:
        blockers.append("skill_forbidden_fields:" + ",".join(forbidden))
    skill_id = data.get("skill_id")
    if not isinstance(skill_id, str):
        blockers.append(f"skill_id_missing:{path}")
        return None, blockers
    return Skill(
        skill_id=skill_id,
        display_name=str(data.get("display_name") or skill_id),
        allowed_triggers=tuple(str(v) for v in data.get("allowed_triggers") or []),
        forbidden_triggers=tuple(str(v) for v in data.get("forbidden_triggers") or []),
        actions=tuple(str(v) for v in data.get("actions") or []),
        enabled=bool(data.get("enabled")),
        offline_only=bool(data.get("offline_only")),
        runtime_authorized=bool(data.get("runtime_authorized")),
    ), blockers


def _load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def _require(obj: dict[str, Any], key: str, expected: Any, blockers: list[str], prefix: str) -> None:
    if obj.get(key) != expected:
        blockers.append(f"{prefix}_{key}_invalid")
