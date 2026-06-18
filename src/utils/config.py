"""Carregamento de configuracoes YAML/JSON do projeto."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    """Carrega um arquivo YAML e retorna como dicionario.

    Args:
        path: caminho para o arquivo ``.yaml``/``.yml``.

    Raises:
        FileNotFoundError: se o arquivo nao existir.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo de configuracao nao encontrado: {p}")
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuracao em {p} nao e um mapeamento YAML valido.")
    return data


def load_json(path: str | Path) -> dict[str, Any]:
    """Carrega um arquivo JSON e retorna como dicionario.

    Usado, por exemplo, para o mapa de nomes de selecoes. Retorna ``{}`` se o
    caminho for vazio/None ou o arquivo nao existir.
    """
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def get_model_config(model_name: str, path: str | Path = "configs/models.yaml") -> dict[str, Any]:
    """Retorna a configuracao especifica de um modelo de ``configs/models.yaml``.

    Args:
        model_name: chave do modelo (ex: ``"dixon_coles"``).
        path: caminho do arquivo de configuracao de modelos.
    """
    cfg = load_config(path)
    if model_name not in cfg:
        raise KeyError(f"Modelo '{model_name}' nao encontrado em {path}.")
    return cfg[model_name]
