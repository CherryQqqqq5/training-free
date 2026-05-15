from __future__ import annotations

import json
from pathlib import Path

from scripts.check_abhe_trace_cards import validate_card, validate_schema

FIXTURE_ROOT = Path("tests/fixtures/abhe_trace_cards")


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_trace_card_schema_accepts_current_contract() -> None:
    schema = json.loads(Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_card.schema.json").read_text(encoding="utf-8"))
    assert validate_schema(schema) == []


def test_trace_card_accepts_valid_state_tracking_card() -> None:
    blockers = validate_card(load_fixture("valid_state_tracking_card.json"), "state_card")
    assert blockers == []


def test_trace_card_accepts_valid_hallucination_card() -> None:
    blockers = validate_card(load_fixture("valid_hallucination_card.json"), "hallucination_card")
    assert blockers == []


def test_trace_card_rejects_raw_case_id() -> None:
    blockers = validate_card(load_fixture("reject_raw_case_id.json"), "raw_card")
    assert any("raw_case_id" in blocker for blocker in blockers)


def test_trace_card_rejects_missing_state_variable_for_state_tracking() -> None:
    blockers = validate_card(load_fixture("reject_missing_state_variable.json"), "state_card")
    assert any("state_variable_lost_required_for_state_tracking" in blocker for blocker in blockers)


def test_trace_card_rejects_missing_answerability_kind_for_hallucination() -> None:
    blockers = validate_card(load_fixture("reject_missing_answerability_kind.json"), "hallucination_card")
    assert any("answerability_failure_kind_required_for_hallucination_abstain" in blocker for blocker in blockers)


def test_trace_card_rejects_forbidden_fields_absent_false() -> None:
    card = load_fixture("valid_state_tracking_card.json")
    card["forbidden_fields_absent"] = False
    blockers = validate_card(card, "state_card")
    assert any("forbidden_fields_absent_not_true" in blocker for blocker in blockers)
