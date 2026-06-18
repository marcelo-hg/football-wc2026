"""Orquestracao da engenharia de features.

Le os CSVs de ``data/raw/``, monta o dataset por partida e a tabela de forca das
selecoes, e grava ambos em ``data/processed/``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.features.home_advantage import compute_home_advantage
from src.features.match_features import build_match_dataset
from src.features.team_features import compute_attack_defense_strength
from src.features.weight_decay import compute_time_weights
from src.utils.logging import get_logger

logger = get_logger(__name__)

MATCHES_FILE = "matches.csv"
ELO_FILE = "elo_ratings.csv"
FIFA_FILE = "fifa_rankings.csv"
MARKET_FILE = "market_values.csv"

OUT_FEATURES = "matches_features.csv"
OUT_STRENGTHS = "team_strengths.csv"


def _read_optional(path: Path) -> pd.DataFrame | None:
    """Le um CSV se existir; caso contrario retorna ``None`` (fonte ausente)."""
    if path.exists():
        df = pd.read_csv(path)
        logger.info("Lido %s (%d linhas).", path.name, len(df))
        return df
    logger.warning("Arquivo opcional ausente: %s", path)
    return None


def run_feature_pipeline(raw_dir: str, processed_dir: str, config: dict) -> None:
    """Le ``data/raw/``, aplica as transformacoes e grava ``data/processed/``.

    Args:
        raw_dir: diretorio com os CSVs brutos (saida do scraping).
        processed_dir: diretorio de saida dos datasets processados.
        config: dicionario (tipicamente ``configs/data.yaml``); usa as chaves
            ``competition_weights`` e ``features.time_decay_half_life_days``.
    """
    raw = Path(raw_dir)
    out = Path(processed_dir)
    out.mkdir(parents=True, exist_ok=True)

    matches = _read_optional(raw / MATCHES_FILE)
    if matches is None or matches.empty:
        raise FileNotFoundError(
            f"'{MATCHES_FILE}' nao encontrado em {raw}. Rode o scraping antes (make scrape)."
        )

    elo = _read_optional(raw / ELO_FILE)
    fifa = _read_optional(raw / FIFA_FILE)
    mkt = _read_optional(raw / MARKET_FILE)

    features_cfg = config.get("features", {})
    half_life = int(features_cfg.get("time_decay_half_life_days", 365))
    weight_map = config.get("competition_weights", {})

    # 1) Dataset por partida.
    dataset = build_match_dataset(
        matches,
        elo=elo,
        fifa=fifa,
        mkt=mkt,
        competition_weights=weight_map,
        half_life_days=half_life,
    )
    features_path = out / OUT_FEATURES
    dataset.to_csv(features_path, index=False)
    logger.info("[features] %d partidas -> %s", len(dataset), features_path)

    # 2) Forca de ataque/defesa por selecao (ponderada por decaimento temporal).
    matches = matches.copy()
    matches["date"] = pd.to_datetime(matches["date"])
    weights = compute_time_weights(matches["date"], half_life_days=half_life)
    strengths = compute_attack_defense_strength(matches, weights=weights)

    home_adv = compute_home_advantage(matches)
    strengths.attrs["home_advantage"] = home_adv

    strengths_path = out / OUT_STRENGTHS
    strengths.to_csv(strengths_path, index=False)
    logger.info(
        "[features] forca de %d selecoes (home_advantage=%.4f) -> %s",
        len(strengths), home_adv, strengths_path,
    )
