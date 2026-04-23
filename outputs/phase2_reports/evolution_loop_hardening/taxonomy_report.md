# Phase-2 Taxonomy Report

## Runs

| Run | Accuracy | Accuracy Source | Correct Count | Failure Count | Top-3 Families |
| --- | ---: | --- | ---: | ---: | --- |
| baseline | 36.5 | subsets.multi_turn_miss_param | 73.0 | 948 | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION), (POST_TOOL,CLARIFICATION_REQUEST), (POST_TOOL,EMPTY_TOOL_CALL) |
| primary_v4 | 40.0 | subsets.multi_turn_miss_param | 80.0 | 1533 | (POST_TOOL,EMPTY_TOOL_CALL), (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION), (POST_TOOL,TERMINATION_INADMISSIBLE) |

## Table A

| Run | Failure Label | Group | Count | Share |
| --- | --- | --- | ---: | ---: |
| baseline | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | decision_layer_target | 808 | 0.8523 |
| baseline | (POST_TOOL,CLARIFICATION_REQUEST) | boundary_misuse | 115 | 0.1213 |
| baseline | (POST_TOOL,EMPTY_TOOL_CALL) | compatibility_heavy | 25 | 0.0264 |
| primary_v4 | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | decision_layer_target | 339 | 0.2211 |
| primary_v4 | (POST_TOOL,CLARIFICATION_REQUEST) | allowed_boundary | 90 | 0.0587 |
| primary_v4 | (POST_TOOL,EMPTY_TOOL_CALL) | compatibility_heavy | 486 | 0.3170 |
| primary_v4 | (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | decision_layer_target | 279 | 0.1820 |
| primary_v4 | (POST_TOOL,TERMINATION_INADMISSIBLE) | decision_layer_target | 339 | 0.2211 |

## Merged Comparison

| failure_label | baseline_count | baseline_share | primary_v4_count | primary_v4_share |
| --- | --- | --- | --- | --- |
| (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | 808 | 0.8523206751054853 | 339 | 0.22113502935420742 |
| (POST_TOOL,CLARIFICATION_REQUEST) | 115 | 0.12130801687763713 | 90 | 0.05870841487279843 |
| (POST_TOOL,EMPTY_TOOL_CALL) | 25 | 0.026371308016877638 | 486 | 0.31702544031311153 |
| (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | 0 | 0.0 | 279 | 0.18199608610567514 |
| (POST_TOOL,TERMINATION_INADMISSIBLE) | 0 | 0.0 | 339 | 0.22113502935420742 |

## Delta Vs Baseline

| Run | Failure Label | Count Delta | Share Delta |
| --- | --- | ---: | ---: |
| primary_v4 | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | -469 | -0.6312 |
| primary_v4 | (POST_TOOL,CLARIFICATION_REQUEST) | -25 | -0.0626 |
| primary_v4 | (POST_TOOL,EMPTY_TOOL_CALL) | 461 | 0.2907 |
| primary_v4 | (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | 279 | 0.1820 |
| primary_v4 | (POST_TOOL,TERMINATION_INADMISSIBLE) | 339 | 0.2211 |

