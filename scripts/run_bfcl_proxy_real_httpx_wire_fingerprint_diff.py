#!/usr/bin/env python3
"""Run an offline real-httpx prepared-request/wire-fingerprint diff for proxy diagnostics."""
from __future__ import annotations
import argparse, asyncio, importlib.util, json, os, sys, threading, types, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from scripts.check_bfcl_proxy_real_httpx_wire_fingerprint_diff_artifact import check as check_artifact
from scripts.check_bfcl_proxy_real_httpx_wire_fingerprint_diff_gate import DEFAULT_PACKET, REQUIRED_COMPACT_FIELDS, check as check_packet
from scripts.run_bfcl_proxy_responses_tool_shape import _responses_payload
DEFAULT_OUTPUT=Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_real_httpx_wire_fingerprint_diff_compact.json")
PROXY_SOURCE=Path("src/grc/runtime/proxy.py")
PROXY_ENV_NAMES=("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","NO_PROXY")
HTTPX_DEFAULTS={"user-agent","accept","accept-encoding","connection"}
def _proxy_env_presence_label()->str:
 return "proxy_env_names_present" if any(os.environ.get(n) for n in PROXY_ENV_NAMES) else "proxy_env_names_absent"
def _base_record(command_executed:bool=False)->Dict[str,Any]:
 return {"preflight_command_executed":command_executed,"provider_call_started":False,"profile_sourced":False,"proxy_live_request_started":False,"fake_transport_capture_used":command_executed,"real_httpx_prepared_request_capture_used":command_executed,"fake_httpx_module_used":False,"direct_capture_layer_label":"unknown","proxy_capture_layer_label":"unknown","direct_client_stack_label":"unknown","proxy_client_stack_label":"unknown","method_label":"unknown","url_suffix_label":"unknown","wire_request_target_label":"unknown","header_name_set_label":"unknown","direct_header_name_set_label":"unknown","default_header_shape_label":"unknown","wire_user_agent_label":"unknown","wire_accept_label":"unknown","wire_accept_encoding_label":"unknown","wire_connection_label":"unknown","content_length_shape_label":"unknown","transfer_encoding_label":"unknown","body_bytes_shape_match_label":"unknown","proxy_env_presence_label":_proxy_env_presence_label(),"trust_env_label":"unknown","http2_config_label":"unknown","timeout_shape_label":"unknown","tls_context_source_label":"not_observed","raw_outputs_committed":False,"raw_temp_outputs_removed":command_executed,"suspected_403_cause_label":"unknown","bfcl_generate_started":False,"bfcl_evaluate_started":False,"scorer_started":False,"full_baseline_executed":False,"candidate_specs_inert":True,"source_collection_executed":False,"source_diagnostics_executed":False,"performance_evidence":False,"stop_gate_triggered":"none" if not command_executed else "stopped_after_real_httpx_prepared_request_capture","preflight_failed_check_label":"none_observed"}
def _suffix_label(target:Any)->str: return "chat_completions_suffix" if str(target).endswith("/chat/completions") else "unknown"
def _target_label(target:Any)->str: return "chat_completions_target" if str(target).endswith("/chat/completions") else "unknown"
def _header_label(names:set)->str:
 lower={str(n).lower() for n in names}
 if {"authorization","content-type","content-length"}.issubset(lower) and HTTPX_DEFAULTS.issubset(lower): return "authorization_content_type_content_length_httpx_defaults"
 if {"authorization","content-type","content-length"}.issubset(lower): return "authorization_content_type_content_length_urllib_defaults"
 if {"authorization","content-type"}.issubset(lower): return "authorization_content_type_only"
 return "unknown"
def _presence(proxy:set,direct:set,name:str)->str:
 p=name in proxy; d=name in direct
 if p and d: return "present_both"
 if p and not d: return "proxy_present_direct_absent"
 if d and not p: return "direct_present_proxy_absent"
 return "absent_both"
def _nonzero_bytes(value:Any)->bool: return isinstance(value,(bytes,bytearray)) and len(value)>0
class _DirectCaptureHandler(BaseHTTPRequestHandler):
 capture:Dict[str,Any]={}
 def do_POST(self)->None:
  length_text=self.headers.get("Content-Length")
  try: length=int(length_text or "0")
  except ValueError: length=0
  body=self.rfile.read(length) if length>0 else b""
  type(self).capture={"method":self.command,"path":self.path,"header_names":{str(k).lower() for k in self.headers.keys()},"body_nonzero":len(body)>0,"content_length_present":length_text is not None,"transfer_encoding_present":self.headers.get("Transfer-Encoding") is not None}
  self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(b"{}")
 def log_message(self,*_args:Any)->None: return
def _direct_local_wire_capture()->Dict[str,Any]:
 import scripts.run_bfcl_live_provider_preflight as direct_runner
 _DirectCaptureHandler.capture={}
 server=HTTPServer(("127.0.0.1",0),_DirectCaptureHandler)
 thread=threading.Thread(target=server.handle_request)
 thread.daemon=True; thread.start()
 try:
  direct_runner._default_post_json("http://127.0.0.1:%d/chat/completions"%server.server_port,"synthetic-direct-token",direct_runner._chat_tool_payload())
 finally:
  server.server_close(); thread.join(timeout=2)
 cap=_DirectCaptureHandler.capture
 names=cap.get("header_names",set())
 return {"capture_layer_label":"urllib_local_fake_upstream_wire","client_stack_label":"urllib_request","method_label":"post" if cap.get("method")=="POST" else "unknown","url_suffix_label":_suffix_label(cap.get("path","")),"wire_request_target_label":_target_label(cap.get("path","")),"header_names":names,"header_name_set_label":_header_label(names),"body_nonzero":bool(cap.get("body_nonzero")),"content_length_present":bool(cap.get("content_length_present")),"transfer_encoding_present":bool(cap.get("transfer_encoding_present")),"timeout":30}
class _FakeFastAPI:
 def __init__(self)->None: self.routes={}
 def get(self,path:str,*_args:Any,**_kwargs:Any)->Any:
  def dec(func:Any)->Any: self.routes[("GET",path)]=func; return func
  return dec
 def post(self,path:str,*_args:Any,**_kwargs:Any)->Any:
  def dec(func:Any)->Any: self.routes[("POST",path)]=func; return func
  return dec
class _FakeHTTPException(Exception):
 def __init__(self,status_code:Any=None,detail:Any=None)->None: super().__init__(detail); self.status_code=status_code; self.detail=detail
class _FakeJSONResponse:
 def __init__(self,content:Any=None,status_code:int=200)->None: self.content=content; self.status_code=status_code
class _FakeRequest:
 def __init__(self,payload:Dict[str,Any])->None: self._payload=payload
 async def json(self)->Dict[str,Any]: return self._payload
class _FakeRuleEngine:
 apply_request_called=False
 def __init__(self,*_args:Any,**_kwargs:Any)->None: pass
 def apply_request(self,request_json:Dict[str,Any])->Tuple[Dict[str,Any],List[Any]]: type(self).apply_request_called=True; return request_json,[]
 def apply_response(self,request_json:Dict[str,Any],response_json:Dict[str,Any],request_patches:Any=None)->Tuple[Dict[str,Any],List[Any],Any]:
  class Validation:
   def model_dump(self,mode:str="json")->Dict[str,Any]: return {"issues":[],"rule_hits":[],"request_patches":[]}
  return response_json,[],Validation()
class _FakeTraceStore:
 write_called=False
 def __init__(self,*_args:Any,**_kwargs:Any)->None: pass
 def write(self,_payload:Dict[str,Any])->None: type(self).write_called=True
def _install_non_httpx_stubs()->Dict[str,Any]:
 names=("fastapi","fastapi.responses","yaml","grc","grc.runtime","grc.runtime.engine","grc.runtime.trace_store","grc.utils","grc.utils.tool_schema")
 originals={n:sys.modules.get(n) for n in names}
 fake_fastapi=types.ModuleType("fastapi"); fake_fastapi.FastAPI=_FakeFastAPI; fake_fastapi.HTTPException=_FakeHTTPException; fake_fastapi.Request=_FakeRequest
 fake_responses=types.ModuleType("fastapi.responses"); fake_responses.JSONResponse=_FakeJSONResponse
 fake_yaml=types.ModuleType("yaml"); fake_yaml.safe_load=lambda _text:{"timeout_sec":120,"runtime_policy":{"bfcl_measurement_responses_to_chat_tool_choice_normalization":True},"upstream":{"active_profile":"novacode","base_url":"ENV_ONLY","api_key_env":"OPENAI_API_KEY","model":"gpt-4.1","profiles":{"novacode":{"base_url_env":"NOVACODE_BASE_URL","base_url":"ENV_ONLY_NOVACODE_BASE_URL","api_key_env":"NOVACODE_API_KEY","model":"gpt-4.1"}},"base_url_env":"NOVACODE_BASE_URL"}}
 fake_grc=types.ModuleType("grc"); fake_grc.__path__=[]
 fake_runtime=types.ModuleType("grc.runtime"); fake_runtime.__path__=[]
 fake_engine=types.ModuleType("grc.runtime.engine"); fake_engine.RuleEngine=_FakeRuleEngine
 fake_trace=types.ModuleType("grc.runtime.trace_store"); fake_trace.TraceStore=_FakeTraceStore
 fake_utils=types.ModuleType("grc.utils"); fake_utils.__path__=[]
 fake_tool_schema=types.ModuleType("grc.utils.tool_schema"); fake_tool_schema.tool_map_from_tools_payload=lambda _tools:{}
 sys.modules.update({"fastapi":fake_fastapi,"fastapi.responses":fake_responses,"yaml":fake_yaml,"grc":fake_grc,"grc.runtime":fake_runtime,"grc.runtime.engine":fake_engine,"grc.runtime.trace_store":fake_trace,"grc.utils":fake_utils,"grc.utils.tool_schema":fake_tool_schema})
 return originals
def _restore_modules(originals:Dict[str,Any])->None:
 for n,o in originals.items():
  if o is None: sys.modules.pop(n,None)
  else: sys.modules[n]=o
def _temporary_env(updates:Dict[str,str])->Dict[str,Any]:
 old={}
 for k,v in updates.items(): old[k]=os.environ.get(k); os.environ[k]=v
 return old
def _restore_env(old:Dict[str,Any])->None:
 for k,v in old.items():
  if v is None: os.environ.pop(k,None)
  else: os.environ[k]=v
def _proxy_real_httpx_capture()->Dict[str,Any]:
 try: import httpx
 except ImportError as exc: raise RuntimeError("missing_httpx_dependency") from exc
 _FakeRuleEngine.apply_request_called=False; _FakeTraceStore.write_called=False
 originals=_install_non_httpx_stubs(); old_env=_temporary_env({"GRC_UPSTREAM_PROFILE":"novacode","GRC_UPSTREAM_BASE_URL":"http://capture.invalid/v1","GRC_UPSTREAM_API_KEY_ENV":"CHUANGZHI_API_KEY","CHUANGZHI_API_KEY":"synthetic-proxy-token","GRC_PROXY_RESPONSES_TOOL_SHAPE_DIRECT_ALIGNMENT":"1"})
 capture:Dict[str,Any]={}
 try:
  spec=importlib.util.spec_from_file_location("proxy_real_httpx_capture_module",REPO_ROOT/PROXY_SOURCE)
  if spec is None or spec.loader is None: raise RuntimeError("proxy module spec unavailable")
  module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
  original_async_client=module.httpx.AsyncClient
  class CaptureAsyncClient:
   def __init__(self,*args:Any,**kwargs:Any)->None:
    capture["trust_env"]=kwargs.get("trust_env",True); capture["http2"]=kwargs.get("http2",False); capture["timeout"]=kwargs.get("timeout",args[0] if args else None)
    def handler(request:Any)->Any:
     body=getattr(request,"content",b"")
     capture["request"]={"method":request.method,"target_path":request.url.raw_path.decode("ascii","ignore") if hasattr(request.url,"raw_path") else request.url.path,"header_names":{str(k).lower() for k in request.headers.keys()},"body_nonzero":len(body)>0,"content_length_present":"content-length" in request.headers,"transfer_encoding_present":"transfer-encoding" in request.headers}
     return httpx.Response(200,json={"id":"synthetic","model":"gpt-4.1","choices":[{"message":{"tool_calls":[{"id":"synthetic_call","type":"function","function":{"name":"synthetic_proxy_responses_tool_shape_ping","arguments":"{}"}}]}}]})
    kwargs=dict(kwargs); kwargs["transport"]=httpx.MockTransport(handler)
    self._client=original_async_client(*args,**kwargs)
   async def __aenter__(self)->"CaptureAsyncClient": await self._client.__aenter__(); return self
   async def __aexit__(self,exc_type:Any,exc:Any,tb:Any)->Any: return await self._client.__aexit__(exc_type,exc,tb)
   async def post(self,*args:Any,**kwargs:Any)->Any: return await self._client.post(*args,**kwargs)
  module.httpx.AsyncClient=CaptureAsyncClient
  app=module.create_app("configs/runtime_bfcl_structured.yaml","rules/baseline_empty","/tmp/proxy-real-httpx-wire-fingerprint-fake-traces")
  handler=app.routes[("POST","/v1/responses")]
  asyncio.run(handler(_FakeRequest(_responses_payload())))
 finally:
  _restore_env(old_env); _restore_modules(originals)
 req=capture.get("request",{})
 names=req.get("header_names",set())
 return {"capture_layer_label":"httpx_mock_transport_prepared_request","client_stack_label":"httpx_async_client","method_label":"post" if req.get("method")=="POST" else "unknown","url_suffix_label":_suffix_label(req.get("target_path","")),"wire_request_target_label":_target_label(req.get("target_path","")),"header_names":names,"header_name_set_label":_header_label(names),"body_nonzero":bool(req.get("body_nonzero")),"content_length_present":bool(req.get("content_length_present")),"transfer_encoding_present":bool(req.get("transfer_encoding_present")),"trust_env":capture.get("trust_env"),"http2":capture.get("http2"),"timeout":capture.get("timeout")}
def build_diff_record()->Dict[str,Any]:
 direct=_direct_local_wire_capture(); proxy=_proxy_real_httpx_capture(); dh=direct.get("header_names",set()); ph=proxy.get("header_names",set())
 body="both_compact_json_nonzero" if direct.get("body_nonzero") and proxy.get("body_nonzero") else "mismatch_or_not_observed"
 content_length="both_nonzero" if direct.get("content_length_present") and proxy.get("content_length_present") else "missing"
 default_shape="httpx_defaults_superset_of_urllib" if HTTPX_DEFAULTS.issubset(ph) else "httpx_and_urllib_defaults_differ"
 cause="real_httpx_default_header_context_diff" if default_shape in {"httpx_defaults_superset_of_urllib","httpx_and_urllib_defaults_differ"} else "none_observed"
 record=_base_record(True); record.update({"direct_capture_layer_label":direct["capture_layer_label"],"proxy_capture_layer_label":proxy["capture_layer_label"],"direct_client_stack_label":direct["client_stack_label"],"proxy_client_stack_label":proxy["client_stack_label"],"method_label":"post" if direct.get("method_label")==proxy.get("method_label")=="post" else "unknown","url_suffix_label":"chat_completions_suffix" if direct.get("url_suffix_label")==proxy.get("url_suffix_label")=="chat_completions_suffix" else "unknown","wire_request_target_label":"chat_completions_target" if direct.get("wire_request_target_label")==proxy.get("wire_request_target_label")=="chat_completions_target" else "unknown","header_name_set_label":proxy["header_name_set_label"],"direct_header_name_set_label":direct["header_name_set_label"],"default_header_shape_label":default_shape,"wire_user_agent_label":_presence(ph,dh,"user-agent"),"wire_accept_label":_presence(ph,dh,"accept"),"wire_accept_encoding_label":_presence(ph,dh,"accept-encoding"),"wire_connection_label":_presence(ph,dh,"connection"),"content_length_shape_label":content_length,"transfer_encoding_label":"present" if proxy.get("transfer_encoding_present") or direct.get("transfer_encoding_present") else "absent","body_bytes_shape_match_label":body,"proxy_env_presence_label":_proxy_env_presence_label(),"trust_env_label":"true" if proxy.get("trust_env") is True else ("false" if proxy.get("trust_env") is False else "not_observed"),"http2_config_label":"true" if proxy.get("http2") is True else ("false" if proxy.get("http2") is False else "not_observed"),"timeout_shape_label":"proxy_config_timeout_direct_urllib_timeout" if proxy.get("timeout")==120 and direct.get("timeout")==30 else "not_observed","tls_context_source_label":"not_observed","suspected_403_cause_label":cause})
 return record
def _write_artifact(record:Dict[str,Any],output:Path)->None:
 payload={"artifact_kind":"bfcl_proxy_real_httpx_wire_fingerprint_diff_compact","compact_schema_version":"proxy_real_httpx_wire_fingerprint_diff_v1","measurement_kind":"compact_offline_proxy_real_httpx_prepared_request_wire_fingerprint_diff","route_profile":"novacode","route_model":"gpt-4.1","provider_call_executed":False,"proxy_live_request_executed":False,"profile_sourced_summary":False,"bfcl_generate_executed":False,"bfcl_evaluate_executed":False,"scorer_executed":False,"full_baseline_executed":False,"candidate_runtime_activation_authorized":False,"candidate_jsonl_authorized":False,"candidate_pool_ready":False,"source_collection_executed":False,"source_diagnostics_executed":False,"performance_evidence":False,"sota_3pp_claim_ready":False,"huawei_acceptance_ready":False,"raw_outputs_committed":False,"records":[{f:record.get(f) for f in REQUIRED_COMPACT_FIELDS}]}
 output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def _blocked(blockers:List[str])->Dict[str,Any]: return {"report_scope":"bfcl_proxy_real_httpx_wire_fingerprint_diff_execute",**_base_record(False),"output_artifact":None,"blockers":sorted(set(blockers))}
def build_plan(packet_path:Path=DEFAULT_PACKET,output_artifact:Path=DEFAULT_OUTPUT)->Dict[str,Any]:
 ps=check_packet(packet_path); return {"report_scope":"bfcl_proxy_real_httpx_wire_fingerprint_diff_plan","packet_path":str(packet_path),"output_artifact_planned":str(output_artifact),"approval_status":ps.get("approval_status"),"authorized":ps.get("authorized"),"planned_attempt_count":1,"compact_only":True,"synthetic_probe_only":True,"compact_fields":list(REQUIRED_COMPACT_FIELDS),**_base_record(False),"blockers":list(ps.get("blockers",[]))}
def execute_real_httpx_wire_fingerprint_diff(packet_path:Path=DEFAULT_PACKET,output_artifact:Path=DEFAULT_OUTPUT)->Dict[str,Any]:
 ps=check_packet(packet_path); blockers=list(ps.get("blockers",[]))
 if ps.get("approval_status")!="approved" or ps.get("authorized") is not True: blockers.append("real_httpx_wire_fingerprint_diff_packet_not_approved")
 if output_artifact.exists(): blockers.append("output_artifact_exists")
 if blockers: return _blocked(blockers)
 try: record=build_diff_record()
 except RuntimeError as exc:
  if str(exc)=="missing_httpx_dependency":
   rec=_base_record(False); rec.update({"stop_gate_triggered":"missing_httpx_dependency","preflight_failed_check_label":"missing_httpx_dependency"}); return {"report_scope":"bfcl_proxy_real_httpx_wire_fingerprint_diff_execute",**rec,"output_artifact":None,"blockers":["missing_httpx_dependency"]}
  raise
 _write_artifact(record,output_artifact); art=check_artifact(output_artifact)
 return {"report_scope":"bfcl_proxy_real_httpx_wire_fingerprint_diff_execute",**record,"output_artifact":str(output_artifact),"artifact_check_passed":art.get("bfcl_proxy_real_httpx_wire_fingerprint_diff_artifact_passed"),"blockers":list(art.get("blockers",[]))}
def main(argv:Any=None)->int:
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--packet",type=Path,default=DEFAULT_PACKET); p.add_argument("--output-artifact",type=Path,default=DEFAULT_OUTPUT); p.add_argument("--execute-real-httpx-wire-fingerprint-diff",action="store_true"); p.add_argument("--dry-run",action="store_true"); p.add_argument("--compact",action="store_true"); p.add_argument("--strict",action="store_true"); a=p.parse_args(argv)
 summary=execute_real_httpx_wire_fingerprint_diff(a.packet,a.output_artifact) if a.execute_real_httpx_wire_fingerprint_diff else build_plan(a.packet,a.output_artifact)
 print(json.dumps(summary,sort_keys=True) if a.compact else json.dumps(summary,indent=2,sort_keys=True))
 if a.strict and summary.get("blockers"): return 1
 if a.strict and a.execute_real_httpx_wire_fingerprint_diff and not summary.get("artifact_check_passed"): return 1
 return 0
if __name__=="__main__": raise SystemExit(main())
