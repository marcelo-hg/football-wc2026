"""CLI de engenharia de features: le data/raw/ e gera data/processed/.

Uso:
    python cli/features.py --config configs/data.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.features.pipeline import run_feature_pipeline  # noqa: E402
from src.utils.config import load_config  # noqa: E402
from src.utils.logging import get_logger  # noqa: E402

logger = get_logger("cli.features")
app = typer.Typer(add_completion=False, help="Gera features processadas a partir de data/raw/.")


@app.command()
def features(
    config: str = typer.Option("configs/data.yaml", "--config", help="Arquivo de config."),
    raw_dir: str = typer.Option("data/raw/", "--raw-dir", help="Diretorio dos dados brutos."),
    processed_dir: str = typer.Option(
        "data/processed/", "--processed-dir", help="Diretorio de saida processada."
    ),
) -> None:
    """Executa o pipeline de features."""
    cfg = load_config(config)
    run_feature_pipeline(raw_dir, processed_dir, cfg)


if __name__ == "__main__":
    app()
