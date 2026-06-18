"""Forca de ataque/defesa por selecao e forma recente."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.utils.logging import get_logger

logger = get_logger(__name__)


def _long_team_view(matches: pd.DataFrame, weights: pd.Series | None) -> pd.DataFrame:
    """Reorganiza as partidas numa visao "por selecao por jogo".

    Cada partida gera duas linhas: uma para o mandante e outra para o visitante,
    com colunas ``team, scored, conceded, weight``.
    """
    if weights is None:
        weights = pd.Series(1.0, index=matches.index)
    weights = weights.reindex(matches.index).fillna(1.0)

    home = pd.DataFrame(
        {
            "team": matches["home_team"].values,
            "scored": matches["home_goals"].values,
            "conceded": matches["away_goals"].values,
            "weight": weights.values,
        }
    )
    away = pd.DataFrame(
        {
            "team": matches["away_team"].values,
            "scored": matches["away_goals"].values,
            "conceded": matches["home_goals"].values,
            "weight": weights.values,
        }
    )
    return pd.concat([home, away], ignore_index=True)


def compute_attack_defense_strength(
    matches: pd.DataFrame,
    teams: list[str] | None = None,
    *,
    weights: pd.Series | None = None,
) -> pd.DataFrame:
    """Estima forca de ataque e defesa de cada selecao.

    Usa a media (opcionalmente ponderada por ``weights``) de gols marcados e
    sofridos, normalizada pela media global de gols por time-jogo:

        attack_strength  = media_gols_marcados(team) / media_global
        defense_strength = media_gols_sofridos(team) / media_global

    Assim, ``attack_strength > 1`` indica ataque acima da media e
    ``defense_strength < 1`` indica defesa acima da media (sofre menos gols).

    Args:
        matches: DataFrame com ``home_team, away_team, home_goals, away_goals``.
        teams: subconjunto de selecoes a incluir; ``None`` usa todas.
        weights: pesos por partida (ex.: decaimento temporal), alinhados ao
            indice de ``matches``.

    Returns:
        DataFrame ``[team, attack_strength, defense_strength, matches_played]``,
        ordenado por forca de ataque decrescente.
    """
    if matches.empty:
        return pd.DataFrame(
            columns=["team", "attack_strength", "defense_strength", "matches_played"]
        )

    long = _long_team_view(matches, weights)

    def _wmean(values: pd.Series, w: pd.Series) -> float:
        total = w.sum()
        return float((values * w).sum() / total) if total > 0 else float("nan")

    global_avg = _wmean(long["scored"], long["weight"])
    if not global_avg or np.isnan(global_avg) or global_avg <= 0:
        global_avg = float(long["scored"].mean()) or 1.0

    grouped = long.groupby("team")
    rows = []
    for team, g in grouped:
        if teams is not None and team not in teams:
            continue
        rows.append(
            {
                "team": team,
                "attack_strength": _wmean(g["scored"], g["weight"]) / global_avg,
                "defense_strength": _wmean(g["conceded"], g["weight"]) / global_avg,
                "matches_played": int(len(g)),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out.sort_values("attack_strength", ascending=False).reset_index(drop=True)
    logger.info("Forca estimada para %d selecoes (media global=%.3f gols/jogo).",
                len(out), global_avg)
    return out


def compute_recent_form(matches: pd.DataFrame, team: str, n_games: int = 5) -> float:
    """Retorna a forma recente de uma selecao (pontos por jogo nos ultimos N).

    Pontuacao no estilo classico: vitoria=3, empate=1, derrota=0, calculada na
    perspectiva da selecao (mandante ou visitante).

    Args:
        matches: DataFrame com ``date, home_team, away_team, home_goals, away_goals``.
        team: selecao alvo.
        n_games: numero de jogos recentes a considerar.

    Returns:
        Media de pontos por jogo (0.0 a 3.0). ``nan`` se a selecao nao tiver jogos.
    """
    mask = (matches["home_team"] == team) | (matches["away_team"] == team)
    sub = matches.loc[mask].sort_values("date").tail(n_games)
    if sub.empty:
        return float("nan")

    points = 0
    for row in sub.itertuples(index=False):
        is_home = row.home_team == team
        gf = row.home_goals if is_home else row.away_goals
        ga = row.away_goals if is_home else row.home_goals
        if gf > ga:
            points += 3
        elif gf == ga:
            points += 1
    return points / len(sub)
