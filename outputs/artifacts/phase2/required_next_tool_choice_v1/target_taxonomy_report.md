# Phase-2 Taxonomy Report

## Runs

| Run | Accuracy | Accuracy Source | Correct Count | Failure Count | Top-3 Families |
| --- | ---: | --- | ---: | ---: | --- |
| baseline | 37.0 | subsets.multi_turn_miss_param | 74.0 | 1217 | (POST_TOOL,EMPTY_TOOL_CALL), (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION), (POST_TOOL,POST_TOOL_PROSE_SUMMARY) |
| primary_v4 | 39.5 | subsets.multi_turn_miss_param | 79.0 | 1566 | (POST_TOOL,EMPTY_TOOL_CALL), (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION), (POST_TOOL,TERMINATION_INADMISSIBLE) |
| required | 38.0 | subsets.multi_turn_miss_param | 76.0 | 1534 | (POST_TOOL,EMPTY_TOOL_CALL), (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION), (POST_TOOL,TERMINATION_INADMISSIBLE) |

## Table A

| Run | Failure Label | Group | Count | Share |
| --- | --- | --- | ---: | ---: |
| baseline | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | decision_layer_target | 372 | 0.3057 |
| baseline | (POST_TOOL,CLARIFICATION_REQUEST) | boundary_misuse | 92 | 0.0756 |
| baseline | (POST_TOOL,EMPTY_TOOL_CALL) | compatibility_heavy | 463 | 0.3804 |
| baseline | (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | decision_layer_target | 288 | 0.2366 |
| baseline | (POST_TOOL,UNSUPPORTED_REQUEST) | allowed_boundary | 2 | 0.0016 |
| primary_v4 | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | decision_layer_target | 353 | 0.2254 |
| primary_v4 | (POST_TOOL,CLARIFICATION_REQUEST) | allowed_boundary | 88 | 0.0562 |
| primary_v4 | (POST_TOOL,EMPTY_TOOL_CALL) | compatibility_heavy | 483 | 0.3084 |
| primary_v4 | (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | decision_layer_target | 287 | 0.1833 |
| primary_v4 | (POST_TOOL,TERMINATION_INADMISSIBLE) | decision_layer_target | 353 | 0.2254 |
| primary_v4 | (POST_TOOL,UNSUPPORTED_REQUEST) | allowed_boundary | 2 | 0.0013 |
| required | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | decision_layer_target | 344 | 0.2243 |
| required | (POST_TOOL,CLARIFICATION_REQUEST) | boundary_misuse | 90 | 0.0587 |
| required | (POST_TOOL,EMPTY_TOOL_CALL) | compatibility_heavy | 484 | 0.3155 |
| required | (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | decision_layer_target | 272 | 0.1773 |
| required | (POST_TOOL,TERMINATION_INADMISSIBLE) | decision_layer_target | 344 | 0.2243 |

## Merged Comparison

| failure_label | baseline_count | baseline_share | primary_v4_count | primary_v4_share | required_count | required_share |
| --- | --- | --- | --- | --- | --- | --- |
| (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | 372 | 0.3056696795398521 | 353 | 0.22541507024265645 | 344 | 0.2242503259452412 |
| (POST_TOOL,CLARIFICATION_REQUEST) | 92 | 0.07559572719802794 | 88 | 0.0561941251596424 | 90 | 0.05867014341590613 |
| (POST_TOOL,EMPTY_TOOL_CALL) | 463 | 0.38044371405094496 | 483 | 0.30842911877394635 | 484 | 0.3155149934810952 |
| (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | 288 | 0.23664749383730485 | 287 | 0.18326947637292465 | 272 | 0.1773142112125163 |
| (POST_TOOL,TERMINATION_INADMISSIBLE) | 0 | 0.0 | 353 | 0.22541507024265645 | 344 | 0.2242503259452412 |
| (POST_TOOL,UNSUPPORTED_REQUEST) | 2 | 0.0016433853738701725 | 2 | 0.001277139208173691 | 0 | 0.0 |

## Delta Vs Baseline

| Run | Failure Label | Count Delta | Share Delta |
| --- | --- | ---: | ---: |
| primary_v4 | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | -19 | -0.0803 |
| required | (POST_TOOL,ACTIONABLE_NO_TOOL_DECISION) | -28 | -0.0814 |
| primary_v4 | (POST_TOOL,CLARIFICATION_REQUEST) | -4 | -0.0194 |
| required | (POST_TOOL,CLARIFICATION_REQUEST) | -2 | -0.0169 |
| primary_v4 | (POST_TOOL,EMPTY_TOOL_CALL) | 20 | -0.0720 |
| required | (POST_TOOL,EMPTY_TOOL_CALL) | 21 | -0.0649 |
| primary_v4 | (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | -1 | -0.0534 |
| required | (POST_TOOL,POST_TOOL_PROSE_SUMMARY) | -16 | -0.0593 |
| primary_v4 | (POST_TOOL,TERMINATION_INADMISSIBLE) | 353 | 0.2254 |
| required | (POST_TOOL,TERMINATION_INADMISSIBLE) | 344 | 0.2243 |
| primary_v4 | (POST_TOOL,UNSUPPORTED_REQUEST) | 0 | -0.0004 |
| required | (POST_TOOL,UNSUPPORTED_REQUEST) | -2 | -0.0016 |

