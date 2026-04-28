from __future__ import annotations

from pathlib import Path

import scripts.check_artifact_boundary as boundary


def test_forbidden_output_patterns_include_untracked_sensitive_artifacts() -> None:
    bad = [
        "outputs/artifacts/run/bfcl/.env",
        "outputs/artifacts/run/artifacts/repairs.jsonl",
        "outputs/artifacts/phase2/foo_repair_records.jsonl",
        "outputs/artifacts/run/traces/trace.json",
        "outputs/artifacts/run/bfcl/result/model/out.json",
        "outputs/artifacts/run/bfcl/score/model/score.csv",
        "outputs/artifacts/run/logs/run.log",
    ]
    assert boundary.forbidden_outputs(bad) == sorted(bad)


def test_compact_summaries_are_allowed() -> None:
    paths = [
        "outputs/artifacts/bfcl_explicit_required_arg_literal_v1/m28pre_offline_summary.json",
        "outputs/artifacts/bfcl_explicit_required_arg_literal_v1/compiler_summary.md",
        "outputs/README.md",
    ]
    assert boundary.forbidden_outputs(paths) == []


def test_filesystem_scan_catches_ignored_env_and_repair_records(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    env = tmp_path / "outputs" / "artifacts" / "run" / "bfcl" / ".env"
    repair = tmp_path / "outputs" / "artifacts" / "phase2" / "foo_repair_records.jsonl"
    summary = tmp_path / "outputs" / "artifacts" / "run" / "summary.json"
    for path in [env, repair, summary]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    monkeypatch.setattr(boundary, "tracked_files", lambda root="outputs": [])

    bad = boundary.forbidden_outputs(boundary.collect_output_paths())

    assert "outputs/artifacts/run/bfcl/.env" in bad
    assert "outputs/artifacts/phase2/foo_repair_records.jsonl" in bad
    assert "outputs/artifacts/run/summary.json" not in bad
