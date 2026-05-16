# Stage 1 ABHE-v0 BFCL Dev Smoke Approval Request

This request prepares the first bounded paired BFCL dev smoke for review. It is not an approval packet.

Scope: bounded dev smoke only for `state_tracking_v0` and `hallucination_abstain_v0`.

The future execution must use the same fresh case list hash, provider, model, protocol, and runtime configuration for baseline and candidate arms. The artifact boundary is compact only.

Stop-loss conditions:
- raw leakage
- provider/model/protocol mismatch
- case list hash mismatch
- unapproved candidate rule
- fresh slice not materialized
- cost or latency cap exceeded
- regression cap exceeded
- compact scorer artifact schema failure

Boundary:
- This request does not authorize provider calls.
- This request does not authorize BFCL generate or evaluate.
- This request does not authorize scorer execution.
- This request does not authorize holdout or full suite.
- This request does not authorize performance, +3pp, SOTA, or Huawei acceptance claims.
