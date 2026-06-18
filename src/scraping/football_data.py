"""Coleta de resultados historicos de partidas internacionais.

O plano original aponta football-data.co.uk como fonte. Na pratica, aquela
pagina nao expoe um CSV consolidado de partidas internacionais de forma
estavel. Usamos como fonte primaria o dataset publico e mantido
``martj42/international_results`` (resultados oficiais e amistosos desde 1872),
cujo esquema mapeia diretamente nas colunas exigidas pelo plano:

    date, home_team, away_team, home_score, away_score, tournament, city,
    country, neutral

A saida e normalizada para:

    [date, home_team, away_team, home_goals, away_goals, competition, neutral]
"""

from __future__ import annotations

import io

import pandas as pd

from src.scraping._http import get
from src.utils.logging import get_logger

logger = get_logger(__name__)

# CSV consolidado (raw) com todos os resultados internacionais.
RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)

OUTPUT_COLUMNS = [
    "date",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
    "competition",
    "neutral",
]


def fetch_international_matches(
    start_year: int,
    end_year: int,
    *,
    include_friendlies: bool = True,
    url: str = RESULTS_URL,
) -> pd.DataFrame:
    """Raspa resultados historicos de partidas internacionais.

    Args:
        start_year: ano inicial (inclusivo).
        end_year: ano final (inclusivo).
        include_friendlies: se ``False``, descarta partidas cujo torneio e
            ``"Friendly"``.
        url: endereco do CSV consolidado (parametrizavel para testes/mirrors).

    Returns:
        DataFrame com colunas
        ``[date, home_team, away_team, home_goals, away_goals, competition, neutral]``.
        Partidas ainda nao disputadas (placar ausente) sao descartadas.
    """
    logger.info("Baixando resultados internacionais de %s", url)
    resp = get(url)
    raw = pd.read_csv(io.StringIO(resp.text))
    logger.info("CSV bruto: %d linhas", len(raw))

    df = raw.rename(
        columns={
            "home_score": "home_goals",
            "away_score": "away_goals",
            "tournament": "competition",
        }
    )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # Janela temporal (inclusiva nos dois extremos).
    mask = (df["date"].dt.year >= start_year) & (df["date"].dt.year <= end_year)
    df = df.loc[mask].copy()

    # Descarta partidas futuras / sem placar.
    df = df.dropna(subset=["home_goals", "away_goals"])
    df["home_goals"] = df["home_goals"].astype(int)
    df["away_goals"] = df["away_goals"].astype(int)

    df["neutral"] = df["neutral"].astype(bool)

    if not include_friendlies:
        before = len(df)
        df = df[df["competition"].str.casefold() != "friendly"]
        logger.info("Amistosos removidos: %d partidas", before - len(df))

    df = df[OUTPUT_COLUMNS].sort_values("date").reset_index(drop=True)
    logger.info(
        "Partidas %d-%d: %d registros, %d selecoes distintas",
        start_year,
        end_year,
        len(df),
        pd.concat([df["home_team"], df["away_team"]]).nunique(),
    )
    return df


def normalize_team_names(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Padroniza nomes de selecoes usando um dicionario de mapeamento.

    Aplica o mapa as colunas ``home_team`` e ``away_team``. Nomes ausentes no
    dicionario sao mantidos como estao (o mapeamento e parcial por design).

    Args:
        df: DataFrame com colunas ``home_team`` e ``away_team``.
        mapping: dicionario ``{nome_origem: nome_canonico}``.

    Returns:
        Novo DataFrame com os nomes normalizados.
    """
    if not mapping:
        return df.copy()

    out = df.copy()
    for col in ("home_team", "away_team"):
        if col in out.columns:
            out[col] = out[col].map(lambda name: mapping.get(name, name))
    return out
