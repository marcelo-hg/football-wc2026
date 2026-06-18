"""Pesos de amostra: decaimento temporal e peso por competicao.

Partidas recentes e de competicoes mais relevantes devem pesar mais na
estimacao de forca das selecoes. Estes pesos sao usados como `sample weights`
pelos modelos (Poisson/Dixon-Coles) e na agregacao de forca de ataque/defesa.
"""

from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from src.utils.logging import get_logger

logger = get_logger(__name__)


def compute_time_weights(dates: pd.Series, half_life_days: int = 365) -> pd.Series:
    """Aplica decaimento exponencial: jogos recentes recebem peso maior.

    Formula: ``w = exp(-lambda * days_ago)``, com ``lambda = ln(2)/half_life_days``.
    O peso e medido em relacao a data mais recente da serie (peso 1.0), de modo
    que uma partida com ``half_life_days`` dias de idade recebe peso ``0.5``.

    Args:
        dates: serie de datas das partidas.
        half_life_days: meia-vida do decaimento, em dias.

    Returns:
        Serie de pesos (float em ``(0, 1]``), alinhada ao indice de ``dates``.
    """
    if half_life_days <= 0:
        raise ValueError("half_life_days deve ser positivo.")

    dt = pd.to_datetime(dates)
    reference = dt.max()
    days_ago = (reference - dt).dt.days.clip(lower=0)
    lam = math.log(2) / half_life_days
    weights = np.exp(-lam * days_ago)
    return pd.Series(weights, index=dates.index, name="time_weight")


# Regras de classificacao de competicao -> chave canonica do weight_map.
# Avaliadas em ordem; a primeira que casar vence.
_COMPETITION_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"world cup qualif", re.I), "Qualifiers"),
    (re.compile(r"qualif", re.I), "Qualifiers"),
    (re.compile(r"world cup", re.I), "FIFA World Cup"),
    (re.compile(r"\beuro\b|european champ", re.I), "UEFA Euro"),
    (re.compile(r"copa am[eé]rica", re.I), "Copa America"),
    (re.compile(r"african cup|africa cup|afcon", re.I), "African Cup of Nations"),
    (re.compile(r"nations league", re.I), "Nations League"),
    (re.compile(r"friendly", re.I), "Friendly"),
]


def classify_competition(competition: str) -> str:
    """Mapeia o nome bruto de uma competicao para uma chave canonica.

    Ex.: ``"FIFA World Cup qualification"`` -> ``"Qualifiers"``,
    ``"Copa América"`` -> ``"Copa America"``. Sem correspondencia, retorna o
    proprio nome (o chamador decide o peso padrao).
    """
    if not isinstance(competition, str):
        return "Friendly"
    for pattern, key in _COMPETITION_RULES:
        if pattern.search(competition):
            return key
    return competition


def apply_competition_weights(
    df: pd.DataFrame,
    weight_map: dict,
    *,
    default: float = 0.5,
    competition_col: str = "competition",
) -> pd.DataFrame:
    """Adiciona a coluna ``competition_weight`` com base no tipo de competicao.

    Args:
        df: DataFrame com a coluna de competicao.
        weight_map: mapa ``{chave_canonica: peso}`` (ex.: ``{"FIFA World Cup": 1.0}``).
        default: peso usado quando a competicao nao tem entrada no mapa.
        competition_col: nome da coluna de competicao.

    Returns:
        Novo DataFrame com a coluna ``competition_weight`` adicionada.
    """
    out = df.copy()
    if competition_col not in out.columns:
        logger.warning("Coluna '%s' ausente; competition_weight=%.2f para tudo.",
                       competition_col, default)
        out["competition_weight"] = default
        return out

    canonical = out[competition_col].map(classify_competition)
    out["competition_weight"] = canonical.map(lambda k: weight_map.get(k, default)).astype(float)
    return out
