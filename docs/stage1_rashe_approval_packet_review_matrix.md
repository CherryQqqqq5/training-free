# Stage-1 RASHE Approval Packet Review Matrix

This is the active post-runtime-approval review matrix. Runtime behavior lane L1 is approved only for synthetic/default-disabled wiring; source collection, candidate/proposer execution, scorer use, performance evidence, SOTA/+3pp claims, and Huawei acceptance readiness remain pending and unauthorized.

Current gate: `scripts/check_rashe_approval_packet_review_matrix_after_runtime_behavior.py --compact --strict`. Legacy pre-runtime gate: `scripts/check_rashe_approval_packet_review_matrix.py --compact --strict`; it intentionally rejects approved runtime packets and should not be used as the current post-runtime gate.

Dependency order: `offline scaffold ready -> L1 runtime behavior approved synthetic/default-disabled only -> source/candidate approvals -> scorer/dev/holdout/full -> performance/+3pp/Huawei acceptance`

| Order | Lane | Owner | Status | Authorized | Packet / Scope | Downstream | Forbidden Claims |
|---:|---|---|---|---|---|---|---|
| 1 | `runtime_behavior_approval` | RASHE runtime engineering owner + acceptance reviewer | `approved` | `true` | `synthetic_default_disabled_only`; `outputs/artifacts/stage1_bfcl_acceptance/rashe_runtime_behavior_approval_packet.json` | source_real_trace_approval, candidate_proposer_execution_approval | runtime enabled by default, provider authorized, source collection authorized, candidate pool ready, scorer authorized, performance evidence, Huawei acceptance ready |
| 2 | `source_real_trace_approval` | source collection owner + no-leakage reviewer | `pending` | `false` | `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_real_trace_approval_packet.json` | candidate_proposer_execution_approval, scorer_dev_holdout_full_approval | real trace approved, candidate pool ready, scorer authorized, performance evidence, Huawei acceptance ready |
| 3 | `candidate_proposer_execution_approval` | candidate engineering owner + no-leakage reviewer | `pending` | `false` | `outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_proposer_execution_approval_packet.json` | scorer_dev_holdout_full_approval | candidate pool ready, scorer authorized, performance evidence, SOTA +3pp ready, Huawei acceptance ready |
| 4 | `scorer_dev_holdout_full_approval` | scorer owner + acceptance reviewer | `pending` | `false` | `outputs/artifacts/stage1_bfcl_acceptance/rashe_scorer_dev_holdout_full_approval_packet.json` | performance_3pp_huawei_acceptance_approval | scorer authorized, paired comparison passed, performance evidence, SOTA +3pp ready, Huawei acceptance ready |
| 5 | `performance_3pp_huawei_acceptance_approval` | Huawei acceptance owner + project lead | `pending` | `false` | `outputs/artifacts/stage1_bfcl_acceptance/rashe_performance_3pp_huawei_acceptance_approval_packet.json` | terminal_no_downstream_lane | performance evidence, SOTA +3pp ready, Huawei acceptance ready, BFCL performance ready |

## 1. runtime_behavior_approval

- owner_role: RASHE runtime engineering owner + acceptance reviewer
- current_status: `approved`
- approval_packet_path: `outputs/artifacts/stage1_bfcl_acceptance/rashe_runtime_behavior_approval_packet.json`
- authorized: `true`
- runtime_behavior_scope: `synthetic_default_disabled_only`

### Prerequisites
- rashe_offline_scaffold_ready=true
- scope_change_route=RASHE approved
- runtime skeleton remains default disabled
- rollback plan and cost/latency/regression gates reviewed

### Allowed Only After Approval
- default-disabled runtime behavior wiring
- bounded router invocation in reviewed path
- compact verifier counters

### Allowed Commands
- offline checker commands only until packet is approved
- post-approval runtime skeleton tests with config enabled=false unless separate enable approval exists

### Forbidden Until Approved
- prompt injection
- retry
- tool path mutation
- RuleEngine/proxy active path import
- provider/source/scorer/candidate execution

### Stop Gates
- default_enabled=true without separate enable approval
- provider/scorer/source side effect detected
- ambiguous router decision does not fail closed

### Allowed Claims
- runtime behavior L1 approved for synthetic/default-disabled checks
- downstream lanes remain pending/fail-closed

### Forbidden Claims
- runtime enabled by default
- provider authorized
- source collection authorized
- candidate pool ready
- scorer authorized
- performance evidence
- Huawei acceptance ready

## 2. source_real_trace_approval

- owner_role: source collection owner + no-leakage reviewer
- current_status: `pending`
- approval_packet_path: `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_real_trace_approval_packet.json`
- authorized: `false`

### Prerequisites
- rashe_offline_scaffold_ready=true
- runtime/source approval signed separately
- raw payload handling and sanitization policy reviewed
- artifact boundary rules reviewed

### Allowed Only After Approval
- bounded source collection for approved categories only
- raw payload capture under approved raw root only
- compact sanitized counters and hashes

### Allowed Commands
- no source/provider commands while current_status=pending
- post-approval bounded source command from signed packet only

### Forbidden Until Approved
- source collection
- raw trace capture
- raw payload committed to tracked artifacts
- candidate generation
- scorer execution
- performance claim

### Stop Gates
- forbidden field violation
- raw path leak
- artifact boundary failure
- provider/model drift

### Allowed Claims
- source approval pending
- no source execution authorized

### Forbidden Claims
- real trace approved
- candidate pool ready
- scorer authorized
- performance evidence
- Huawei acceptance ready

## 3. candidate_proposer_execution_approval

- owner_role: candidate engineering owner + no-leakage reviewer
- current_status: `pending`
- approval_packet_path: `outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_proposer_execution_approval_packet.json`
- authorized: `false`

### Prerequisites
- runtime_behavior_approval reviewed if runtime behavior is needed
- source_real_trace_approval reviewed if real traces are needed
- approved sanitized source scope exists
- proposal schema gate passed
- no-leakage gate reviewed

### Allowed Only After Approval
- bounded proposer execution over approved sanitized inputs
- candidate metadata draft generation after approval
- candidate pool checker execution

### Allowed Commands
- offline proposer schema checker only while current_status=pending
- post-approval proposer execution command from signed packet only

### Forbidden Until Approved
- candidate/proposer execution
- candidate JSONL
- dev/holdout manifest creation
- gold/expected/scorer diff use
- holdout/full-suite feedback use

### Stop Gates
- any leakage counter nonzero
- candidate checker failure
- holdout/full-suite feedback in candidate path
- ambiguous proposal source

### Allowed Claims
- candidate/proposer approval pending
- candidate generation unauthorized

### Forbidden Claims
- candidate pool ready
- scorer authorized
- performance evidence
- SOTA +3pp ready
- Huawei acceptance ready

## 4. scorer_dev_holdout_full_approval

- owner_role: scorer owner + acceptance reviewer
- current_status: `pending`
- approval_packet_path: `outputs/artifacts/stage1_bfcl_acceptance/rashe_scorer_dev_holdout_full_approval_packet.json`
- authorized: `false`

### Prerequisites
- candidate_proposer_execution_approval approved and candidate pool readiness established by its gate
- source_real_trace_approval approved if source-derived inputs are used
- same provider/model/protocol comparator frozen
- dev/holdout disjoint manifests signed
- paired baseline/candidate command templates reviewed

### Allowed Only After Approval
- baseline dev scorer command
- candidate dev scorer command
- holdout scorer command after dev pass
- paired baseline/candidate comparison artifacts

### Allowed Commands
- no BFCL scorer command while current_status=pending
- post-approval exact baseline/candidate scorer commands from signed packet only

### Forbidden Until Approved
- BFCL scorer
- candidate run
- paired comparison
- dev/holdout/full-suite scoring
- provider/model/protocol drift

### Stop Gates
- same provider/model/protocol mismatch
- dev/holdout overlap
- paired comparison regression
- run schema checker failure

### Allowed Claims
- scorer approval pending
- performance evidence unavailable

### Forbidden Claims
- scorer authorized
- paired comparison passed
- performance evidence
- SOTA +3pp ready
- Huawei acceptance ready

## 5. performance_3pp_huawei_acceptance_approval

- owner_role: Huawei acceptance owner + project lead
- current_status: `pending`
- approval_packet_path: `outputs/artifacts/stage1_bfcl_acceptance/rashe_performance_3pp_huawei_acceptance_approval_packet.json`
- authorized: `false`

### Prerequisites
- scorer_dev_holdout_full_approval approved
- paired BFCL baseline/candidate comparison passed
- +3pp delta evidence present
- no regression gate passed
- cost/latency gates passed
- artifact boundary and run schema gates passed

### Allowed Only After Approval
- formal performance evidence publication
- SOTA/+3pp claim after signed acceptance review
- Huawei readiness artifact after owner approval

### Allowed Commands
- no performance claim command while current_status=pending
- post-approval publication/check commands from signed acceptance packet only

### Forbidden Until Approved
- performance evidence
- SOTA/+3pp claim
- Huawei acceptance readiness claim
- claim from unpaired or partial score
- claim before no-leakage and regression gates

### Stop Gates
- +3pp threshold miss
- paired regression
- cost/latency bound failure
- artifact boundary failure
- Huawei owner rejection

### Allowed Claims
- performance/Huawei approval pending
- no BFCL +3pp evidence yet

### Forbidden Claims
- performance evidence
- SOTA +3pp ready
- Huawei acceptance ready
- BFCL performance ready
