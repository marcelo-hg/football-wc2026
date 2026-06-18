"""Configuracao compartilhada de testes."""

import sys
from pathlib import Path

# Garante que a raiz do projeto esteja importavel (src.*) sem instalacao.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "network: testes que exigem acesso a internet (fontes reais)."
    )
