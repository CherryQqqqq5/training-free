import json
import subprocess
import sys
from pathlib import Path

from scripts import build_rashe_source_inputs_compact as builder
from scripts import check_rashe_source_inputs_compact as checker


RAW_SECRET = "raw prompt text must not leak"


def write_source_metadata(root: Path, *, raw_field=None, count=20):
    root.mkdir(parents=True, exist_ok=True)
    for category in builder.APPROVED_CATEGORIES:
        rows = []
        for ordinal in range(count):
            row = {
                "category": category,
                "ordinal": ordinal,
                "prompt_family": builder.CATEGORY_PROMPT_FAMILY[category],
                "source_nonce": f"approved-compact-token-{category}-{ordinal:02d}-safe",
                "source_family_id": builder.CATEGORY_SOURCE_FAMILY_ID[category],
            }
            if raw_field:
                row[raw_field] = RAW_SECRET
            rows.append(row)
        (root / f"{category}.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")


def test_builder_writes_8x20_compact_manifests_from_sanitized_metadata(tmp_path):
    source_root = tmp_path / "source"
    output_root = tmp_path / "out"
    write_source_metadata(source_root)

    written = builder.write_manifests(source_root, output_root)

    assert len(written) == 8
    result = checker.check_root(output_root)
    assert result["blockers"] == []
    assert sum(result["category_counts"].values()) == 160
    for category in builder.APPROVED_CATEGORIES:
        path = output_root / f"{category}.jsonl"
        records = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(records) == 20
        for ordinal, record in enumerate(records):
            assert set(record) == {"category", "ordinal", "prompt_family", "compact_source_hash"}
            assert record["category"] == category
            assert record["ordinal"] == ordinal
            assert record["prompt_family"] == builder.CATEGORY_PROMPT_FAMILY[category]
            assert len(record["compact_source_hash"]) == 64
            assert "case_id" not in str(record).lower()
            assert RAW_SECRET not in str(record)
            assert category not in record["compact_source_hash"]


def test_builder_missing_source_root_reports_precise_blocker(tmp_path):
    missing_root = tmp_path / "missing"

    blockers = builder.check_plan(missing_root)

    assert blockers == [f"approved_bfcl_source_metadata_missing:{missing_root}"]


def test_checker_missing_manifest_root_reports_precise_blocker(tmp_path):
    missing_root = tmp_path / "missing"

    result = checker.check_root(missing_root)

    assert result["blockers"] == [f"approved_source_input_root_missing:{missing_root}"]
    assert result["category_counts"] == {}


def test_builder_rejects_raw_or_forbidden_source_metadata(tmp_path):
    for raw_field in ["case_id", "raw_prompt", "gold", "expected", "reference", "scorer_diff", "candidate_output", "repair_output", "feedback", "holdout_feedback", "full_suite_feedback"]:
        source_root = tmp_path / raw_field
        write_source_metadata(source_root, raw_field=raw_field)
        blockers = builder.check_plan(source_root)
        assert blockers
        assert any("approved_source_input_forbidden_field" in blocker for blocker in blockers)
        assert all(RAW_SECRET not in blocker for blocker in blockers)


def test_builder_rejects_wrong_count_prompt_family_and_extra_fields(tmp_path):
    source_root = tmp_path / "source"
    write_source_metadata(source_root)
    path = source_root / "agentic_web_search.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["prompt_family"] = "raw task summary not taxonomy"
    rows[1]["unexpected"] = "not allowed"
    rows = rows[:-1]
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")

    blockers = builder.check_plan(source_root)

    assert any("approved_source_input_count_not_signed:agentic_web_search:19" in blocker for blocker in blockers)

    write_source_metadata(source_root)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["prompt_family"] = "raw task summary not taxonomy"
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")
    blockers = builder.check_plan(source_root)
    assert any("approved_source_input_prompt_family_not_signed" in blocker for blocker in blockers)

    write_source_metadata(source_root)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]["unexpected"] = "not allowed"
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")
    blockers = builder.check_plan(source_root)
    assert any("approved_source_input_extra_field:unexpected" in blocker for blocker in blockers)


def test_builder_rejects_wrong_source_family_id(tmp_path):
    source_root = tmp_path / "source_family"
    write_source_metadata(source_root)
    path = source_root / "agentic_web_search.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["source_family_id"] = "agentic_web_case_0"
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")

    blockers = builder.check_plan(source_root)

    assert any("approved_source_input_source_family_id_not_signed" in blocker for blocker in blockers)


def test_checker_rejects_manifest_extra_fields_bad_ordinals_and_raw_values(tmp_path):
    source_root = tmp_path / "source"
    output_root = tmp_path / "out"
    write_source_metadata(source_root)
    builder.write_manifests(source_root, output_root)
    path = output_root / "agentic_web_search.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["case_id"] = "raw-case-id"
    rows[1]["ordinal"] = 99
    rows[2]["prompt_family"] = "raw_prompt_summary"
    rows[3]["compact_source_hash"] = "not-a-hash"
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")

    blockers = checker.check_root(output_root)["blockers"]

    assert any("compact_source_input_extra_field:case_id" in blocker for blocker in blockers)
    assert any("compact_source_input_forbidden_field:case_id" in blocker for blocker in blockers)
    assert any("compact_source_input_ordinal_not_continuous:agentic_web_search:99:1" in blocker for blocker in blockers)
    assert any("compact_source_input_prompt_family_not_taxonomy" in blocker for blocker in blockers)
    assert any("compact_source_input_hash_format_invalid:agentic_web_search:3" in blocker for blocker in blockers)


def test_checker_cli_default_root_passes_after_manifest_preparation():
    result = subprocess.run(
        [sys.executable, "scripts/check_rashe_source_inputs_compact.py", "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_source_inputs_compact_passed"] is True
    assert summary["total_cases"] == 160
    assert summary["blockers"] == []


def test_builder_cli_dry_run_missing_source_root_is_precise(tmp_path):
    result = subprocess.run(
        [sys.executable, "scripts/build_rashe_source_inputs_compact.py", "--source-root", str(tmp_path / "missing"), "--dry-run", "--compact"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    summary = json.loads(result.stdout)
    assert summary["rashe_source_inputs_compact_builder_passed"] is False
    assert summary["written_manifests"] == []
    assert any(blocker.startswith("approved_bfcl_source_metadata_missing:") for blocker in summary["blockers"])
