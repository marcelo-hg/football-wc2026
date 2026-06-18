"""Modulo de engenharia de features para o worldcup2026-predictor.

Transforma os dados brutos coletados em ``data/raw/`` num dataset por partida
pronto para modelagem (``data/processed/matches_features.csv``) e numa tabela de
forca de ataque/defesa por selecao (``data/processed/team_strengths.csv``).

Submodulos:
    * weight_decay    -> pesos temporais e por competicao
    * home_advantage  -> fator de mando de campo e deteccao de campo neutro
    * team_features   -> forca de ataque/defesa e forma recente
    * match_features  -> juncao das fontes em um dataset por partida
    * pipeline        -> orquestracao (run_feature_pipeline)
"""

from src.features.home_advantage import compute_home_advantage, is_neutral_venue
from src.features.match_features import build_match_dataset, encode_result
from src.features.team_features import compute_attack_defense_strength, compute_recent_form
from src.features.weight_decay import apply_competition_weights, compute_time_weights

__all__ = [
    "compute_time_weights",
    "apply_competition_weights",
    "compute_home_advantage",
    "is_neutral_venue",
    "compute_attack_defense_strength",
    "compute_recent_form",
    "build_match_dataset",
    "encode_result",
]
