"""Helpers de HTTP compartilhados pelos scrapers.

Centraliza User-Agent, timeout e politica de retry com backoff exponencial,
para que cada scraper nao precise reimplementar resiliencia de rede.
"""

from __future__ import annotations

import time

import requests

from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

DEFAULT_TIMEOUT = 30


def build_session() -> requests.Session:
    """Cria uma ``requests.Session`` com headers padrao do projeto."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def get(
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 3,
    backoff: float = 1.5,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    """GET com retry exponencial.

    Args:
        url: endereco a requisitar.
        session: sessao reaproveitavel; criada sob demanda se ``None``.
        timeout: timeout por tentativa, em segundos.
        retries: numero maximo de tentativas.
        backoff: fator multiplicativo de espera entre tentativas.
        headers: cabecalhos extras para esta requisicao.

    Raises:
        requests.RequestException: se todas as tentativas falharem.
    """
    sess = session or build_session()
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = sess.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:  # rede, status >= 400, etc.
            last_exc = exc
            wait = backoff ** attempt
            logger.warning(
                "GET falhou (tentativa %d/%d) em %s: %s — aguardando %.1fs",
                attempt,
                retries,
                url,
                exc,
                wait,
            )
            if attempt < retries:
                time.sleep(wait)
    assert last_exc is not None
    raise last_exc
