"""Modulo de coleta de dados (scraping) para o worldcup2026-predictor.

Fontes implementadas:
    * football_data  -> resultados historicos de partidas internacionais
    * elo_ratings    -> serie historica de rating Elo por selecao
    * fifa_rankings  -> ranking FIFA mensal (posicao + pontos)
    * transfermarkt  -> valor de mercado dos elencos (requer Playwright)

A orquestracao fica em :mod:`src.scraping.pipeline`.
"""

from src.scraping.elo_ratings import fetch_elo_ratings, get_elo_at_date
from src.scraping.fifa_rankings import fetch_fifa_rankings
from src.scraping.football_data import fetch_international_matches, normalize_team_names
from src.scraping.transfermarkt import fetch_market_values

__all__ = [
    "fetch_international_matches",
    "normalize_team_names",
    "fetch_elo_ratings",
    "get_elo_at_date",
    "fetch_fifa_rankings",
    "fetch_market_values",
]
