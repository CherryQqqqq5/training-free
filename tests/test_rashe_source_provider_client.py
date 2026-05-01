import builtins

import pytest

from scripts import rashe_source_provider_client as provider_client


def signed_request(**overrides):
    request = {
        "provider_profile": "Chuangzhi/Novacode",
        "model": "gpt-5.2",
        "categories": list(provider_client.APPROVED_CATEGORIES),
        "case_count_per_category": 20,
        "max_total_cases": 160,
        "output_root": "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/",
        "schema_path": "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json",
        "forbidden_fields": list(provider_client.FORBIDDEN_FIELD_NAMES),
        "failure_buckets": list(provider_client.FAILURE_BUCKETS),
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "raw_payload_capture_authorized": False,
        "raw_trace_capture_authorized": False,
        "compact_sanitized_only": True,
    }
    request.update(overrides)
    return request


def category_request(category="agentic_web_search", **overrides):
    request = {
        "category": category,
        "case_count": 20,
        "provider_profile": "Chuangzhi/Novacode",
        "model": "gpt-5.2",
        "compact_sanitized_only": True,
        "raw_payload_capture_authorized": False,
        "raw_trace_capture_authorized": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }
    request.update(overrides)
    return request


def compact_cases(category):
    return [
        {
            "category": category,
            "ordinal": index,
            "prompt_family": "synthetic-boundary",
            "compact_hash": f"hash-{category}-{index}",
        }
        for index in range(20)
    ]


def test_factory_import_and_construction_do_not_read_key(monkeypatch):
    opened = []

    def blocked_open(*args, **kwargs):
        opened.append(args[0])
        raise AssertionError("key/profile file must not be opened")

    monkeypatch.setenv("CHUANGZHI_API_KEY", "mock-secret-must-not-leak")
    monkeypatch.setattr(builtins, "open", blocked_open)

    client = provider_client.build_chuangzhi_novacode_source_provider_client(signed_request())

    assert callable(client)
    assert opened == []


def test_client_without_source_case_provider_fails_precisely():
    client = provider_client.build_chuangzhi_novacode_source_provider_client(signed_request())

    with pytest.raises(provider_client.SourceProviderClientError, match="source_case_provider_missing"):
        client(category_request())


def test_client_without_provider_transport_fails_precisely(monkeypatch):
    monkeypatch.delenv("CHUANGZHI_API_KEY", raising=False)
    monkeypatch.delenv("NOVACODE_API_KEY", raising=False)
    request = signed_request(source_case_provider=lambda request: compact_cases(request["category"]))
    client = provider_client.build_chuangzhi_novacode_source_provider_client(request)

    with pytest.raises(provider_client.SourceProviderClientError, match="provider_key_missing"):
        client(category_request())


def test_default_transport_requires_provider_transport_approval(monkeypatch):
    request = signed_request(source_case_provider=lambda request: compact_cases(request["category"]))
    client = provider_client.build_chuangzhi_novacode_source_provider_client(request)
    monkeypatch.setattr(provider_client, "_provider_transport_approved", lambda: (_ for _ in ()).throw(provider_client.SourceProviderClientError("provider_transport_not_approved")))

    with pytest.raises(provider_client.SourceProviderClientError, match="provider_transport_not_approved"):
        client(category_request())


def test_client_with_mock_source_and_transport_returns_compact_counter_only(monkeypatch):
    monkeypatch.setenv("CHUANGZHI_API_KEY", "mock-secret-must-not-leak")
    source_calls = []
    transport_calls = []

    def source_case_provider(request):
        source_calls.append(request)
        assert "api_key" not in str(request).lower()
        return compact_cases(request["category"])

    def provider_transport(request):
        transport_calls.append(request)
        assert "mock-secret-must-not-leak" not in str(request)
        return {"failure_bucket": "answered_without_tool"}

    client = provider_client.build_chuangzhi_novacode_source_provider_client(
        signed_request(source_case_provider=source_case_provider, provider_transport=provider_transport)
    )
    record = client(category_request())

    assert source_calls and len(transport_calls) == 20
    assert set(record) == {
        "category",
        "case_count",
        "provider_call_count",
        "failure_bucket_counts",
        "raw_payload_tracked_count",
        "forbidden_field_violation_count",
        "candidate_generation_authorized",
        "scorer_authorized",
        "performance_evidence",
    }
    assert record["category"] == "agentic_web_search"
    assert record["case_count"] == 20
    assert record["provider_call_count"] == 20
    assert record["failure_bucket_counts"]["answered_without_tool"] == 20
    assert record["raw_payload_tracked_count"] == 0
    assert record["forbidden_field_violation_count"] == 0
    assert record["candidate_generation_authorized"] is False
    assert record["scorer_authorized"] is False
    assert record["performance_evidence"] is False
    assert "mock-secret-must-not-leak" not in str(record)


def test_factory_rejects_unsigned_request_scope():
    invalid = signed_request(provider_profile="Unsigned")
    with pytest.raises(provider_client.SourceProviderClientError) as exc_info:
        provider_client.build_chuangzhi_novacode_source_provider_client(invalid)
    assert "provider_client_profile_not_signed" in str(exc_info.value)

    invalid = signed_request(categories=["agentic_web_search"])
    with pytest.raises(provider_client.SourceProviderClientError) as exc_info:
        provider_client.build_chuangzhi_novacode_source_provider_client(invalid)
    assert "provider_client_categories_not_signed" in str(exc_info.value)

    invalid = signed_request(case_count_per_category=25, max_total_cases=200)
    with pytest.raises(provider_client.SourceProviderClientError) as exc_info:
        provider_client.build_chuangzhi_novacode_source_provider_client(invalid)
    message = str(exc_info.value)
    assert "provider_client_case_count_per_category_not_signed" in message
    assert "provider_client_max_total_cases_not_signed" in message


def test_client_rejects_unsigned_category_request():
    client = provider_client.build_chuangzhi_novacode_source_provider_client(signed_request())

    with pytest.raises(provider_client.SourceProviderClientError, match="source_category_not_signed"):
        client(category_request(category="not_signed"))

    with pytest.raises(provider_client.SourceProviderClientError, match="source_category_case_count_not_signed"):
        client(category_request(case_count=25))


def test_client_rejects_forbidden_source_case_output():
    def source_case_provider(request):
        cases = compact_cases(request["category"])
        cases[0]["case_id"] = "raw-case-id"
        return cases

    request = signed_request(source_case_provider=source_case_provider, provider_transport=lambda request: None)
    client = provider_client.build_chuangzhi_novacode_source_provider_client(request)

    with pytest.raises(provider_client.SourceProviderClientError) as exc_info:
        client(category_request())
    assert "source_case_forbidden_field" in str(exc_info.value)
    assert "case_id" in str(exc_info.value)


def test_client_rejects_forbidden_transport_output_and_downstream_flags():
    def source_case_provider(request):
        return compact_cases(request["category"])

    for result, expected in [
        ({"raw_payload": "raw-provider-payload"}, "provider_transport_result_forbidden_field"),
        ({"candidate_generation_authorized": True}, "provider_transport_result_extra_field"),
        ({"scorer_authorized": True}, "provider_transport_result_extra_field"),
        ({"performance_evidence": True}, "provider_transport_result_extra_field"),
    ]:
        request = signed_request(source_case_provider=source_case_provider, provider_transport=lambda _: result)
        client = provider_client.build_chuangzhi_novacode_source_provider_client(request)
        with pytest.raises(provider_client.SourceProviderClientError) as exc_info:
            client(category_request())
        assert expected in str(exc_info.value)
