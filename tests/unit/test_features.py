"""Testes unitarios do modulo de features (logica pura, sem acesso a rede)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.home_advantage import compute_home_advantage, is_neutral_venue
from src.features.match_features import build_match_dataset, encode_result
from src.features.team_features import compute_attack_defense_strength, compute_recent_form
from src.features.weight_decay import (
    apply_competition_weights,
    classify_competition,
    compute_time_weights,
)


# --------------------------------------------------------------------------- #
# weight_decay
# --------------------------------------------------------------------------- #
def test_compute_time_weights_half_life():
    dates = pd.Series(pd.to_datetime(["2024-01-01", "2025-01-01"]))  # 366 dias de diferenca
    w = compute_time_weights(dates, half_life_days=366)
    assert w.iloc[1] == pytest.approx(1.0)          # mais recente -> peso 1
    assert w.iloc[0] == pytest.approx(0.5, abs=0.01)  # ~1 meia-vida atras -> ~0.5


def test_compute_time_weights_rejects_nonpositive_half_life():
    with pytest.raises(ValueError):
        compute_time_weights(pd.Series(pd.to_datetime(["2025-01-01"])), half_life_days=0)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("FIFA World Cup", "FIFA World Cup"),
        ("FIFA World Cup qualification", "Qualifiers"),
        ("UEFA Euro qualification", "Qualifiers"),
        ("Copa América", "Copa America"),
        ("African Cup of Nations", "African Cup of Nations"),
        ("Friendly", "Friendly"),
        ("Kirin Cup", "Kirin Cup"),  # sem regra -> nome original
    ],
)
def test_classify_competition(name, expected):
    assert classify_competition(name) == expected


def test_apply_competition_weights_uses_map_and_default():
    df = pd.DataFrame({"competition": ["FIFA World Cup", "Friendly", "Kirin Cup"]})
    weight_map = {"FIFA World Cup": 1.0, "Friendly": 0.5}
    out = apply_competition_weights(df, weight_map, default=0.3)
    assert list(out["competition_weight"]) == [1.0, 0.5, 0.3]


# --------------------------------------------------------------------------- #
# home_advantage
# --------------------------------------------------------------------------- #
def test_is_neutral_venue_prefers_flag():
    assert is_neutral_venue("Friendly", pd.Series({"neutral": True})) is True
    assert is_neutral_venue("FIFA World Cup", pd.Series({"neutral": False})) is False


def test_is_neutral_venue_heuristic_fallback():
    # Sem coluna 'neutral': cai na heuristica por nome da competicao.
    assert is_neutral_venue("FIFA World Cup", pd.Series({"home_goals": 1})) is True
    assert is_neutral_venue("Friendly", pd.Series({"home_goals": 1})) is False


def test_compute_home_advantage_positive_when_home_scores_more():
    matches = pd.DataFrame(
        {
            "home_goals": [2, 3, 1, 2],
            "away_goals": [1, 1, 0, 1],
            "neutral": [False, False, False, False],
        }
    )
    gamma = compute_home_advantage(matches)
    assert gamma > 0  # mandantes marcam mais -> vantagem positiva


def test_compute_home_advantage_excludes_neutral():
    matches = pd.DataFrame(
        {"home_goals": [5, 1], "away_goals": [0, 1], "neutral": [True, False]}
    )
    # So a 2a partida (nao-neutra, 1x1) conta -> razao 1 -> gamma 0.
    assert compute_home_advantage(matches) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# team_features
# --------------------------------------------------------------------------- #
def _toy_matches():
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"]),
            "home_team": ["A", "B", "A"],
            "away_team": ["B", "A", "B"],
            "home_goals": [3, 0, 2],
            "away_goals": [0, 1, 2],
        }
    )


def test_attack_defense_strength_shape_and_normalization():
    out = compute_attack_defense_strength(_toy_matches())
    assert set(out["team"]) == {"A", "B"}
    assert {"attack_strength", "defense_strength", "matches_played"} <= set(out.columns)
    # A media global das forcas de ataque, ponderada por jogos, ~1.0.
    assert out["attack_strength"].mean() == pytest.approx(1.0, abs=0.3)


def test_attack_defense_strength_team_filter():
    out = compute_attack_defense_strength(_toy_matches(), teams=["A"])
    assert list(out["team"]) == ["A"]


def test_compute_recent_form_points_per_game():
    matches = _toy_matches()
    # A: venceu (3x0), perdeu (B 0x1 A -> A marcou 1, sofreu 0 -> A venceu!), ...
    # Recalcular do ponto de vista de A:
    #  2025-01-01 A 3x0 B -> V (3)
    #  2025-02-01 B 0x1 A -> A venceu (3)
    #  2025-03-01 A 2x2 B -> E (1)
    form_a = compute_recent_form(matches, "A", n_games=5)
    assert form_a == pytest.approx((3 + 3 + 1) / 3)


def test_compute_recent_form_unknown_team_is_nan():
    assert np.isnan(compute_recent_form(_toy_matches(), "Z"))


# --------------------------------------------------------------------------- #
# match_features
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "hg,ag,expected", [(2, 1, "W"), (1, 1, "D"), (0, 3, "L")]
)
def test_encode_result(hg, ag, expected):
    assert encode_result(hg, ag) == expected


def test_build_match_dataset_joins_and_diffs():
    matches = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-06-01"]),
            "home_team": ["A"],
            "away_team": ["B"],
            "home_goals": [2],
            "away_goals": [0],
            "competition": ["FIFA World Cup"],
            "neutral": [False],
        }
    )
    elo = pd.DataFrame(
        {
            "team": ["A", "B"],
            "date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
            "elo": [2000, 1800],
        }
    )
    fifa = pd.DataFrame(
        {
            "team": ["A", "B"],
            "date": pd.to_datetime(["2025-05-01", "2025-05-01"]),
            "rank": [1, 10],
            "points": [1900.0, 1700.0],
        }
    )
    out = build_match_dataset(
        matches, elo=elo, fifa=fifa, mkt=None,
        competition_weights={"FIFA World Cup": 1.0},
    )
    row = out.iloc[0]
    assert row["home_elo"] == 2000 and row["away_elo"] == 1800
    assert row["elo_diff"] == 200
    assert row["rank_diff"] == 1 - 10
    assert row["competition_weight"] == 1.0
    assert row["result"] == "W"
    assert bool(row["is_neutral"]) is False
    # Sem fonte de mercado -> colunas NaN.
    assert np.isnan(row["home_market_value"])


def test_build_match_dataset_asof_alignment_regression():
    """Garante que cada selecao recebe o SEU Elo (as-of), sem desalinhamento.

    Regressao: uma versao anterior reatribuia os valores por posicao apos o
    merge_asof (que reordena por data), embaralhando Elo entre selecoes.
    """
    matches = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-03-01", "2025-03-01", "2025-04-01"]),
            "home_team": ["A", "C", "B"],
            "away_team": ["B", "D", "A"],
            "home_goals": [1, 2, 0],
            "away_goals": [0, 2, 1],
            "competition": ["Friendly"] * 3,
            "neutral": [False, False, False],
        }
    )
    elo = pd.DataFrame(
        {
            "team": ["A", "B", "C", "D"],
            "date": pd.to_datetime(["2025-01-01"] * 4),
            "elo": [2000, 1500, 1800, 1700],
        }
    )
    out = build_match_dataset(matches, elo=elo).set_index(["home_team", "away_team"])
    assert out.loc[("A", "B"), "home_elo"] == 2000
    assert out.loc[("A", "B"), "away_elo"] == 1500
    assert out.loc[("C", "D"), "home_elo"] == 1800
    assert out.loc[("B", "A"), "home_elo"] == 1500
    assert out.loc[("B", "A"), "away_elo"] == 2000


def test_build_match_dataset_without_optional_sources():
    matches = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-06-01"]),
            "home_team": ["A"],
            "away_team": ["B"],
            "home_goals": [1],
            "away_goals": [1],
            "competition": ["Friendly"],
            "neutral": [True],
        }
    )
    out = build_match_dataset(matches)  # nenhuma fonte extra
    row = out.iloc[0]
    assert np.isnan(row["home_elo"]) and np.isnan(row["elo_diff"])
    assert row["result"] == "D"
    assert bool(row["is_neutral"]) is True
