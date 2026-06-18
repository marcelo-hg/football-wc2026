"""Configuracao de logging padronizada para todo o projeto.

Nivel padrao: INFO. Pode ser elevado para DEBUG exportando ``LOGLEVEL=DEBUG``.
"""

from __future__ import annotations

import logging
import os

_CONFIGURED = False
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _configure_root() -> None:
    """Configura o handler raiz uma unica vez por processo."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.environ.get("LOGLEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt=_FORMAT, datefmt=_DATEFMT))

    root = logging.getLogger()
    root.setLevel(level)
    # Evita handlers duplicados em re-imports / execucoes interativas.
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado com formatacao padronizada.

    Args:
        name: nome do logger, normalmente ``__name__`` do modulo chamador.
    """
    _configure_root()
    return logging.getLogger(name)
