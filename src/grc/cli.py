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

    status = compile_patch(failures, out, patch_id=patch_id, candidate_dir=candidate_dir)
    print(json.dumps(status, ensure_ascii=False, indent=2))


@app.command()
def select(
    baseline_metrics: str = typer.Option(..., "--baseline-metrics"),
    candidate_metrics: str = typer.Option(..., "--candidate-metrics"),
    baseline_manifest: str | None = typer.Option(None, "--baseline-manifest"),
    candidate_manifest: str | None = typer.Option(None, "--candidate-manifest"),
    compile_status: str | None = typer.Option(None, "--compile-status"),
    candidate_dir: str | None = typer.Option(None, "--candidate-dir"),
    rule_path: str | None = typer.Option(None, "--rule-path"),
    accepted_dir: str | None = typer.Option(None, "--accepted-dir"),
    rejected_dir: str | None = typer.Option(None, "--rejected-dir"),
    active_dir: str | None = typer.Option(None, "--active-dir"),
    out: str | None = typer.Option(None, "--out"),
) -> None:
    from grc.selector.pareto import select_patch, write_selection_outputs

    decision = select_patch(
        baseline_metrics,
        candidate_metrics,
        baseline_manifest_path=baseline_manifest,
        candidate_manifest_path=candidate_manifest,
        compile_status_path=compile_status,
    )
    write_selection_outputs(decision, candidate_dir, rule_path, accepted_dir, rejected_dir, active_dir, out)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
