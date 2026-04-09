from __future__ import annotations

import json
from pathlib import Path

import typer
import uvicorn

from grc.compiler.mine import mine_failures
from grc.compiler.trace_to_patch import compile_patch
from grc.runtime.proxy import create_app
from grc.selector.pareto import select_patch

app = typer.Typer(no_args_is_help=True)


@app.command()
def serve(
    config: str = typer.Option(..., "--config"),
    rules_dir: str = typer.Option(..., "--rules-dir"),
    trace_dir: str = typer.Option(..., "--trace-dir"),
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8011, "--port"),
) -> None:
    uvicorn.run(create_app(config, rules_dir, trace_dir), host=host, port=port)


@app.command()
def mine(
    trace_dir: str = typer.Option(..., "--trace-dir"),
    out: str = typer.Option(..., "--out"),
) -> None:
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
) -> None:
    compile_patch(failures, out, patch_id=patch_id)
    print(f"wrote patch -> {out}")


@app.command()
def select(
    baseline_metrics: str = typer.Option(..., "--baseline-metrics"),
    candidate_metrics: str = typer.Option(..., "--candidate-metrics"),
) -> None:
    decision = select_patch(baseline_metrics, candidate_metrics)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()

