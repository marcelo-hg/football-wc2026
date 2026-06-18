# Módulo `features/`

Transforma os CSVs brutos de `data/raw/` em dois datasets processados em
`data/processed/`:

| Saída | Conteúdo |
|---|---|
| `matches_features.csv` | um registro por partida, com Elo/FIFA/mercado de cada lado, diferenças, pesos e alvo `result` |
| `team_strengths.csv` | força de ataque/defesa estimada por seleção |

## Uso

```bash
python cli/features.py --config configs/data.yaml
# ou, programaticamente:
```
```python
from src.features import build_match_dataset, compute_attack_defense_strength
```

## Colunas de `matches_features.csv`

`date, home_team, away_team, home_goals, away_goals, home_elo, away_elo, elo_diff,
home_fifa_rank, away_fifa_rank, rank_diff, home_market_value, away_market_value,
market_diff, competition_weight, is_neutral, result` (+ `competition`, `time_weight`).

## Decisões de design

- **Junção temporal (as-of).** Elo e ranking FIFA são unidos por *as-of join*
  (`merge_asof`, direção `backward`): cada partida recebe o valor mais recente
  **até** a data do jogo, sem vazamento de informação futura. As fontes são
  **opcionais** — se um CSV não existir (ex.: `market_values.csv` com o
  Transfermarkt desabilitado), as colunas correspondentes ficam `NaN`.
- **Valor de mercado.** Usa o registro mais recente por seleção para todas as
  partidas (o valor é essencialmente um instantâneo; serve de proxy de qualidade).
- **Força de ataque/defesa.** Média de gols marcados/sofridos (ponderada por
  decaimento temporal) normalizada pela média global → `attack > 1` é ataque
  acima da média; `defense < 1` é defesa acima da média.
- **Mando de campo** (`compute_home_advantage`). Estimado como
  `ln(média_gols_casa / média_gols_fora)` em jogos não-neutros — valor aditivo na
  escala de log-ataque, consistente com o `gamma` do Dixon-Coles.
- **Pesos.** `time_weight` decai exponencialmente (meia-vida configurável em
  `configs/data.yaml → features.time_decay_half_life_days`); `competition_weight`
  vem de `competition_weights`, com classificação tolerante a variações de nome
  (ex.: `"FIFA World Cup qualification" → Qualifiers`, `"Copa América" → Copa America`).

## Testes

```bash
pytest tests/unit/test_features.py
```

Inclui um teste de regressão (`..._asof_alignment_regression`) que garante que
cada seleção recebe o **seu** Elo após o `merge_asof` (uma versão anterior
embaralhava os valores por reatribuição posicional).
