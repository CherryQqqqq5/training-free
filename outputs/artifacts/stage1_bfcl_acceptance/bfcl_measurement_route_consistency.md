# BFCL Measurement Route Consistency

Status: active measurement-readiness route cleanup only. This is not BFCL scorer authorization, provider-call authorization, Phase B rerun authorization, candidate JSONL/pool authorization, performance evidence, +3pp evidence, or Huawei readiness.

- provider/profile: `Chuangzhi/Novacode` / `novacode`
- active upstream model route: `gpt-4.1`
- fallback_allowed: `false`
- gpt-4o fallback: `false`
- OpenRouter: `false` / disabled
- old signed model `gpt-5.2`: historical, superseded, inactive only
- candidate specs remain inert: `true`

Checked active configs:

- `configs/runtime.yaml`
- `configs/runtime_bfcl_structured.yaml`
- `configs/bfcl_eval_protocol.yaml`
- `configs/bfcl_v4_phase1.env`

## Endpoint And Feedback Hygiene

- endpoint/key values committed: `false`
- endpoint/key routing: env-only via signed env var names
- scorer feedback input: `disabled_inert_for_measurement_only`
