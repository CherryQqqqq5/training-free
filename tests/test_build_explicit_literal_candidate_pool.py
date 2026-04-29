from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_explicit_literal_candidate_pool import build


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_explicit_literal_candidate_pool.py"


def test_build_explicit_literal_candidate_pool_help() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "--source-root" in result.stdout
    assert "--source-manifest" in result.stdout
    assert "--dataset-json" in result.stdout
    assert "--categories" in result.stdout
    assert "--candidate-jsonl" in result.stdout
    assert "--audit-json" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--out-candidates" in result.stdout


def test_build_explicit_literal_candidate_pool_empty_input_fails_closed(tmp_path: Path) -> None:
    report = build(
        source_manifest=tmp_path / "missing_source_manifest.json",
        dataset_json=tmp_path / "missing_dataset.json",
        out_candidates=tmp_path / "candidate_rules.jsonl",
        dev_manifest=tmp_path / "dev20.json",
        holdout_manifest=tmp_path / "holdout20.json",
        summary_output=tmp_path / "summary.json",
        markdown_output=tmp_path / "summary.md",
    )

    assert report["candidate_pool_build_passed"] is False
    assert report["offline_only"] is True
    assert report["does_not_call_provider"] is True
    assert report["does_not_call_bfcl_or_model"] is True
    assert report["does_not_authorize_scorer"] is True
    assert report["candidate_jsonl"] == str(tmp_path / "candidate_rules.jsonl")
    assert report["audit_json"] == str(tmp_path / "explicit_literal_extractor_audit.json")
    assert report["requested_categories"] == []
    assert report["candidate_jsonl_written"] is True
    assert report["audit_json_written"] is True
    assert report["manifests_written"] is True
    assert "source_collection_manifest_missing" in report["blockers"]
    assert "dataset_json_missing" in report["blockers"]
    assert (tmp_path / "candidate_rules.jsonl").read_text(encoding="utf-8") == ""
    audit = json.loads((tmp_path / "explicit_literal_extractor_audit.json").read_text(encoding="utf-8"))
    assert audit["requested_categories"] == []
    assert audit["planned_commands"] == []
    assert audit["candidate_commands"] == []
    dev = json.loads((tmp_path / "dev20.json").read_text(encoding="utf-8"))
    holdout = json.loads((tmp_path / "holdout20.json").read_text(encoding="utf-8"))
    assert dev["selected_case_ids"] == []
    assert holdout["selected_case_ids"] == []


def test_build_explicit_literal_candidate_pool_accepts_fixture_ready_interface(tmp_path: Path) -> None:
    source_manifest = tmp_path / "source_collection_manifest.json"
    source_manifest.write_text(json.dumps({
        "category_status": [{"category": "multi_turn_miss_func"}],
    }) + "\n", encoding="utf-8")

    report = build(
        source_root=tmp_path / "source_root",
        source_manifest=source_manifest,
        dataset_json=tmp_path / "missing_dataset.json",
        categories="multi_turn_miss_func,multiple",
        output_root=tmp_path / "out",
        candidate_jsonl=tmp_path / "out" / "candidate_rules.jsonl",
        audit_json=tmp_path / "out" / "audit.json",
        dev_manifest=tmp_path / "out" / "dev20.json",
        holdout_manifest=tmp_path / "out" / "holdout20.json",
        summary_output=tmp_path / "out" / "summary.json",
        markdown_output=tmp_path / "out" / "summary.md",
        min_pool_size=35,
    )

    assert report["candidate_pool_build_passed"] is False
    assert report["source_root"] == str(tmp_path / "source_root")
    assert report["source_manifest_categories"] == ["multi_turn_miss_func"]
    assert report["requested_categories"] == ["multi_turn_miss_func", "multiple"]
    assert report["candidate_jsonl"] == str(tmp_path / "out" / "candidate_rules.jsonl")
    assert report["audit_json"] == str(tmp_path / "out" / "audit.json")
    assert report["min_pool_size"] == 35


def _write_json(path: Path, payload) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_build_explicit_literal_candidate_pool_extracts_one_fixture_candidate(tmp_path: Path) -> None:
    source_root = tmp_path / "source" / "multi_turn_miss_func" / "baseline"
    result_path = source_root / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_func_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({"id": "case_1", "result": [{"grep": json.dumps({"pattern": "urgent"})}]}) + "\n", encoding="utf-8")
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": "multi_turn_miss_func", "existing_source_roots": [str(source_root)]}]})
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "case_1",
        "question": [[{"role": "user", "content": "Search 'notes.txt' for urgent lines."}]],
        "function": [{
            "name": "grep",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}, "file_name": {"type": "string"}},
                "required": ["pattern", "file_name"],
            },
        }],
    }])

    report = build(
        source_manifest=source_manifest,
        dataset_json=dataset,
        out_candidates=tmp_path / "candidate_rules.jsonl",
        dev_manifest=tmp_path / "dev20.json",
        holdout_manifest=tmp_path / "holdout20.json",
        summary_output=tmp_path / "summary.json",
        markdown_output=tmp_path / "summary.md",
        min_eligible=1,
        dev_count=1,
        holdout_count=0,
    )

    assert report["candidate_pool_build_passed"] is True
    assert report["candidate_record_count"] == 1
    rows = [json.loads(line) for line in (tmp_path / "candidate_rules.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["case_id"] == "case_1"
    assert rows[0]["schema_arg_name"] == "file_name"
    assert rows[0]["selected_literal"] == "notes.txt"
    assert rows[0]["literal_source"] == "current_request"
    assert rows[0]["used_gold_fields"] is False


def test_build_explicit_literal_candidate_pool_rejects_non_unique_literal(tmp_path: Path) -> None:
    source_root = tmp_path / "source" / "multi_turn_miss_func" / "baseline"
    result_path = source_root / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_func_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({"id": "case_1", "result": [{"grep": json.dumps({"pattern": "urgent"})}]}) + "\n", encoding="utf-8")
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": "multi_turn_miss_func", "existing_source_roots": [str(source_root)]}]})
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "case_1",
        "question": [[{"role": "user", "content": "Compare 'a.txt' and 'b.txt'."}]],
        "function": [{
            "name": "grep",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}, "file_name": {"type": "string"}},
                "required": ["pattern", "file_name"],
            },
        }],
    }])

    report = build(
        source_manifest=source_manifest,
        dataset_json=dataset,
        out_candidates=tmp_path / "candidate_rules.jsonl",
        dev_manifest=tmp_path / "dev20.json",
        holdout_manifest=tmp_path / "holdout20.json",
        summary_output=tmp_path / "summary.json",
        markdown_output=tmp_path / "summary.md",
        min_eligible=1,
        dev_count=1,
        holdout_count=0,
    )

    assert report["candidate_pool_build_passed"] is False
    assert report["candidate_record_count"] == 0
    assert report["reject_reason_counts"]["ambiguous_literal"] == 1
    assert "eligible_explicit_literal_candidates_below_minimum" in report["blockers"]


def test_build_explicit_literal_candidate_pool_extracts_current_observation_candidate(tmp_path: Path) -> None:
    source_root = tmp_path / "source" / "multi_turn_miss_func" / "baseline"
    result_path = source_root / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_func_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps({
            "id": "case_1",
            "current_observation": "The active file is 'observed.txt'.",
            "result": [{"grep": json.dumps({"pattern": "urgent"})}],
        }) + "\n",
        encoding="utf-8",
    )
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": "multi_turn_miss_func", "existing_source_roots": [str(source_root)]}]})
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "case_1",
        "question": [[{"role": "user", "content": "Search the active file for urgent lines."}]],
        "function": [{
            "name": "grep",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}, "file_name": {"type": "string"}},
                "required": ["pattern", "file_name"],
            },
        }],
    }])

    report = build(
        source_manifest=source_manifest,
        dataset_json=dataset,
        out_candidates=tmp_path / "candidate_rules.jsonl",
        dev_manifest=tmp_path / "dev20.json",
        holdout_manifest=tmp_path / "holdout20.json",
        summary_output=tmp_path / "summary.json",
        markdown_output=tmp_path / "summary.md",
        min_eligible=1,
        dev_count=1,
        holdout_count=0,
    )

    assert report["candidate_pool_build_passed"] is True
    rows = [json.loads(line) for line in (tmp_path / "candidate_rules.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["selected_literal"] == "observed.txt"
    assert rows[0]["literal_source"] == "current_observation"
    assert rows[0]["literal_source_span"]["source"] == "current_observation"


def test_build_explicit_literal_candidate_pool_request_wins_when_observation_matches(tmp_path: Path) -> None:
    source_root = tmp_path / "source" / "multi_turn_miss_func" / "baseline"
    result_path = source_root / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_func_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps({
            "id": "case_1",
            "current_observation": "The active file is 'notes.txt'.",
            "result": [{"grep": json.dumps({"pattern": "urgent"})}],
        }) + "\n",
        encoding="utf-8",
    )
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": "multi_turn_miss_func", "existing_source_roots": [str(source_root)]}]})
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "case_1",
        "question": [[{"role": "user", "content": "Search 'notes.txt' for urgent lines."}]],
        "function": [{
            "name": "grep",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}, "file_name": {"type": "string"}},
                "required": ["pattern", "file_name"],
            },
        }],
    }])

    report = build(
        source_manifest=source_manifest,
        dataset_json=dataset,
        out_candidates=tmp_path / "candidate_rules.jsonl",
        dev_manifest=tmp_path / "dev20.json",
        holdout_manifest=tmp_path / "holdout20.json",
        summary_output=tmp_path / "summary.json",
        markdown_output=tmp_path / "summary.md",
        min_eligible=1,
        dev_count=1,
        holdout_count=0,
    )

    assert report["candidate_pool_build_passed"] is True
    rows = [json.loads(line) for line in (tmp_path / "candidate_rules.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["selected_literal"] == "notes.txt"
    assert rows[0]["literal_source"] == "current_request"
    assert rows[0]["literal_source_span"]["source"] == "current_request"


def test_build_explicit_literal_candidate_pool_rejects_request_observation_conflict(tmp_path: Path) -> None:
    source_root = tmp_path / "source" / "multi_turn_miss_func" / "baseline"
    result_path = source_root / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_func_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps({
            "id": "case_1",
            "current_observation": "The active file is 'observed.txt'.",
            "result": [{"grep": json.dumps({"pattern": "urgent"})}],
        }) + "\n",
        encoding="utf-8",
    )
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": "multi_turn_miss_func", "existing_source_roots": [str(source_root)]}]})
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "case_1",
        "question": [[{"role": "user", "content": "Search 'request.txt' for urgent lines."}]],
        "function": [{
            "name": "grep",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}, "file_name": {"type": "string"}},
                "required": ["pattern", "file_name"],
            },
        }],
    }])

    report = build(
        source_manifest=source_manifest,
        dataset_json=dataset,
        out_candidates=tmp_path / "candidate_rules.jsonl",
        dev_manifest=tmp_path / "dev20.json",
        holdout_manifest=tmp_path / "holdout20.json",
        summary_output=tmp_path / "summary.json",
        markdown_output=tmp_path / "summary.md",
        min_eligible=1,
        dev_count=1,
        holdout_count=0,
    )

    assert report["candidate_pool_build_passed"] is False
    assert report["candidate_record_count"] == 0
    assert report["reject_reason_counts"]["ambiguous_observable_literal"] == 1
    assert (tmp_path / "candidate_rules.jsonl").read_text(encoding="utf-8") == ""


def test_build_explicit_literal_candidate_pool_rejects_parallel_call_mapping_not_unique(tmp_path: Path) -> None:
    source_root = tmp_path / "source" / "multi_turn_miss_func" / "baseline"
    result_path = source_root / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_func_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps({
            "id": "case_1",
            "result": [
                {"grep": json.dumps({"pattern": "urgent"})},
                {"cat": json.dumps({})},
            ],
        }) + "\n",
        encoding="utf-8",
    )
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": "multi_turn_miss_func", "existing_source_roots": [str(source_root)]}]})
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "case_1",
        "question": [[{"role": "user", "content": "Search 'notes.txt' for urgent lines."}]],
        "function": [
            {
                "name": "grep",
                "parameters": {
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}, "file_name": {"type": "string"}},
                    "required": ["pattern", "file_name"],
                },
            },
            {
                "name": "cat",
                "parameters": {
                    "type": "object",
                    "properties": {"file_name": {"type": "string"}},
                    "required": ["file_name"],
                },
            },
        ],
    }])

    report = build(
        source_manifest=source_manifest,
        dataset_json=dataset,
        out_candidates=tmp_path / "candidate_rules.jsonl",
        dev_manifest=tmp_path / "dev20.json",
        holdout_manifest=tmp_path / "holdout20.json",
        summary_output=tmp_path / "summary.json",
        markdown_output=tmp_path / "summary.md",
        min_eligible=1,
        dev_count=1,
        holdout_count=0,
    )

    assert report["candidate_pool_build_passed"] is False
    assert report["candidate_record_count"] == 0
    assert report["reject_reason_counts"]["parallel_call_mapping_not_unique"] == 1
    assert (tmp_path / "candidate_rules.jsonl").read_text(encoding="utf-8") == ""


def test_build_explicit_literal_candidate_pool_rejects_missing_source_result(tmp_path: Path) -> None:
    source_root = tmp_path / "source" / "multi_turn_miss_func" / "baseline"
    source_root.mkdir(parents=True)
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": "multi_turn_miss_func", "existing_source_roots": [str(source_root)]}]})
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{"id": "case_1", "question": [[{"role": "user", "content": "Search 'notes.txt'."}]], "function": []}])

    report = build(
        source_manifest=source_manifest,
        dataset_json=dataset,
        out_candidates=tmp_path / "candidate_rules.jsonl",
        dev_manifest=tmp_path / "dev20.json",
        holdout_manifest=tmp_path / "holdout20.json",
        summary_output=tmp_path / "summary.json",
        markdown_output=tmp_path / "summary.md",
        min_eligible=1,
        dev_count=1,
        holdout_count=0,
    )

    assert report["candidate_pool_build_passed"] is False
    assert report["reject_reason_counts"]["missing_source_result"] == 1


def test_build_explicit_literal_candidate_pool_rejects_schema_type_mismatch(tmp_path: Path) -> None:
    source_root = tmp_path / "source" / "multi_turn_miss_func" / "baseline"
    result_path = source_root / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_func_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({"id": "case_1", "result": [{"calc": json.dumps({"height": 7})}]}) + "\n", encoding="utf-8")
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": "multi_turn_miss_func", "existing_source_roots": [str(source_root)]}]})
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "case_1",
        "question": [[{"role": "user", "content": "Use 'notes.txt' as the base."}]],
        "function": [{
            "name": "calc",
            "parameters": {
                "type": "object",
                "properties": {"height": {"type": "integer"}, "base": {"type": "integer"}},
                "required": ["height", "base"],
            },
        }],
    }])

    report = build(
        source_manifest=source_manifest,
        dataset_json=dataset,
        out_candidates=tmp_path / "candidate_rules.jsonl",
        dev_manifest=tmp_path / "dev20.json",
        holdout_manifest=tmp_path / "holdout20.json",
        summary_output=tmp_path / "summary.json",
        markdown_output=tmp_path / "summary.md",
        min_eligible=1,
        dev_count=1,
        holdout_count=0,
    )

    assert report["candidate_pool_build_passed"] is False
    assert report["candidate_record_count"] == 0
    assert report["reject_reason_counts"]["schema_type_mismatch"] == 1
