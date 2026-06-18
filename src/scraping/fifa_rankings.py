"""Coleta do ranking FIFA masculino (posicao + pontos) por data de publicacao.

A FIFA expoe os dados via API JSON em
``https://inside.fifa.com/api/ranking-overview?locale=en&dateId={dateId}``.
A lista de ``dateId`` disponiveis (um por publicacao do ranking) esta embutida
na pagina ``https://inside.fifa.com/fifa-world-ranking/men`` como objetos
``{"id": "idNNNNN", "iso": "YYYY-MM-DD..."}``.

Fluxo:
    1. Descobrir o mapa ``dateId -> data`` a partir da pagina.
    2. Para cada mes/data solicitada, buscar o ranking via API.

Saida: ``[team, date, rank, points]``.
"""

from __future__ import annotations

import re

import pandas as pd

from src.scraping._http import build_session, get
from src.utils.logging import get_logger

logger = get_logger(__name__)

RANKING_PAGE = "https://inside.fifa.com/fifa-world-ranking/men"
API_URL = "https://inside.fifa.com/api/ranking-overview?locale=en&dateId={date_id}"

_DATE_ENTRY_RE = re.compile(r'\{"id":"(id\d+)","iso":"(\d{4}-\d{2}-\d{2})')


def discover_ranking_dates(*, session=None) -> pd.DataFrame:
    """Descobre as datas de publicacao do ranking e seus ``dateId``.

    Returns:
        DataFrame ``[date_id, date]`` ordenado por data (mais antigo primeiro).
    """
    resp = get(RANKING_PAGE, session=session)
    pairs = _DATE_ENTRY_RE.findall(resp.text)
    if not pairs:
        raise RuntimeError(
            "Nao foi possivel extrair a lista de datas do ranking FIFA "
            "(layout da pagina pode ter mudado)."
        )
    df = pd.DataFrame(pairs, columns=["date_id", "date"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates("date_id").sort_values("date").reset_index(drop=True)
    logger.info("Datas de ranking FIFA descobertas: %d (de %s a %s)",
                len(df), df["date"].min().date(), df["date"].max().date())
    return df


def _fetch_single_ranking(date_id: str, date: pd.Timestamp, *, session) -> pd.DataFrame:
    """Busca o ranking de uma unica data via API."""
    resp = get(API_URL.format(date_id=date_id), session=session)
    payload = resp.json()
    rows: list[dict] = []
    for entry in payload.get("rankings", []):
        item = entry.get("rankingItem", {})
        name = item.get("name")
        if not name:
            continue
        rows.append(
            {
                "team": name,
                "date": date,
                "rank": item.get("rank"),
                "points": item.get("totalPoints"),
            }
        )
    return pd.DataFrame(rows)


def _select_date_ids(dates_df: pd.DataFrame, months: list[str] | None) -> pd.DataFrame:
    """Filtra as datas de publicacao pelos meses solicitados.

    Args:
        dates_df: saida de :func:`discover_ranking_dates`.
        months: lista de meses no formato ``"YYYY-MM"``. Se ``None``, usa todas.
            Para cada mes, escolhe a ultima publicacao daquele mes.
    """
    if not months:
        return dates_df

    wanted = set(months)
    dates_df = dates_df.copy()
    dates_df["ym"] = dates_df["date"].dt.strftime("%Y-%m")
    selected = (
        dates_df[dates_df["ym"].isin(wanted)]
        .sort_values("date")
        .groupby("ym", as_index=False)
        .last()
    )
    missing = wanted - set(selected["ym"])
    if missing:
        logger.warning("Sem ranking FIFA publicado para: %s", sorted(missing))
    return selected[["date_id", "date"]]


def fetch_fifa_rankings(months: list[str] | None = None) -> pd.DataFrame:
    """Coleta o ranking FIFA para os meses especificados.

    Args:
        months: lista de meses ``"YYYY-MM"`` (ex.: ``["2025-04", "2025-07"]``).
            Se ``None``, coleta todas as publicacoes disponiveis (historico
            completo) — pode ser demorado (centenas de requisicoes).

    Returns:
        DataFrame ``[team, date, rank, points]``.
    """
    session = build_session()
    dates_df = discover_ranking_dates(session=session)
    selected = _select_date_ids(dates_df, months)

    frames: list[pd.DataFrame] = []
    for row in selected.itertuples(index=False):
        try:
            df = _fetch_single_ranking(row.date_id, row.date, session=session)
        except Exception as exc:  # noqa: BLE001 — uma data nao deve travar o restante
            logger.error("Falha ao buscar ranking FIFA de %s: %s", row.date.date(), exc)
            continue
        if df.empty:
            logger.warning("Ranking FIFA vazio para %s (%s)", row.date.date(), row.date_id)
            continue
        logger.info("Ranking FIFA %s: %d selecoes", row.date.date(), len(df))
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["team", "date", "rank", "points"])
    return pd.concat(frames, ignore_index=True).sort_values(["date", "rank"]).reset_index(
        drop=True
    )
