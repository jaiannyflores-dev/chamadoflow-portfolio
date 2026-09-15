import re

from chamadoflow.versao import NOME_APP, VERSAO, nome_completo_app


def test_versao_segue_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSAO)


def test_nome_completo_inclui_nome_e_versao():
    assert nome_completo_app() == f"{NOME_APP} v{VERSAO}"
