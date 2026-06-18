# Módulo `scraping/`

Coleta dos dados brutos usados pelo modelo preditivo da Copa 2026. Cada scraper é
isolado e grava um CSV em `data/raw/`. A orquestração e a validação ficam em
`pipeline.py`.

## Uso

```bash
# instala dependências do pacote (scraping + CLI)
pip install -e .

# coleta todas as fontes habilitadas em configs/data.yaml
python cli/scrape.py --config configs/data.yaml

# apenas valida os CSVs já existentes em data/raw/
python cli/scrape.py --config configs/data.yaml --validate-only
```

Programaticamente:

```python
from src.scraping import fetch_international_matches, fetch_elo_ratings, fetch_fifa_rankings

matches = fetch_international_matches(2017, 2025)            # [date, home_team, away_team, home_goals, away_goals, competition, neutral]
elo     = fetch_elo_ratings(["Brazil", "Argentina"])        # [team, date, elo]
fifa    = fetch_fifa_rankings(["2025-04", "2025-07"])       # [team, date, rank, points]
```

## Fontes

| Scraper | Fonte real | Saída (`data/raw/`) |
|---|---|---|
| `football_data.py` | `martj42/international_results` (GitHub, raw CSV) | `matches.csv` |
| `elo_ratings.py` | `eloratings.net/{Team}.tsv` | `elo_ratings.csv` |
| `fifa_rankings.py` | API `inside.fifa.com/api/ranking-overview` | `fifa_rankings.csv` |
| `transfermarkt.py` | `transfermarkt.com` via Playwright | `market_values.csv` |

### Desvio em relação ao plano: fonte de partidas

O plano aponta **football-data.co.uk** como fonte de resultados internacionais.
Na prática, aquela página (`internationals.php`) não expõe um CSV consolidado e
estável de partidas internacionais. Substituí pela base pública e mantida
[`martj42/international_results`](https://github.com/martj42/international_results),
que cobre resultados oficiais e amistosos desde 1872 e cujo esquema mapeia
diretamente nas colunas exigidas pelo plano (inclusive a flag `neutral` e os
jogos já agendados da Copa 2026). O parâmetro `url` de
`fetch_international_matches` permite trocar a fonte/mirror sem alterar o código.

### Mapeamento de Elo (`eloratings.net`)

O site renderiza via JavaScript, mas cada seleção expõe um TSV plano em
`eloratings.net/{Team}.tsv` (espaços → `_`, ex.: `United_States`). Cada linha é
uma partida; o Elo pós-jogo da seleção é a **coluna 10** quando ela é mandante e
a **coluna 11** quando é visitante. Seleções com grafia divergente podem ser
ajustadas via `sources.elo_ratings.url_overrides` no `configs/data.yaml`.

### Ranking FIFA

A lista de publicações (`dateId` → data) é extraída da página
`inside.fifa.com/fifa-world-ranking/men` e cada data é consultada na API JSON.
Sem `months`, coleta o histórico completo (centenas de requisições).

## Transfermarkt (opcional)

Requer Playwright, instalado à parte por causa do navegador headless:

```bash
pip install ".[transfermarkt]"
playwright install chromium
```

Está **desabilitado por padrão** em `configs/data.yaml`
(`sources.transfermarkt.enabled: false`).

## Testes

```bash
pytest tests/unit/test_scraping.py     # lógica pura, sem rede
```
