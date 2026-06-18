"""Estimativa do fator de mando de campo e deteccao de campo neutro."""

from __future__ import annotations

import math

import pandas as pd

from src.utils.logging import get_logger

logger = get_logger(__name__)


def is_neutral_venue(competition: str, row: pd.Series) -> bool:
    """Determina se uma partida foi disputada em campo neutro.

    Prioriza a flag ``neutral`` (presente nos dados brutos do martj42). Sem ela,
    aplica uma heuristica simples: finais de Copa/Euro/Copa America costumam ser
    em sede neutra.

    Args:
        competition: nome da competicao (usado apenas na heuristica de fallback).
        row: linha da partida; se contiver ``neutral``, ela e usada diretamente.
    """
    if "neutral" in row and pd.notna(row["neutral"]):
        return bool(row["neutral"])

    comp = (competition or "").lower()
    neutral_hints = ("world cup", "euro", "copa américa", "copa america", "nations league")
    return any(h in comp for h in neutral_hints)


def compute_home_advantage(matches: pd.DataFrame) -> float:
    """Estima o fator de vantagem de mando de campo (escala logaritmica).

    Considera apenas partidas em campo nao-neutro e calcula o log da razao entre
    a media de gols do mandante e a do visitante::

        gamma = ln( media_gols_mandante / media_gols_visitante )

    O valor e aditivo na escala de log-ataque (consistente com o ``gamma`` do
    Dixon-Coles): ``gamma > 0`` indica vantagem do mandante.

    Args:
        matches: DataFrame com ``home_goals``, ``away_goals`` e (idealmente)
            ``neutral``/``is_neutral``.

    Returns:
        Fator de mando de campo (float). Retorna ``0.0`` se nao houver dados
        utilizaveis.
    """
    df = matches
    neutral_col = next((c for c in ("neutral", "is_neutral") if c in df.columns), None)
    if neutral_col is not None:
        df = df[~df[neutral_col].astype(bool)]

    if df.empty:
        logger.warning("Sem partidas em campo nao-neutro; home_advantage=0.0")
        return 0.0

    mean_home = float(df["home_goals"].mean())
    mean_away = float(df["away_goals"].mean())
    if mean_home <= 0 or mean_away <= 0:
        logger.warning("Medias de gols invalidas (%.3f / %.3f); home_advantage=0.0",
                       mean_home, mean_away)
        return 0.0

    gamma = math.log(mean_home / mean_away)
    logger.info(
        "Home advantage: media casa=%.3f, fora=%.3f -> gamma=%.4f (%d partidas)",
        mean_home, mean_away, gamma, len(df),
    )
    return gamma
