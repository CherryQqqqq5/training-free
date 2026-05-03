#!/usr/bin/env python3
"""Check compact offline real-httpx prepared-request/wire-fingerprint diff artifacts."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from scripts.check_bfcl_proxy_real_httpx_wire_fingerprint_diff_gate import REQUIRED_COMPACT_FIELDS
DEFAULT_ARTIFACT=Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_real_httpx_wire_fingerprint_diff_compact.json")
STACK={"urllib_request","httpx_async_client","unknown"}
CAPTURE={"urllib_local_fake_upstream_wire","httpx_mock_transport_prepared_request","unknown"}
METHOD={"post","unknown"}; SUFFIX={"chat_completions_suffix","unknown"}; TARGET={"chat_completions_target","unknown"}
HEADER={"authorization_content_type_content_length_httpx_defaults","authorization_content_type_content_length_urllib_defaults","authorization_content_type_only","unknown"}
DEFAULTS={"httpx_defaults_superset_of_urllib","httpx_and_urllib_defaults_differ","not_observed","unknown"}
PRESENCE={"present_both","proxy_present_direct_absent","direct_present_proxy_absent","absent_both","not_observed","unknown"}
CONTENT_LEN={"both_nonzero","proxy_nonzero_direct_missing","missing","unknown"}; TRANSFER={"absent","present","not_observed","unknown"}
BODY={"both_compact_json_nonzero","proxy_only_nonzero","mismatch_or_not_observed","unknown"}
PROXY_ENV={"proxy_env_names_present","proxy_env_names_absent","not_observed","unknown"}; BOOL_LABEL={"true","false","not_observed","unknown"}
TIMEOUT={"proxy_config_timeout_direct_urllib_timeout","not_observed","unknown"}; TLS={"not_observed","default_context_uninspected","unknown"}
CAUSE={"real_httpx_default_header_context_diff","real_httpx_context_no_unique_cause","body_shape_or_serialization_diff","none_observed","unknown"}
STOP={"none","stopped_after_real_httpx_prepared_request_capture","packet_not_approved","output_artifact_exists","raw_or_secret_leak","missing_httpx_dependency","unknown"}
FAILED={"none_observed","packet_not_approved","output_artifact_exists","raw_or_secret_leak","missing_httpx_dependency","unknown"}
FORBIDDEN_KEY_RE=re.compile(r"(^|_)(raw_(requests?|responses?|bod(y|ies)|contents?|headers?|logs?|traces?|prompts?|cases?|tool_args?|provider_payloads?)|provider_payload|endpoint_values?|key_values?|api_key_values?|secret_values?|full_urls?|prompt_text|case_content|trace_content|log_content|tool_argument_value|gold_value|reference_value|expected_value|scorer_diffs?|candidate_outputs?|huawei_claim|performance_claim)(_|$)",re.I)
FORBIDDEN_VALUE_RE=re.compile(("s"+"k-"+r"[A-Za-z0-9_-]{16,}|https?://|bearer |endpoint value|key value|full url|secret|provider payload|raw request|raw response|raw body|raw content|raw header|raw log|raw trace|raw prompt|raw case|raw tool arg|scorer diff|candidate output|huawei|\+3pp|performance evidence"),re.I)
ALLOWED_FIELD_NAMES=set(REQUIRED_COMPACT_FIELDS)
def _load(path:Path)->Dict[str,Any]:
 data=json.loads(path.read_text(encoding="utf-8"))
 if not isinstance(data,dict): raise ValueError("%s must contain JSON object"%path)
 return data
def _walk(value:Any,path:Tuple[str,...]=())->List[Tuple[Tuple[str,...],Any]]:
 items=[(path,value)]
 if isinstance(value,dict):
  for k,v in value.items(): items.extend(_walk(v,path+(str(k),)))
 elif isinstance(value,list):
  for i,v in enumerate(value): items.extend(_walk(v,path+(str(i),)))
 return items
def _scan(data:Dict[str,Any])->List[str]:
 blockers=[]
 for path,value in _walk(data):
  key=path[-1] if path else ""; dotted=".".join(path)
  if key and key not in ALLOWED_FIELD_NAMES and FORBIDDEN_KEY_RE.search(key): blockers.append("forbidden_key:%s"%dotted)
  if isinstance(value,str) and FORBIDDEN_VALUE_RE.search(value):
   if key=="route_model" and value=="gpt-4.1": continue
   blockers.append("forbidden_value:%s"%dotted)
 return sorted(set(blockers))
def validate(data:Dict[str,Any])->List[str]:
 blockers=[]
 if data.get("artifact_kind")!="bfcl_proxy_real_httpx_wire_fingerprint_diff_compact": blockers.append("artifact_kind_invalid:%r"%data.get("artifact_kind"))
 if data.get("compact_schema_version")!="proxy_real_httpx_wire_fingerprint_diff_v1": blockers.append("compact_schema_version_invalid:%r"%data.get("compact_schema_version"))
 if data.get("measurement_kind")!="compact_offline_proxy_real_httpx_prepared_request_wire_fingerprint_diff": blockers.append("measurement_kind_invalid:%r"%data.get("measurement_kind"))
 if data.get("route_profile")!="novacode" or data.get("route_model")!="gpt-4.1": blockers.append("route_drift")
 for k in ("provider_call_executed","proxy_live_request_executed","profile_sourced_summary","bfcl_generate_executed","bfcl_evaluate_executed","scorer_executed","full_baseline_executed","candidate_runtime_activation_authorized","candidate_jsonl_authorized","candidate_pool_ready","source_collection_executed","source_diagnostics_executed","performance_evidence","sota_3pp_claim_ready","huawei_acceptance_ready","raw_outputs_committed"):
  if data.get(k) is not False: blockers.append("%s_not_false:%r"%(k,data.get(k)))
 records=data.get("records")
 if not isinstance(records,list) or len(records)!=1 or not isinstance(records[0],dict): blockers.append("records_invalid"); rec={}
 else: rec=records[0]
 if rec:
  missing=[f for f in REQUIRED_COMPACT_FIELDS if f not in rec]; extra=[f for f in rec if f not in REQUIRED_COMPACT_FIELDS]
  if missing: blockers.append("missing_required_fields:%r"%missing)
  if extra: blockers.append("extra_fields:%r"%extra)
  for k in ("preflight_command_executed","provider_call_started","profile_sourced","proxy_live_request_started","fake_transport_capture_used","real_httpx_prepared_request_capture_used","fake_httpx_module_used","raw_outputs_committed","raw_temp_outputs_removed","bfcl_generate_started","bfcl_evaluate_started","scorer_started","full_baseline_executed","candidate_specs_inert","source_collection_executed","source_diagnostics_executed","performance_evidence"):
   if rec.get(k) not in (True,False): blockers.append("%s_not_bool:%r"%(k,rec.get(k)))
  for k in ("provider_call_started","profile_sourced","proxy_live_request_started","fake_httpx_module_used","raw_outputs_committed","bfcl_generate_started","bfcl_evaluate_started","scorer_started","full_baseline_executed","source_collection_executed","source_diagnostics_executed","performance_evidence"):
   if rec.get(k) is not False: blockers.append("%s_not_false:%r"%(k,rec.get(k)))
  for k in ("fake_transport_capture_used","real_httpx_prepared_request_capture_used","raw_temp_outputs_removed","candidate_specs_inert"):
   if rec.get(k) is not True: blockers.append("%s_not_true:%r"%(k,rec.get(k)))
  validations={"direct_capture_layer_label":CAPTURE,"proxy_capture_layer_label":CAPTURE,"direct_client_stack_label":STACK,"proxy_client_stack_label":STACK,"method_label":METHOD,"url_suffix_label":SUFFIX,"wire_request_target_label":TARGET,"header_name_set_label":HEADER,"direct_header_name_set_label":HEADER,"default_header_shape_label":DEFAULTS,"wire_user_agent_label":PRESENCE,"wire_accept_label":PRESENCE,"wire_accept_encoding_label":PRESENCE,"wire_connection_label":PRESENCE,"content_length_shape_label":CONTENT_LEN,"transfer_encoding_label":TRANSFER,"body_bytes_shape_match_label":BODY,"proxy_env_presence_label":PROXY_ENV,"trust_env_label":BOOL_LABEL,"http2_config_label":BOOL_LABEL,"timeout_shape_label":TIMEOUT,"tls_context_source_label":TLS,"suspected_403_cause_label":CAUSE,"stop_gate_triggered":STOP,"preflight_failed_check_label":FAILED}
  for k,allowed in validations.items():
   if rec.get(k) not in allowed: blockers.append("%s_invalid:%r"%(k,rec.get(k)))
 blockers.extend(_scan(data)); return sorted(set(blockers))
def check(path:Path=DEFAULT_ARTIFACT)->Dict[str,Any]:
 data=_load(path); blockers=validate(data); rec=data.get("records",[{}])[0] if isinstance(data.get("records"),list) and data.get("records") else {}
 return {"report_scope":"bfcl_proxy_real_httpx_wire_fingerprint_diff_artifact_check","artifact_path":str(path),"bfcl_proxy_real_httpx_wire_fingerprint_diff_artifact_passed":not blockers,"real_httpx_prepared_request_capture_used":rec.get("real_httpx_prepared_request_capture_used") if isinstance(rec,dict) else None,"fake_httpx_module_used":rec.get("fake_httpx_module_used") if isinstance(rec,dict) else None,"header_name_set_label":rec.get("header_name_set_label") if isinstance(rec,dict) else None,"default_header_shape_label":rec.get("default_header_shape_label") if isinstance(rec,dict) else None,"body_bytes_shape_match_label":rec.get("body_bytes_shape_match_label") if isinstance(rec,dict) else None,"content_length_shape_label":rec.get("content_length_shape_label") if isinstance(rec,dict) else None,"trust_env_label":rec.get("trust_env_label") if isinstance(rec,dict) else None,"http2_config_label":rec.get("http2_config_label") if isinstance(rec,dict) else None,"suspected_403_cause_label":rec.get("suspected_403_cause_label") if isinstance(rec,dict) else None,"blockers":blockers}
def main(argv:Any=None)->int:
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--artifact",type=Path,default=DEFAULT_ARTIFACT); p.add_argument("--compact",action="store_true"); p.add_argument("--strict",action="store_true"); a=p.parse_args(argv)
 try: summary=check(a.artifact)
 except (OSError,ValueError,json.JSONDecodeError) as exc: summary={"report_scope":"bfcl_proxy_real_httpx_wire_fingerprint_diff_artifact_check","bfcl_proxy_real_httpx_wire_fingerprint_diff_artifact_passed":False,"blockers":["load_failed:%s"%exc]}
 print(json.dumps(summary,sort_keys=True) if a.compact else json.dumps(summary,indent=2,sort_keys=True)); return 1 if a.strict and not summary.get("bfcl_proxy_real_httpx_wire_fingerprint_diff_artifact_passed") else 0
if __name__=="__main__": raise SystemExit(main())
