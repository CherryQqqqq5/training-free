import scripts.diagnose_directory_obligation_readonly as audit


def test_directory_readonly_candidate_when_list_without_trajectory() -> None:
    row = audit._classify({"trace_id": "c", "postcondition_gap": "directory_navigation", "user_text_excerpt": "Please list the files in the temp directory."})
    assert row["directory_obligation_label"] == "readonly_directory_obligation_candidate"
    assert row["retain_prior_candidate"] is True


def test_directory_trajectory_stays_diagnostic() -> None:
    row = audit._classify({"trace_id": "c", "postcondition_gap": "directory_navigation", "user_text_excerpt": "Go to temp directory and for each file count the lines."})
    assert row["directory_obligation_label"] == "diagnostic_stateful_directory_trajectory"
    assert row["retain_prior_candidate"] is False


def test_directory_mutation_adjacent_rejected() -> None:
    row = audit._classify({"trace_id": "c", "postcondition_gap": "directory_navigation", "user_text_excerpt": "Create a file in the reports folder."})
    assert row["directory_obligation_label"] == "reject_mutation_adjacent_directory_request"
    assert row["retain_prior_candidate"] is False


def test_directory_audit_has_no_scorer_commands(tmp_path) -> None:
    report = audit.evaluate(tmp_path / "missing.json")
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["does_not_authorize_scorer"] is True
