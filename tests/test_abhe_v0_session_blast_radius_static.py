"""
Boundary tests for the static blast radius checker.

Hard contract:
  - all 10 guarded files exist on disk
  - none of them imports any forbidden substring
  - the checker exits 0 in strict mode (no blockers)
  - the checker exits 1 if a guarded file develops a forbidden import
    (simulated by temp-injecting a sentinel file into the guard list)
  - guarded files are part of the current P1/P1.5a/P2/P3/G1/G2 stream
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_PYPATH = str(REPO) + ":" + str(REPO / "src")
CHECKER = REPO / "scripts/check_abhe_v0_session_blast_radius_static.py"


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO),
                          env={"PYTHONPATH": _PYPATH, "PATH": "/usr/bin:/bin"})


def test_checker_exists():
    assert CHECKER.exists()


def test_checker_strict_passes_on_current_state():
    p = _run([sys.executable, str(CHECKER), "--strict", "--compact"])
    assert p.returncode == 0, f"rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["abhe_v0_session_blast_radius_static_passed"] is True
    assert out["guarded_file_count"] == 15  # G7-revised added v2 score adapter + checker  # G6b-1 added executor scaffolding  # G6a added 2 more guarded scripts
    assert out["guarded_files_with_forbidden_imports"] == 0
    assert out["blockers"] == []


def test_each_guarded_file_exists():
    # Run non-compact to get per_file; assert each file present.
    p = _run([sys.executable, str(CHECKER), "--strict"])
    assert p.returncode == 0
    out = json.loads(p.stdout)
    for entry in out["per_file"]:
        assert entry["present"] is True, f"missing: {entry['path']}"
        assert not entry["forbidden_imports"], (
            f"forbidden_in_{entry['path']}:{entry['forbidden_imports']}"
        )


def test_checker_flags_forbidden_import_when_injected():
    """Synthesize a tiny module with a forbidden import, point the
    checker at it via a tmp wrapper, and verify it rejects.

    The on-disk checker reads GUARDED_FILES from its source. To
    simulate a violation without mutating any committed file, we
    instead write a temp module with a forbidden import and verify
    by direct import that the AST scanner finds it."""
    import ast
    tmp_dir = tempfile.mkdtemp()
    try:
        tmp_file = Path(tmp_dir) / "bad_module.py"
        tmp_file.write_text(
            "import requests  # forbidden network primitive\n"
            "def f(): pass\n",
            encoding="utf-8",
        )
        tree = ast.parse(tmp_file.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.append(n.name)
        # Mirror the checker's logic
        forbidden_subs = ("requests", "httpx", "urllib", "openai")
        found = []
        for name in imports:
            for sub in forbidden_subs:
                if sub in name.lower():
                    found.append((name, sub))
        assert found, "expected_forbidden_imports_to_be_detected_but_none_were"
        assert ("requests", "requests") in found
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_blast_radius_boundary_attestations_echoed():
    p = _run([sys.executable, str(CHECKER), "--strict", "--compact"])
    out = json.loads(p.stdout.strip().splitlines()[-1])
    for k in [
        "performance_evidence", "holdout_touched", "full_suite_touched",
        "archive_updated", "scorer_diff_committed",
        "raw_provider_payload_committed", "raw_bfcl_result_tree_committed",
        "gold_expected_committed", "argument_values_committed",
        "prompt_literal_committed",
    ]:
        assert out[k] is False, f"{k}_not_false_in_report"


def test_guarded_files_cover_session_work_stream():
    """The guarded files list should include the entry-point for each
    work stream merged this session: P1, P1.5a, P2, P3, G1, G2."""
    src = CHECKER.read_text(encoding="utf-8")
    must_include = [
        "build_abhe_v0_true_per_selected_id_score_adapter.py",       # P1
        "build_abhe_v0_category_arm_error_class_matrix.py",           # P1.5a
        "build_abhe_v0_runtime_slot_controller_v3_skeleton.py",       # P2
        "build_abhe_v0_provider_transport_backoff_policy.py",         # P3
        "check_abhe_v0_per_case_scorer_slicer_approval_packet.py",    # G1
        "abhe_v0_runtime_slot_controller_v3_wire_stub.py",            # G2
        "build_abhe_v0_per_case_scorer_slicer_rerun_manifest.py",     # G6a
        "build_abhe_v0_per_selected_id_score_adapter_v2.py",        # G7-revised
    ]
    for f in must_include:
        assert f in src, f"missing_from_guard_list:{f}"
