"""Juncao das fontes brutas em um dataset por partida pronto para modelagem."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.weight_decay import apply_competition_weights, compute_time_weights
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Ordem canonica das colunas de saida (conforme o plano).
FEATURE_COLUMNS = [
    "date",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
    "home_elo",
    "away_elo",
    "elo_diff",
    "home_fifa_rank",
    "away_fifa_rank",
    "rank_diff",
    "home_market_value",
    "away_market_value",
    "market_diff",
    "competition_weight",
    "is_neutral",
    "result",
]


def encode_result(home_goals: int, away_goals: int) -> str:
    """Codifica o resultado na perspectiva do mandante.

    Returns:
        ``"W"`` (vitoria do mandante), ``"D"`` (empate) ou ``"L"`` (derrota).
    """
    if home_goals > away_goals:
        return "W"
    if home_goals == away_goals:
        return "D"
    return "L"


def _asof_lookup(
    matches: pd.DataFrame, source: pd.DataFrame, team_col: str, value_cols: list[str]
) -> pd.DataFrame:
    """As-of join: valor mais recente (<= data da partida) por selecao.

    Returns:
        DataFrame indexado como ``matches`` com as colunas ``value_cols``.
    """
    left = matches[["date", team_col]].reset_index(names="_row").sort_values("date")
    src = source[["team", "date", *value_cols]].sort_values("date")
    merged = pd.merge_asof(
        left,
        src,
        on="date",
        left_by=team_col,
        right_by="team",
        direction="backward",
    )
    # Reindexa pela posicao original da partida para reverter a ordenacao por data
    # (merge_asof reordena por data; alinhamento posicional seria fragil com empates).
    return merged.set_index("_row")[value_cols].sort_index()


def _attach_source(
    matches: pd.DataFrame,
    source: pd.DataFrame | None,
    value_cols: list[str],
    rename: dict[str, str],
) -> pd.DataFrame:
    """Anexa colunas ``home_*``/``away_*`` de uma fonte com chave temporal.

    Se ``source`` for ``None``/vazio, cria as colunas preenchidas com ``NaN``.
    """
    out = matches.copy()
    if source is None or source.empty:
        for side in ("home", "away"):
            for prefixed in rename.values():
                out[f"{side}_{prefixed}"] = np.nan
        return out

    src = source.copy()
    src["date"] = pd.to_datetime(src["date"])
    out = out.reset_index(drop=True)  # garante indice 0..n-1 para alinhar com _asof_lookup
    for side in ("home", "away"):
        vals = _asof_lookup(out, src, f"{side}_team", value_cols)
        for col in value_cols:
            out[f"{side}_{rename[col]}"] = vals[col]  # alinhamento por indice
    return out


def _attach_market_values(matches: pd.DataFrame, mkt: pd.DataFrame | None) -> pd.DataFrame:
    """Anexa o valor de mercado mais recente de cada selecao (proxy de qualidade).

    Como o valor de mercado e essencialmente um instantaneo, usamos o registro
    mais recente por selecao para todas as partidas.
    """
    out = matches.copy()
    if mkt is None or mkt.empty:
        out["home_market_value"] = np.nan
        out["away_market_value"] = np.nan
        return out

    latest = (
        mkt.sort_values("year").groupby("team", as_index=False).tail(1)[["team", "market_value_eur"]]
    )
    for side in ("home", "away"):
        out = out.merge(
            latest.rename(
                columns={"team": f"{side}_team", "market_value_eur": f"{side}_market_value"}
            ),
            on=f"{side}_team",
            how="left",
        )
    return out


def build_match_dataset(
    matches: pd.DataFrame,
    elo: pd.DataFrame | None = None,
    fifa: pd.DataFrame | None = None,
    mkt: pd.DataFrame | None = None,
    *,
    competition_weights: dict | None = None,
    half_life_days: int = 365,
) -> pd.DataFrame:
    """Junta todas as fontes em um dataset por partida.

    Args:
        matches: resultados ``[date, home_team, away_team, home_goals,
            away_goals, competition, neutral]``.
        elo: ratings Elo ``[team, date, elo]`` (opcional).
        fifa: ranking FIFA ``[team, date, rank, points]`` (opcional).
        mkt: valores de mercado ``[team, year, market_value_eur]`` (opcional).
        competition_weights: mapa ``{competicao: peso}``; sem ele, todas as
            partidas recebem peso 0.5.
        half_life_days: meia-vida do decaimento temporal (coluna ``time_weight``).

    Returns:
        DataFrame com as colunas de :data:`FEATURE_COLUMNS`, mais ``competition``
        e ``time_weight`` ao final.
    """
    df = matches.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Fontes com chave temporal (as-of join).
    df = _attach_source(df, elo, ["elo"], {"elo": "elo"})
    df = _attach_source(df, fifa, ["rank", "points"], {"rank": "fifa_rank", "points": "fifa_points"})
    df = _attach_market_values(df, mkt)

    # Diferencas entre mandante e visitante.
    df["elo_diff"] = df["home_elo"] - df["away_elo"]
    df["rank_diff"] = df["home_fifa_rank"] - df["away_fifa_rank"]
    df["market_diff"] = df["home_market_value"] - df["away_market_value"]

    # Pesos e flags.
    weight_map = competition_weights or {}
    df = apply_competition_weights(df, weight_map)
    df["time_weight"] = compute_time_weights(df["date"], half_life_days=half_life_days)
    df["is_neutral"] = df["neutral"].astype(bool) if "neutral" in df.columns else False

    # Alvo.
    df["result"] = [encode_result(h, a) for h, a in zip(df["home_goals"], df["away_goals"])]

    extras = [c for c in ("competition", "time_weight") if c in df.columns]
    ordered = FEATURE_COLUMNS + extras
    out = df[[c for c in ordered if c in df.columns]]
    logger.info("Dataset de partidas montado: %d linhas x %d colunas.", len(out), out.shape[1])
    return out
