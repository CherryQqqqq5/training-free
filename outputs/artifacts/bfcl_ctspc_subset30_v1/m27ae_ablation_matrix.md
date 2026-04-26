# M2.7ae Ablation Matrix Manifest

Offline plan only; no scorer commands are emitted.

- `candidate_none`: Measure baseline-like behavior without CTSPC intervention.
- `compatibility_repairs_only`: Isolate repair stack contribution without action guidance.
- `action_guidance_only`: Isolate action policy without repair stack side effects.
- `repair_without_action`: Check whether repair/no-tool coercion causes regressions.
- `action_without_repair`: Check whether local action guidance alone damages trajectory.
