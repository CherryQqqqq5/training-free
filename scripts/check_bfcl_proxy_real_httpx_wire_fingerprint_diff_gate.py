#!/usr/bin/env python3
"""Check the pending offline proxy real-httpx wire fingerprint diff gate packet."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any, Dict, List, Tuple
DEFAULT_PACKET=Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_real_httpx_wire_fingerprint_diff_gate_packet.json")
REQUIRED_COMPACT_FIELDS=["preflight_command_executed","provider_call_started","profile_sourced","proxy_live_request_started","fake_transport_capture_used","real_httpx_prepared_request_capture_used","fake_httpx_module_used","direct_capture_layer_label","proxy_capture_layer_label","direct_client_stack_label","proxy_client_stack_label","method_label","url_suffix_label","wire_request_target_label","header_name_set_label","direct_header_name_set_label","default_header_shape_label","wire_user_agent_label","wire_accept_label","wire_accept_encoding_label","wire_connection_label","content_length_shape_label","transfer_encoding_label","body_bytes_shape_match_label","proxy_env_presence_label","trust_env_label","http2_config_label","timeout_shape_label","tls_context_source_label","raw_outputs_committed","raw_temp_outputs_removed","suspected_403_cause_label","bfcl_generate_started","bfcl_evaluate_started","scorer_started","full_baseline_executed","candidate_specs_inert","source_collection_executed","source_diagnostics_executed","performance_evidence","stop_gate_triggered","preflight_failed_check_label"]
APPROVAL_TRUE_KEYS=("authorized",)
ALWAYS_FALSE_KEYS=("provider_request_authorized","proxy_live_request_authorized","profile_source_authorized","bfcl_generate_authorized","bfcl_evaluate_authorized","scorer_authorized","full_baseline_authorized","candidate_runtime_activation_authorized","candidate_jsonl_authorized","candidate_pool_ready","source_collection_authorized","source_diagnostics_authorized","performance_evidence","sota_3pp_claim_ready","huawei_acceptance_ready")
REQUIRED_TRUE_KEYS=("compact_only","one_attempt_only","synthetic_probe_only","fake_transport_capture_required","real_httpx_prepared_request_capture_required","fail_if_output_artifact_exists","raw_output_cleanup_required")
REQUIRED_STOP_GATES={"packet_not_approved","output_artifact_exists","raw_or_secret_leak","profile_source_attempted","provider_call_started","proxy_live_request_started","bfcl_generate_started","bfcl_evaluate_started","scorer_started","full_baseline_started","candidate_activation","source_collection","performance_evidence"}
FORBIDDEN_KEY_RE=re.compile(r"(^|_)(raw_(requests?|responses?|bod(y|ies)|contents?|headers?|logs?|traces?|prompts?|cases?|tool_args?|provider_payloads?)|provider_payload|endpoint_values?|key_values?|api_key_values?|secret_values?|full_urls?|prompt_text|case_content|trace_content|log_content|tool_argument_value|gold_value|reference_value|expected_value|scorer_diffs?|candidate_outputs?|huawei_claim|performance_claim)(_|$)",re.I)
FORBIDDEN_VALUE_RE=re.compile(("s"+"k-"+r"[A-Za-z0-9_-]{16,}|https?://|bearer |endpoint value|key value|full url|secret|provider payload|raw request|raw response|raw body|raw content|raw header|raw log|raw trace|raw prompt|raw case|raw tool arg|scorer diff|candidate output|huawei|\+3pp|performance evidence"),re.I)
ALLOWED_FIELD_NAMES=set(REQUIRED_COMPACT_FIELDS)|set(APPROVAL_TRUE_KEYS)|set(ALWAYS_FALSE_KEYS)|set(REQUIRED_TRUE_KEYS)
def load_packet(path:Path=DEFAULT_PACKET)->Dict[str,Any]:
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
  key=path[-1] if path else ""; parent=path[-2] if len(path)>=2 else ""; dotted=".".join(path)
  if key and key not in ALLOWED_FIELD_NAMES and FORBIDDEN_KEY_RE.search(key): blockers.append("forbidden_key:%s"%dotted)
  if isinstance(value,str) and FORBIDDEN_VALUE_RE.search(value):
   if key=="route_model" and value=="gpt-4.1": continue
   if parent in {"allowed_compact_fields","future_stop_gates"}: continue
   blockers.append("forbidden_value:%s"%dotted)
 return sorted(set(blockers))
def validate_packet(data:Dict[str,Any])->List[str]:
 blockers=[]
 if data.get("artifact_kind")!="bfcl_proxy_real_httpx_wire_fingerprint_diff_gate_packet": blockers.append("artifact_kind_invalid:%r"%data.get("artifact_kind"))
 status=data.get("approval_status")
 if status not in {"pending","approved"}: blockers.append("approval_status_invalid:%r"%status)
 expected=status=="approved"
 for k in APPROVAL_TRUE_KEYS:
  if data.get(k) is not expected: blockers.append("%s_not_%s:%r"%(k,str(expected).lower(),data.get(k)))
 for k in ALWAYS_FALSE_KEYS:
  if data.get(k) is not False: blockers.append("%s_not_false:%r"%(k,data.get(k)))
 for k in REQUIRED_TRUE_KEYS:
  if data.get(k) is not True: blockers.append("%s_not_true:%r"%(k,data.get(k)))
 if data.get("requested_scope")!="offline_no_provider_proxy_real_httpx_prepared_request_wire_fingerprint_diff_only": blockers.append("requested_scope_invalid:%r"%data.get("requested_scope"))
 if data.get("route_profile")!="novacode" or data.get("route_model")!="gpt-4.1": blockers.append("route_drift")
 fields=data.get("allowed_compact_fields")
 if not isinstance(fields,list): blockers.append("allowed_compact_fields_not_list"); fields=[]
 if fields!=REQUIRED_COMPACT_FIELDS:
  missing=[f for f in REQUIRED_COMPACT_FIELDS if f not in fields]; extra=[f for f in fields if f not in REQUIRED_COMPACT_FIELDS]
  if missing: blockers.append("missing_required_compact_fields:%r"%missing)
  if extra: blockers.append("extra_compact_fields:%r"%extra)
  if fields and not missing and not extra: blockers.append("allowed_compact_fields_order_invalid")
 for f in fields:
  if not isinstance(f,str): blockers.append("compact_field_not_string:%r"%f)
  elif f not in REQUIRED_COMPACT_FIELDS or FORBIDDEN_KEY_RE.search(f): blockers.append("forbidden_compact_field:%s"%f)
 stops=set(data.get("future_stop_gates",[])) if isinstance(data.get("future_stop_gates"),list) else set()
 if not stops.issuperset(REQUIRED_STOP_GATES): blockers.append("future_stop_gates_missing")
 blockers.extend(_scan(data)); return sorted(set(blockers))
def check(path:Path=DEFAULT_PACKET)->Dict[str,Any]:
 packet=load_packet(path); blockers=validate_packet(packet)
 return {"report_scope":"bfcl_proxy_real_httpx_wire_fingerprint_diff_gate_check","packet_path":str(path),"bfcl_proxy_real_httpx_wire_fingerprint_diff_gate_passed":not blockers,"approval_status":packet.get("approval_status"),"authorized":packet.get("authorized"),"provider_request_authorized":packet.get("provider_request_authorized"),"proxy_live_request_authorized":packet.get("proxy_live_request_authorized"),"profile_source_authorized":packet.get("profile_source_authorized"),"route_profile":packet.get("route_profile"),"route_model":packet.get("route_model"),"compact_field_count":len(packet.get("allowed_compact_fields",[])) if isinstance(packet.get("allowed_compact_fields"),list) else 0,"bfcl_generate_authorized":packet.get("bfcl_generate_authorized"),"bfcl_evaluate_authorized":packet.get("bfcl_evaluate_authorized"),"scorer_authorized":packet.get("scorer_authorized"),"full_baseline_authorized":packet.get("full_baseline_authorized"),"performance_evidence":packet.get("performance_evidence"),"huawei_acceptance_ready":packet.get("huawei_acceptance_ready"),"blockers":blockers}
def main(argv:Any=None)->int:
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--packet",type=Path,default=DEFAULT_PACKET); p.add_argument("--compact",action="store_true"); p.add_argument("--strict",action="store_true"); a=p.parse_args(argv)
 try: summary=check(a.packet)
 except (OSError,ValueError,json.JSONDecodeError) as exc: summary={"report_scope":"bfcl_proxy_real_httpx_wire_fingerprint_diff_gate_check","bfcl_proxy_real_httpx_wire_fingerprint_diff_gate_passed":False,"blockers":["load_failed:%s"%exc]}
 print(json.dumps(summary,sort_keys=True) if a.compact else json.dumps(summary,indent=2,sort_keys=True)); return 1 if a.strict and not summary.get("bfcl_proxy_real_httpx_wire_fingerprint_diff_gate_passed") else 0
if __name__=="__main__": raise SystemExit(main())
