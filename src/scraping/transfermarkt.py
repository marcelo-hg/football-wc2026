"""Coleta do valor de mercado dos elencos por selecao (Transfermarkt).

O Transfermarkt renderiza a tabela via JavaScript e aplica protecao anti-bot,
por isso usamos Playwright (navegador headless). O Playwright e uma dependencia
opcional: o modulo importa sem ele, mas :func:`fetch_market_values` falha com
uma mensagem acionavel se o pacote/navegador nao estiver instalado.

    pip install ".[transfermarkt]"
    playwright install chromium

Saida: ``[team, year, market_value_eur]``.
"""

from __future__ import annotations

import re

import pandas as pd

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Ranking de selecoes por valor de mercado (paginado).
BASE_URL = "https://www.transfermarkt.com/statistik/weltrangliste"

# Ex.: "1.20bn €", "950.50m €", "12.30k €"
_VALUE_RE = re.compile(r"([\d.,]+)\s*(bn|m|k)?\s*€", re.IGNORECASE)
_MULTIPLIER = {"bn": 1_000_000_000, "m": 1_000_000, "k": 1_000, None: 1.0}


def parse_market_value(text: str) -> float | None:
    """Converte um valor textual do Transfermarkt (ex.: ``"1.20bn €"``) em euros.

    Returns:
        Valor em euros (float) ou ``None`` se nao for possivel parsear.
    """
    if not text:
        return None
    match = _VALUE_RE.search(text.replace("\xa0", " "))
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    suffix = match.group(2)
    suffix = suffix.lower() if suffix else None
    return number * _MULTIPLIER[suffix]


def _require_playwright():
    """Importa o Playwright sob demanda, com erro acionavel se ausente."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depende de instalacao
        raise ImportError(
            "Playwright e necessario para o scraping do Transfermarkt. "
            "Instale com: pip install \".[transfermarkt]\" && playwright install chromium"
        ) from exc
    return sync_playwright


def fetch_market_values(
    year: int,
    *,
    max_pages: int = 10,
    headless: bool = True,
) -> pd.DataFrame:
    """Coleta o valor de mercado total do elenco por selecao via Playwright.

    Args:
        year: ano de referencia (apenas registrado na saida; o Transfermarkt
            expoe o valor corrente).
        max_pages: numero maximo de paginas do ranking a percorrer.
        headless: se ``True``, roda o navegador sem interface.

    Returns:
        DataFrame ``[team, year, market_value_eur]``.
    """
    sync_playwright = _require_playwright()
    rows: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        try:
            for page_num in range(1, max_pages + 1):
                url = f"{BASE_URL}?page={page_num}"
                logger.info("Transfermarkt: pagina %d -> %s", page_num, url)
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)

                table = page.query_selector("table.items")
                if table is None:
                    logger.info("Sem tabela na pagina %d; encerrando.", page_num)
                    break

                page_rows = _parse_table(table)
                if not page_rows:
                    break
                for team, value_text in page_rows:
                    rows.append(
                        {
                            "team": team,
                            "year": year,
                            "market_value_eur": parse_market_value(value_text),
                        }
                    )
        finally:
            browser.close()

    df = pd.DataFrame(rows)
    if df.empty:
        logger.warning("Nenhum valor de mercado coletado no Transfermarkt.")
        return pd.DataFrame(columns=["team", "year", "market_value_eur"])
    df = df.drop_duplicates("team").reset_index(drop=True)
    logger.info("Valores de mercado coletados: %d selecoes", len(df))
    return df


def _parse_table(table) -> list[tuple[str, str]]:
    """Extrai pares ``(selecao, valor_textual)`` de uma tabela ``table.items``."""
    results: list[tuple[str, str]] = []
    for tr in table.query_selector_all("tbody > tr"):
        name_el = tr.query_selector("td.hauptlink a") or tr.query_selector("td a img[title]")
        value_el = tr.query_selector("td.rechts")
        if name_el is None or value_el is None:
            continue
        team = (name_el.get_attribute("title") or name_el.inner_text()).strip()
        value_text = value_el.inner_text().strip()
        if team and value_text:
            results.append((team, value_text))
    return results
