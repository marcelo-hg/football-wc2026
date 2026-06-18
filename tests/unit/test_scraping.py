"""Testes unitarios do modulo de scraping (logica pura, sem acesso a rede)."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.scraping.elo_ratings import _extract_team_series, _parse_team_tsv, get_elo_at_date
from src.scraping.fifa_rankings import _DATE_ENTRY_RE, _select_date_ids
from src.scraping.football_data import normalize_team_names
from src.scraping.transfermarkt import parse_market_value


# --------------------------------------------------------------------------- #
# football_data
# --------------------------------------------------------------------------- #
def test_normalize_team_names_applies_mapping_partially():
    df = pd.DataFrame(
        {
            "home_team": ["USA", "Brazil"],
            "away_team": ["South Korea", "Argentina"],
        }
    )
    mapping = {"USA": "United States", "South Korea": "Korea Republic"}
    out = normalize_team_names(df, mapping)

    assert out.loc[0, "home_team"] == "United States"
    assert out.loc[0, "away_team"] == "Korea Republic"
    # Nomes ausentes no mapa permanecem inalterados.
    assert out.loc[1, "home_team"] == "Brazil"
    assert out.loc[1, "away_team"] == "Argentina"


def test_normalize_team_names_empty_mapping_is_noop():
    df = pd.DataFrame({"home_team": ["A"], "away_team": ["B"]})
    out = normalize_team_names(df, {})
    pd.testing.assert_frame_equal(out, df)


# --------------------------------------------------------------------------- #
# elo_ratings
# --------------------------------------------------------------------------- #
# Layout real (16 colunas): ano mes dia codH codA golH golA tipo sede var
#                           eloH eloA ...
_TSV_SAMPLE = "\n".join(
    [
        # Brazil (BR) fora contra Japan (JP): elo do Brasil em col 11 = 1978
        "2025\t10\t14\tJP\tBR\t3\t2\tF\tJP\t-8\t1871\t1978\t0\t-8\t1\t1",
        # Brazil (BR) em casa contra Senegal (SN): elo do Brasil em col 10 = 1986
        "2025\t11\t15\tBR\tSN\t2\t0\tF\tBR\t8\t1986\t1801\t0\t8\t1\t1",
        # Brazil (BR) em casa contra Tunisia (TN): elo do Brasil em col 10 = 1978
        "2025\t11\t18\tBR\tTN\t1\t1\tF\tFR\t-8\t1978\t1650\t0\t2\t1\t1",
    ]
)


def test_parse_team_tsv_extracts_rows():
    parsed = _parse_team_tsv(_TSV_SAMPLE)
    assert len(parsed) == 3
    assert list(parsed.columns) == [
        "date",
        "home_code",
        "away_code",
        "home_elo",
        "away_elo",
    ]


def test_extract_team_series_picks_correct_elo_column():
    parsed = _parse_team_tsv(_TSV_SAMPLE)
    series = _extract_team_series("Brazil", parsed)

    assert list(series.columns) == ["team", "date", "elo"]
    assert (series["team"] == "Brazil").all()
    # Ordenado por data; usa col 11 quando fora (JP-BR) e col 10 quando casa.
    assert series.iloc[0]["elo"] == 1978  # vs Japan (fora)
    assert series.iloc[1]["elo"] == 1986  # vs Senegal (casa)
    assert series.iloc[2]["elo"] == 1978  # vs Tunisia (casa)


def test_extract_team_series_empty_input():
    out = _extract_team_series("Brazil", pd.DataFrame())
    assert out.empty
    assert list(out.columns) == ["team", "date", "elo"]


def test_get_elo_at_date_as_of_lookup():
    df = pd.DataFrame(
        {
            "team": ["Brazil"] * 3,
            "date": pd.to_datetime(["2025-01-01", "2025-06-01", "2025-11-01"]),
            "elo": [1900, 1950, 1980],
        }
    )
    # Data exata.
    assert get_elo_at_date(df, "Brazil", "2025-06-01") == 1950
    # Entre publicacoes -> usa a anterior.
    assert get_elo_at_date(df, "Brazil", dt.date(2025, 8, 15)) == 1950
    # Antes do primeiro registro -> usa o primeiro disponivel.
    assert get_elo_at_date(df, "Brazil", "2020-01-01") == 1900


def test_get_elo_at_date_unknown_team_raises():
    df = pd.DataFrame({"team": ["Brazil"], "date": pd.to_datetime(["2025-01-01"]), "elo": [1900]})
    with pytest.raises(KeyError):
        get_elo_at_date(df, "Narnia", "2025-01-01")


# --------------------------------------------------------------------------- #
# fifa_rankings
# --------------------------------------------------------------------------- #
def test_date_entry_regex_parses_embedded_pairs():
    html = '...{"id":"id14870","iso":"2025-09-18T00:00:00"}...{"id":"id14800","iso":"2025-07-10T00"}'
    pairs = _DATE_ENTRY_RE.findall(html)
    assert pairs == [("id14870", "2025-09-18"), ("id14800", "2025-07-10")]


def test_select_date_ids_picks_last_publication_per_month():
    dates_df = pd.DataFrame(
        {
            "date_id": ["a", "b", "c"],
            "date": pd.to_datetime(["2025-04-03", "2025-04-30", "2025-07-10"]),
        }
    )
    selected = _select_date_ids(dates_df, ["2025-04"])
    assert list(selected["date_id"]) == ["b"]  # ultima publicacao de abril


def test_select_date_ids_none_returns_all():
    dates_df = pd.DataFrame({"date_id": ["a"], "date": pd.to_datetime(["2025-04-03"])})
    out = _select_date_ids(dates_df, None)
    assert len(out) == 1


# --------------------------------------------------------------------------- #
# transfermarkt
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,expected",
    [
        ("1.20bn €", 1_200_000_000),
        ("950.50m €", 950_500_000),
        ("12.30k €", 12_300),
        ("500 €", 500.0),
        ("", None),
        ("-", None),
    ],
)
def test_parse_market_value(text, expected):
    assert parse_market_value(text) == expected
