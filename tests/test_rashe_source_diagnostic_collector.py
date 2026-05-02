import pytest

from grc.bfcl import source_diagnostic_collector as collector


def signed_request(**overrides):
    request = {
        "provider_profile": "Chuangzhi/Novacode",
        "model": "gpt-4.1",
        "categories": list(collector.APPROVED_CATEGORIES),
        "case_count_per_category": 20,
        "max_total_cases": 160,
        "output_root": "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/",
        "schema_path": "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json",
        "forbidden_fields": list(collector.FORBIDDEN_FIELD_NAMES),
        "failure_buckets": list(collector.FAILURE_BUCKETS),
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "raw_payload_capture_authorized": False,
        "raw_trace_capture_authorized": False,
        "compact_sanitized_only": True,
    }
    request.update(overrides)
    return request


def mock_provider(result_overrides=None, seen=None):
    result_overrides = result_overrides or {}
    seen = seen if seen is not None else []

    def provider(category_request):
        seen.append(category_request)
        assert "api_key" not in str(category_request).lower()
        return {
            "category": category_request["category"],
            "case_count": 20,
            "provider_call_count": 20,
            "failure_bucket_counts": {bucket: 0 for bucket in collector.FAILURE_BUCKETS},
            "raw_payload_tracked_count": 0,
            "forbidden_field_violation_count": 0,
            "candidate_generation_authorized": False,
            "scorer_authorized": False,
            "performance_evidence": False,
            **result_overrides,
        }

    return provider


def test_collector_accepts_signed_request_with_mock_provider_and_returns_8x20(monkeypatch):
    monkeypatch.setenv("CHUANGZHI_API_KEY", "must-not-be-read")
    seen = []
    request = signed_request(provider_client=mock_provider(seen=seen))

    records = collector.collect_compact_source_diagnostics(request)

    assert len(records) == 8
    assert [record["category"] for record in records] == list(collector.APPROVED_CATEGORIES)
    assert sum(record["case_count"] for record in records) == 160
    assert len(seen) == 8
    for record in records:
        assert set(record) == collector.ALLOWED_RECORD_FIELDS
        assert record["case_count"] == 20
        assert record["provider_call_count"] == 20
        assert record["raw_payload_tracked_count"] == 0
        assert record["forbidden_field_violation_count"] == 0
        assert record["candidate_generation_authorized"] is False
        assert record["scorer_authorized"] is False
        assert record["performance_evidence"] is False
        assert set(record["failure_bucket_counts"]) == set(collector.FAILURE_BUCKETS)


def test_collector_fails_closed_without_provider_client(monkeypatch):
    monkeypatch.setenv("CHUANGZHI_API_KEY", "must-not-be-read")
    with pytest.raises(collector.SourceDiagnosticCollectorError, match="source_provider_client_missing"):
        collector.collect_compact_source_diagnostics(signed_request())


def test_collector_rejects_unsigned_request_fields():
    for key, value, expected in [
        ("provider_profile", "Unsigned", "collector_provider_profile_not_signed"),
        ("model", "gpt-5.2", "collector_model_not_signed"),
        ("categories", ["agentic_web_search"], "collector_categories_not_signed"),
        ("case_count_per_category", 25, "collector_case_count_per_category_not_signed"),
        ("max_total_cases", 200, "collector_max_total_cases_not_signed"),
        ("candidate_generation_authorized", True, "collector_forbidden_flag_not_false:candidate_generation_authorized"),
    ]:
        request = signed_request(provider_client=mock_provider(), **{key: value})
        blockers = collector.validate_request(request)
        assert any(expected in blocker for blocker in blockers), (key, blockers)


def test_collector_rejects_forbidden_provider_output_and_does_not_persist_raw_response():
    request = signed_request(provider_client=mock_provider({"case_id": "raw-case-id"}))
    with pytest.raises(collector.SourceDiagnosticCollectorError) as exc_info:
        collector.collect_compact_source_diagnostics(request)
    message = str(exc_info.value)
    assert "collector_provider_result_forbidden_field" in message
    assert "case_id" in message


def test_collector_rejects_downstream_flags_and_nonzero_leakage_counts():
    for overrides, expected in [
        ({"raw_payload_tracked_count": 1}, "collector_raw_payload_tracked_count_not_zero:1"),
        ({"forbidden_field_violation_count": 1}, "collector_forbidden_field_violation_count_not_zero:1"),
        ({"candidate_generation_authorized": True}, "collector_candidate_generation_authorized_not_false:True"),
        ({"scorer_authorized": True}, "collector_scorer_authorized_not_false:True"),
        ({"performance_evidence": True}, "collector_performance_evidence_not_false:True"),
    ]:
        request = signed_request(provider_client=mock_provider(overrides))
        with pytest.raises(collector.SourceDiagnosticCollectorError, match=expected):
            collector.collect_compact_source_diagnostics(request)


def test_collector_rejects_raw_indicator_values_and_extra_fields():
    request = signed_request(provider_client=mock_provider({"unexpected": "raw_trace/path.json"}))
    with pytest.raises(collector.SourceDiagnosticCollectorError) as exc_info:
        collector.collect_compact_source_diagnostics(request)
    message = str(exc_info.value)
    assert "collector_provider_result_forbidden_field" in message or "collector_provider_result_extra_field" in message


def test_tests_do_not_read_profile_or_api_key(monkeypatch):
    opened = []

    def blocked_open(*args, **kwargs):
        opened.append(args[0])
        raise AssertionError("profile/key file should not be opened in tests")

    monkeypatch.setattr("builtins.open", blocked_open)
    request = signed_request(provider_client=mock_provider())
    records = collector.collect_compact_source_diagnostics(request)
    assert len(records) == 8
    assert opened == []
