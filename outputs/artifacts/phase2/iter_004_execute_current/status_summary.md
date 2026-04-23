# Phase-2 iter_004_execute Final Compact Report

Status: Evidence Only / protocol rejected.

| Slice | Accuracy | Correct Count | Delta |
| --- | ---: | ---: | ---: |
| multi_turn_miss_param target | 42.0 | 84 / 200 | +5.5 pp vs baseline |
| multi_turn_miss_param paired rerun | 40.5 | 81 / 200 | +4.0 pp vs baseline |
| simple_python holdout | 95.0 | 380 / 400 | 0.0 pp vs holdout baseline |

Selector decision: `candidate_invalid` with accept=`False`.

Primary protocol issue: `upstream_model_route mismatch: baseline='x-ai/grok-3', candidate='x-ai/grok-3-beta'`.

Conclusion: iter004 is useful evidence that the current policy line can improve the target slice without observed holdout regression, but it is not claimable as an accepted evolution candidate because the route mismatch violates the comparison protocol.
