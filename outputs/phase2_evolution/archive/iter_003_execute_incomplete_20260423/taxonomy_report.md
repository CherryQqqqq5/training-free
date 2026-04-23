# Phase-2 Taxonomy Report

## Runs

| Run | Accuracy | Accuracy Source | Correct Count | Failure Count | Top-3 Families |
| --- | ---: | --- | ---: | ---: | --- |
| baseline | - | - | - | 1408 | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION), (POST_TOOL,TERMINATION_INADMISSIBLE), (POST_TOOL,CLARIFICATION_REQUEST) |
| primary_v4 | 40.0 | subsets.multi_turn_miss_param | 80.0 | 1533 | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION), (POST_TOOL,TERMINATION_INADMISSIBLE), (POST_TOOL,POST_TOOL_PROSE_SUMMARY) |

## Table A

| Run | Failure Label | Group | Count | Share |
| --- | --- | --- | ---: | ---: |
| baseline | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | decision_layer_target | 666 | 0.4730 |
| baseline | (POST_TOOL,CLARIFICATION_REQUEST) | boundary_misuse | 76 | 0.0540 |
| baseline | (POST_TOOL,TERMINATION_INADMISSIBLE) | decision_layer_target | 666 | 0.4730 |
| primary_v4 | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | decision_layer_target | 825 | 0.5382 |
| primary_v4 | (POST_TOOL,CLARIFICATION_REQUEST) | allowed_boundary | 90 | 0.0587 |
| primary_v4 | (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | decision_layer_target | 279 | 0.1820 |
| primary_v4 | (POST_TOOL,TERMINATION_INADMISSIBLE) | decision_layer_target | 339 | 0.2211 |

## Merged Comparison

| failure_label | baseline_count | baseline_share | primary_v4_count | primary_v4_share |
| --- | --- | --- | --- | --- |
| (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | 666 | 0.47301136363636365 | 825 | 0.538160469667319 |
| (POST_TOOL,CLARIFICATION_REQUEST) | 76 | 0.05397727272727273 | 90 | 0.05870841487279843 |
| (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | 0 | 0.0 | 279 | 0.18199608610567514 |
| (POST_TOOL,TERMINATION_INADMISSIBLE) | 666 | 0.47301136363636365 | 339 | 0.22113502935420742 |

## Delta Vs Baseline

| Run | Failure Label | Count Delta | Share Delta |
| --- | --- | ---: | ---: |
| primary_v4 | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | 159 | 0.0651 |
| primary_v4 | (POST_TOOL,CLARIFICATION_REQUEST) | 14 | 0.0047 |
| primary_v4 | (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | 279 | 0.1820 |
| primary_v4 | (POST_TOOL,TERMINATION_INADMISSIBLE) | -327 | -0.2519 |

