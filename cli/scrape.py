"""CLI de coleta de dados: orquestra os scrapers e (opcionalmente) valida.

Uso:
    python cli/scrape.py --config configs/data.yaml
    python cli/scrape.py --config configs/data.yaml --validate-only
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

# Garante que a raiz do projeto esteja no sys.path quando executado como script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scraping.pipeline import run_all_scrapers, validate_raw_data  # noqa: E402
from src.utils.config import load_config  # noqa: E402
from src.utils.logging import get_logger  # noqa: E402

logger = get_logger("cli.scrape")
app = typer.Typer(add_completion=False, help="Coleta de dados das fontes configuradas.")


@app.command()
def scrape(
    config: str = typer.Option("configs/data.yaml", "--config", help="Arquivo de config."),
    validate_only: bool = typer.Option(
        False, "--validate-only", help="Apenas valida os CSVs ja existentes em data/raw/."
    ),
) -> None:
    """Executa o pipeline de scraping e imprime o relatorio de validacao."""
    cfg = load_config(config)

    if not validate_only:
        run_all_scrapers(cfg)

    output_dir = cfg.get("output_dir", "data/raw/")
    report = validate_raw_data(output_dir)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
