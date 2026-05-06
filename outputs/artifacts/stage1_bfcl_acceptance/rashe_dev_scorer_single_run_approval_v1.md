# RASHE Dev Scorer Single-Run Approval v1

Status: pending review packet only. This artifact requests review of an exactly-one bounded dev scorer smoke boundary, but it does not authorize execution.

Current state: `approval_status=pending`, `authorized=false`, and `execution_started=false`. No provider, BFCL, scorer, baseline, candidate, paired comparison, cost/latency, or regression command is authorized by this packet.

Scope if separately approved later: one dev smoke attempt, max 12 aggregate-selected dev cases, six allowed categories with cap 2 each, same provider/model/protocol, compact outputs only, fresh output paths, and raw temporary cleanup. The smoke may inform a later request, but this packet is not final measurement evidence and carries no improvement or external acceptance claim.

Linked review inputs are the Stage 4 draft execution packet, dev manifest, and command manifest with sha256 hashes recorded in the JSON.
