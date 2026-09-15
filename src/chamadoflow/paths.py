"""Caminhos persistentes para execução pelo código-fonte ou pelo aplicativo portátil."""

import sys
from pathlib import Path


def diretorio_app():
    """Retorna a pasta do projeto ou a pasta que contém o executável portátil."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[2]


def caminho_app(*partes):
    """Monta um caminho relativo à pasta persistente do aplicativo."""

    return diretorio_app().joinpath(*partes)
