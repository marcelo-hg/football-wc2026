"""Orquestracao dos scrapers e validacao dos dados brutos.

Le ``configs/data.yaml`` (passado como dict), executa as fontes habilitadas em
sequencia e grava os CSVs em ``data/raw/``. Cada fonte e isolada: uma falha e
registrada no log mas nao interrompe as demais.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.scraping.elo_ratings import fetch_elo_ratings
from src.scraping.fifa_rankings import fetch_fifa_rankings
from src.scraping.football_data import fetch_international_matches, normalize_team_names
from src.scraping.transfermarkt import fetch_market_values
from src.utils.config import load_json
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Nomes de arquivo de saida por fonte (relativos a output_dir).
OUTPUT_FILES = {
    "football_data": "matches.csv",
    "elo_ratings": "elo_ratings.csv",
    "fifa_rankings": "fifa_rankings.csv",
    "transfermarkt": "market_values.csv",
}


def _enabled(config: dict, source: str) -> bool:
    return bool(config.get("sources", {}).get(source, {}).get("enabled", False))


def _months_between(start_year: int, end_year: int) -> list[str]:
    """Gera lista de meses ``YYYY-MM`` no intervalo (inclusivo)."""
    return [
        f"{year:04d}-{month:02d}"
        for year in range(start_year, end_year + 1)
        for month in range(1, 13)
    ]


def run_all_scrapers(config: dict) -> None:
    """Orquestra todos os scrapers habilitados e salva os outputs em ``data/raw/``.

    Args:
        config: dicionario carregado de ``configs/data.yaml``.
    """
    sources = config.get("sources", {})
    output_dir = Path(config.get("output_dir", "data/raw/"))
    output_dir.mkdir(parents=True, exist_ok=True)

    mapping = load_json(config.get("team_name_mapping", ""))
    if mapping:
        logger.info("Mapa de nomes de selecoes carregado: %d entradas", len(mapping))

    counts: dict[str, int] = {}

    # 1) Resultados historicos (football-data / martj42).
    if _enabled(config, "football_data"):
        fd = sources["football_data"]
        try:
            matches = fetch_international_matches(
                start_year=int(fd.get("start_year", 2017)),
                end_year=int(fd.get("end_year", 2025)),
                include_friendlies=bool(fd.get("include_friendlies", True)),
            )
            matches = normalize_team_names(matches, mapping)
            path = output_dir / OUTPUT_FILES["football_data"]
            matches.to_csv(path, index=False)
            counts["football_data"] = len(matches)
            logger.info("[football_data] %d partidas -> %s", len(matches), path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[football_data] falhou: %s", exc)

    # Determina o conjunto de selecoes a partir das partidas (para Elo).
    teams = _resolve_teams(config, output_dir)

    # 2) Ratings Elo.
    if _enabled(config, "elo_ratings"):
        try:
            overrides = sources["elo_ratings"].get("url_overrides", {})
            elo = fetch_elo_ratings(teams, url_overrides=overrides)
            path = output_dir / OUTPUT_FILES["elo_ratings"]
            elo.to_csv(path, index=False)
            counts["elo_ratings"] = len(elo)
            logger.info("[elo_ratings] %d registros -> %s", len(elo), path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[elo_ratings] falhou: %s", exc)

    # 3) Ranking FIFA.
    if _enabled(config, "fifa_rankings"):
        fr = sources["fifa_rankings"]
        try:
            months = fr.get("months")
            if not months and "start_year" in fr:
                months = _months_between(int(fr["start_year"]), int(fr.get("end_year", 2025)))
            fifa = fetch_fifa_rankings(months)
            path = output_dir / OUTPUT_FILES["fifa_rankings"]
            fifa.to_csv(path, index=False)
            counts["fifa_rankings"] = len(fifa)
            logger.info("[fifa_rankings] %d registros -> %s", len(fifa), path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[fifa_rankings] falhou: %s", exc)

    # 4) Valor de mercado (Transfermarkt).
    if _enabled(config, "transfermarkt"):
        tm = sources["transfermarkt"]
        try:
            mkt = fetch_market_values(
                year=int(tm.get("year", 2025)),
                max_pages=int(tm.get("max_pages", 10)),
            )
            mkt = normalize_team_names(mkt, mapping) if not mkt.empty else mkt
            path = output_dir / OUTPUT_FILES["transfermarkt"]
            mkt.to_csv(path, index=False)
            counts["transfermarkt"] = len(mkt)
            logger.info("[transfermarkt] %d registros -> %s", len(mkt), path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[transfermarkt] falhou: %s", exc)

    logger.info("Scraping concluido. Registros por fonte: %s", counts)


def _resolve_teams(config: dict, output_dir: Path) -> list[str]:
    """Determina a lista de selecoes para o scraping de Elo.

    Prioridade:
        1. lista explicita em ``sources.elo_ratings.teams`` na config;
        2. selecoes presentes em ``data/raw/matches.csv`` (se ja gerado).
    """
    explicit = config.get("sources", {}).get("elo_ratings", {}).get("teams")
    if explicit:
        return list(explicit)

    matches_path = output_dir / OUTPUT_FILES["football_data"]
    if matches_path.exists():
        df = pd.read_csv(matches_path)
        teams = pd.concat([df["home_team"], df["away_team"]]).dropna().unique().tolist()
        logger.info("Selecoes inferidas de matches.csv: %d", len(teams))
        return sorted(teams)

    logger.warning("Nenhuma selecao definida para Elo (sem teams na config nem matches.csv).")
    return []


def validate_raw_data(output_dir: str | Path = "data/raw/") -> dict:
    """Verifica integridade dos CSVs gerados.

    Para cada arquivo existente, calcula: numero de linhas, colunas, total de
    nulos, duplicatas e cobertura temporal (min/max de ``date``, quando houver).

    Returns:
        Dicionario ``{fonte: {estatisticas}}``.
    """
    output_dir = Path(output_dir)
    report: dict[str, dict] = {}

    for source, filename in OUTPUT_FILES.items():
        path = output_dir / filename
        if not path.exists():
            report[source] = {"status": "ausente", "path": str(path)}
            continue

        df = pd.read_csv(path)
        stats: dict = {
            "status": "ok" if len(df) else "vazio",
            "rows": int(len(df)),
            "columns": list(df.columns),
            "n_nulls": int(df.isna().sum().sum()),
            "n_duplicates": int(df.duplicated().sum()),
        }
        if "date" in df.columns and len(df):
            dates = pd.to_datetime(df["date"], errors="coerce")
            stats["date_min"] = str(dates.min().date()) if dates.notna().any() else None
            stats["date_max"] = str(dates.max().date()) if dates.notna().any() else None
        report[source] = stats
        logger.info("[validate] %s: %s", source, stats)

    return report
