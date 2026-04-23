from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def serve(
    config: str = typer.Option(..., "--config"),
    rules_dir: str = typer.Option(..., "--rules-dir"),
    trace_dir: str = typer.Option(..., "--trace-dir"),
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8011, "--port"),
) -> None:
    import uvicorn
    from grc.runtime.proxy import create_app

    uvicorn.run(create_app(config, rules_dir, trace_dir), host=host, port=port)


@app.command()
def mine(
    trace_dir: str = typer.Option(..., "--trace-dir"),
    out: str = typer.Option(..., "--out"),
) -> None:
    from grc.compiler.mine import mine_failures

    failures = mine_failures(trace_dir)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as handle:
        for item in failures:
            handle.write(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) + "\n")
    print(f"wrote {len(failures)} failures -> {out}")


@app.command()
def compile(
    failures: str = typer.Option(..., "--failures"),
    out: str = typer.Option(..., "--out"),
    patch_id: str = typer.Option("patch_auto_001", "--patch-id"),
    candidate_dir: str | None = typer.Option(None, "--candidate-dir"),
) -> None:
    from grc.compiler.trace_to_patch import compile_patch

    status_path = (Path(candidate_dir) / "compile_status.json") if candidate_dir else Path(out).with_name("compile_status.json")
    try:
        compile_status = compile_patch(failures, out, patch_id=patch_id, candidate_dir=candidate_dir)
    except Exception as exc:
        compile_status = {
            "status": "compile_failed",
            "patch_id": patch_id,
            "source_failure_count": None,
            "failure_ir_count": None,
            "rule_count": None,
            "high_value_error_types": [],
            "reason": f"compile raised {exc.__class__.__name__}: {exc}",
        }
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(compile_status, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(compile_status, ensure_ascii=False, indent=2))
        raise typer.Exit(code=1)

    print(f"wrote patch -> {out}")
    print(json.dumps(compile_status, ensure_ascii=False, indent=2))


@app.command()
def select(
    baseline_metrics: str = typer.Option(..., "--baseline-metrics"),
    candidate_metrics: str = typer.Option(..., "--candidate-metrics"),
    candidate_dir: str | None = typer.Option(None, "--candidate-dir"),
    rule_path: str | None = typer.Option(None, "--rule-path"),
    accepted_dir: str | None = typer.Option(None, "--accepted-dir"),
    rejected_dir: str | None = typer.Option(None, "--rejected-dir"),
    active_dir: str | None = typer.Option(None, "--active-dir"),
    out: str | None = typer.Option(None, "--out"),
) -> None:
    from grc.selector.pareto import select_patch, write_selection_outputs

    decision = select_patch(baseline_metrics, candidate_metrics)
    write_selection_outputs(decision, candidate_dir, rule_path, accepted_dir, rejected_dir, active_dir, out)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


@app.command()
def propose(
    failures: str = typer.Option(..., "--failures"),
    history: str = typer.Option(..., "--history"),
    out_dir: str = typer.Option(..., "--out-dir"),
    top_k_signatures: int = typer.Option(3, "--top-k-signatures"),
    target_category: str = typer.Option("multi_turn_miss_param", "--target-category"),
    holdout_category: str = typer.Option("simple_python", "--holdout-category"),
    iteration_id: str | None = typer.Option(None, "--iteration-id"),
) -> None:
    from grc.compiler.policy_proposal import generate_proposals

    summary = generate_proposals(
        Path(failures),
        Path(history),
        Path(out_dir),
        top_k_signatures_count=top_k_signatures,
        target_category=target_category,
        holdout_category=holdout_category,
        iteration_id=iteration_id,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
