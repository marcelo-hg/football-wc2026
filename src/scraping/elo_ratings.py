"""Coleta da serie historica de rating Elo por selecao (eloratings.net).

O site renderiza os graficos via JavaScript, mas os dados de cada selecao estao
disponiveis em um TSV plano em ``https://www.eloratings.net/{Team}.tsv``, onde o
nome usa ``_`` no lugar de espacos (ex.: ``United_States``).

Cada linha do TSV e uma partida da selecao, com o seguinte layout (16 colunas):

    0 ano | 1 mes | 2 dia | 3 cod_mandante | 4 cod_visitante |
    5 gols_mandante | 6 gols_visitante | 7 tipo | 8 sede |
    9 var_rank | 10 elo_mandante | 11 elo_visitante | ... (demais ignoradas)

Para a selecao da pagina, o Elo (pos-jogo) e a coluna 10 quando ela e mandante e
a coluna 11 quando e visitante. A saida e a serie ``[team, date, elo]``.
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd

from src.scraping._http import build_session, get
from src.utils.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://www.eloratings.net/{team}.tsv"

# Indices de coluna no TSV por partida.
_COL_HOME_CODE = 3
_COL_AWAY_CODE = 4
_COL_HOME_ELO = 10
_COL_AWAY_ELO = 11


def _team_to_url_slug(team: str, url_overrides: dict[str, str] | None = None) -> str:
    """Converte o nome da selecao no slug de URL do eloratings.net.

    A regra padrao e trocar espacos por ``_``. Casos especiais (ex.: nomes que o
    site grafa de forma diferente) podem ser passados em ``url_overrides``.
    """
    if url_overrides and team in url_overrides:
        return url_overrides[team]
    return team.replace(" ", "_")


def _parse_team_tsv(text: str) -> pd.DataFrame:
    """Parseia o TSV de uma selecao em ``[date, home_code, away_code, home_elo, away_elo]``."""
    records: list[dict] = []
    for line in text.strip().splitlines():
        cols = line.split("\t")
        if len(cols) <= _COL_AWAY_ELO:
            continue
        try:
            date = _dt.date(int(cols[0]), int(cols[1]), int(cols[2]))
            home_elo = int(cols[_COL_HOME_ELO])
            away_elo = int(cols[_COL_AWAY_ELO])
        except (ValueError, IndexError):
            continue
        records.append(
            {
                "date": date,
                "home_code": cols[_COL_HOME_CODE],
                "away_code": cols[_COL_AWAY_CODE],
                "home_elo": home_elo,
                "away_elo": away_elo,
            }
        )
    return pd.DataFrame.from_records(records)


def _extract_team_series(team: str, parsed: pd.DataFrame) -> pd.DataFrame:
    """Extrai a serie ``[team, date, elo]`` da selecao a partir do TSV parseado.

    O codigo de 2 letras da selecao e inferido como aquele presente em todas as
    partidas (a selecao da pagina aparece como mandante ou visitante em cada jogo).
    """
    if parsed.empty:
        return pd.DataFrame(columns=["team", "date", "elo"])

    home_counts = parsed["home_code"].value_counts()
    away_counts = parsed["away_code"].value_counts()
    totals = home_counts.add(away_counts, fill_value=0)
    team_code = totals.idxmax()  # codigo presente em (quase) toda partida

    is_home = parsed["home_code"] == team_code
    elo = parsed["home_elo"].where(is_home, parsed["away_elo"])

    out = pd.DataFrame(
        {
            "team": team,
            "date": pd.to_datetime(parsed["date"]),
            "elo": elo.astype(int),
        }
    )
    return out.sort_values("date").reset_index(drop=True)


def fetch_elo_ratings(
    teams: list[str],
    *,
    url_overrides: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Raspa a serie historica de Elo para as selecoes informadas.

    Args:
        teams: lista de nomes de selecoes (ex.: ``["Brazil", "United States"]``).
        url_overrides: mapa opcional ``{nome: slug_url}`` para selecoes cujo nome
            no eloratings.net difere do padrao "espacos por underscore".

    Returns:
        DataFrame concatenado com colunas ``[team, date, elo]``. Selecoes que
        falharem (ex.: nome inexistente / 404) sao registradas no log e omitidas.
    """
    frames: list[pd.DataFrame] = []
    session = build_session()
    for team in teams:
        slug = _team_to_url_slug(team, url_overrides)
        url = BASE_URL.format(team=slug)
        try:
            resp = get(url, session=session, retries=2)
        except Exception as exc:  # noqa: BLE001 — uma selecao nao deve travar as demais
            logger.error("Falha ao baixar Elo de '%s' (%s): %s", team, url, exc)
            continue

        resp.encoding = "utf-8"
        parsed = _parse_team_tsv(resp.text)
        series = _extract_team_series(team, parsed)
        if series.empty:
            logger.warning("Nenhum registro de Elo encontrado para '%s'", team)
            continue
        logger.info("Elo '%s': %d registros (%s a %s)", team, len(series),
                    series["date"].min().date(), series["date"].max().date())
        frames.append(series)

    if not frames:
        return pd.DataFrame(columns=["team", "date", "elo"])
    return pd.concat(frames, ignore_index=True)


def get_elo_at_date(df: pd.DataFrame, team: str, date: str | _dt.date) -> float:
    """Retorna o Elo de uma selecao na data mais proxima (anterior ou igual) a ``date``.

    Faz um *as-of join* simples: usa o ultimo Elo conhecido ate a data pedida.
    Se nao houver registro anterior, retorna o primeiro registro disponivel.

    Args:
        df: DataFrame ``[team, date, elo]`` (saida de :func:`fetch_elo_ratings`).
        team: selecao desejada.
        date: data de referencia.

    Raises:
        KeyError: se a selecao nao existir no DataFrame.
    """
    sub = df[df["team"] == team].sort_values("date")
    if sub.empty:
        raise KeyError(f"Selecao '{team}' ausente nos ratings Elo.")

    target = pd.to_datetime(date)
    prior = sub[sub["date"] <= target]
    chosen = prior.iloc[-1] if not prior.empty else sub.iloc[0]
    return float(chosen["elo"])
