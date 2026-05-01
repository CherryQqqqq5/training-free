import json

import pytest

from scripts import rashe_source_case_provider as case_provider


RAW_SECRET = "raw prompt text secret must not leak"


def signed_request(root, **overrides):
    request = {
        "categories": list(case_provider.APPROVED_CATEGORIES),
        "case_count_per_category": 20,
        "max_total_cases": 160,
        "source_input_root": str(root),
        "source_case_provider_fixture_mode": True,
    }
    request.update(overrides)
    return request


def category_request(category="agentic_web_search", **overrides):
    request = {
        "category": category,
        "case_count": 20,
        "compact_sanitized_only": True,
        "raw_payload_capture_authorized": False,
        "raw_trace_capture_authorized": False,
    }
    request.update(overrides)
    return request


def write_fixture(root, *, raw_field=None, categories=None, count=20):
    categories = categories or case_provider.APPROVED_CATEGORIES
    root.mkdir(parents=True, exist_ok=True)
    for category in categories:
        rows = []
        for ordinal in range(count):
            row = {
                "category": category,
                "ordinal": ordinal,
                "prompt_family": f"{category}_family",
                "compact_source_hash": f"fixture-source-hash-{category}-{ordinal}",
            }
            if raw_field:
                row[raw_field] = RAW_SECRET
            rows.append(row)
        (root / f"{category}.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")


def build_provider(root):
    return case_provider.build_signed_source_case_provider(signed_request(root))


def test_signed_source_case_provider_fixture_returns_8x20_sanitized_descriptors(tmp_path):
    write_fixture(tmp_path)
    provider = build_provider(tmp_path)

    all_records = []
    for category in case_provider.APPROVED_CATEGORIES:
        records = provider(category_request(category))
        assert len(records) == 20
        all_records.extend(records)
        for ordinal, record in enumerate(records):
            assert set(record) == case_provider.ALLOWED_OUTPUT_FIELDS
            assert record["category"] == category
            assert record["ordinal"] == ordinal
            assert record["prompt_family"] == f"{category}_family"
            assert len(record["compact_hash"]) == 32
            assert RAW_SECRET not in str(record)
            assert "case_id" not in str(record).lower()
            assert "prompt" not in record["compact_hash"].lower()

    assert len(all_records) == 160


def test_compact_hash_is_stable_and_does_not_embed_raw_content(tmp_path):
    write_fixture(tmp_path)
    provider = build_provider(tmp_path)

    first = provider(category_request("agentic_web_search"))[0]
    second = provider(category_request("agentic_web_search"))[0]

    assert first["compact_hash"] == second["compact_hash"]
    assert first["compact_hash"] != "fixture-source-hash-agentic_web_search-0"
    assert "agentic_web_search" not in first["compact_hash"]
    assert RAW_SECRET not in str(first)


def test_source_case_provider_rejects_invalid_category_and_count(tmp_path):
    write_fixture(tmp_path)
    provider = build_provider(tmp_path)

    with pytest.raises(case_provider.SourceCaseProviderError, match="source_case_provider_category_not_signed"):
        provider(category_request("not_signed"))

    with pytest.raises(case_provider.SourceCaseProviderError, match="source_case_provider_case_count_not_signed"):
        provider(category_request(case_count=25))


def test_source_case_provider_rejects_forbidden_raw_fields(tmp_path):
    for raw_field in ["case_id", "gold", "expected", "reference", "scorer_diff", "raw_prompt", "candidate_output", "repair_output", "feedback", "holdout_feedback", "full_suite_feedback"]:
        root = tmp_path / raw_field
        write_fixture(root, raw_field=raw_field)
        provider = build_provider(root)
        with pytest.raises(case_provider.SourceCaseProviderError) as exc_info:
            provider(category_request("agentic_web_search"))
        message = str(exc_info.value)
        assert "source_case_provider_forbidden_input_field" in message
        assert raw_field in message
        assert RAW_SECRET not in message


def test_source_case_provider_rejects_extra_fields_and_bad_ordinals(tmp_path):
    write_fixture(tmp_path)
    path = tmp_path / "agentic_web_search.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["unexpected"] = "compact-only but unsigned"
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")
    provider = build_provider(tmp_path)
    with pytest.raises(case_provider.SourceCaseProviderError, match="source_case_provider_input_extra_field:unexpected"):
        provider(category_request("agentic_web_search"))

    write_fixture(tmp_path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]["ordinal"] = 99
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")
    provider = build_provider(tmp_path)
    with pytest.raises(case_provider.SourceCaseProviderError, match="source_case_provider_ordinal_not_signed"):
        provider(category_request("agentic_web_search"))


def test_source_case_provider_missing_signed_inputs_is_precise():
    provider = case_provider.build_signed_source_case_provider({
        "categories": list(case_provider.APPROVED_CATEGORIES),
        "case_count_per_category": 20,
        "max_total_cases": 160,
    })

    with pytest.raises(case_provider.SourceCaseProviderError, match="bfcl_source_inputs_missing"):
        provider(category_request("agentic_web_search"))


def test_source_case_provider_rejects_unsigned_builder_scope(tmp_path):
    with pytest.raises(case_provider.SourceCaseProviderError, match="source_case_provider_categories_not_signed"):
        case_provider.build_signed_source_case_provider(signed_request(tmp_path, categories=["agentic_web_search"]))

    with pytest.raises(case_provider.SourceCaseProviderError, match="source_case_provider_case_count_not_signed"):
        case_provider.build_signed_source_case_provider(signed_request(tmp_path, case_count_per_category=25))

    with pytest.raises(case_provider.SourceCaseProviderError, match="source_case_provider_root_not_signed"):
        case_provider.build_signed_source_case_provider({"source_input_root": str(tmp_path)})
