import logging

import typer

from app.cli.bench.commands import cli as bench_cli
from app.cli.eval.commands import cli as eval_cli

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)

cli = typer.Typer(help=__doc__)

cli.add_typer(bench_cli, name="bench", help="Run benchmarks")
cli.add_typer(eval_cli, name="eval", help="Run evaluations")

if __name__ == "__main__":
    cli()
