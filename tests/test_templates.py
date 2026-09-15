from unittest.mock import patch

from chamadoflow.templates import (
    MODELOS_ATUALIZACAO_JIRA,
    gerar_atualizacao_jira,
    gerar_mensagem_contato,
    gerar_mensagem_strike,
    gerar_mensagem_strike_manual,
    limpar_strike_resumo,
    primeiro_nome_completo,
    sugerir_objetivo,
)


def test_gerar_atualizacao_jira_retorna_modelo_escolhido():
    tipo = "Atendimento previsto"

    assert gerar_atualizacao_jira(tipo) == (
        "Em contato com a área responsável, fui informada de que o atendimento "
        "está previsto para o dia [data prevista]."
    )


def test_gerar_atualizacao_jira_retorna_vazio_para_tipo_desconhecido():
    assert gerar_atualizacao_jira("Tipo inexistente") == ""
    assert len(MODELOS_ATUALIZACAO_JIRA) == 13


def test_limpar_strike_resumo_remove_apenas_o_marcador():
    assert limpar_strike_resumo(" {STRIKE-2}  Falha no acesso ") == "Falha no acesso"


def test_primeiro_nome_completo_remove_identificador_corporativo():
    chamado = {"solicitante": "Ana Silva (USR-12345)"}

    assert primeiro_nome_completo(chamado) == "Ana Silva"


def test_sugerir_objetivo_para_problema_de_acesso():
    chamado = {"resumo": "Erro de acesso ao sistema"}
    analise = {"situacao": "Aguardando demandante"}

    assert sugerir_objetivo(chamado, analise) == (
        "Verificar se o problema informado no chamado ainda persiste."
    )


def test_mensagem_ao_aprovador_mantem_texto_generico():
    chamado = {
        "chave": "SERV-1",
        "resumo": "Solicitação de acesso",
        "aprovador_nome": "Maria Gestora",
        "solicitante_nome": "Ana Solicitante",
        "time_solucionador": "Gestão de acessos",
    }
    analise = {"quem_precisa_agir": "Aprovador"}

    with patch("chamadoflow.templates._saudacao", return_value="Bom dia"):
        mensagem = gerar_mensagem_contato(chamado, analise)

    assert "Falo em nome da Central de Serviços." in mensagem


def test_gerar_mensagem_strike_retorna_none_sem_elegibilidade():
    chamado = {"chave": "SERV-1", "solicitante": "Ana Silva"}
    analise = {"situacao": "Aguardando demandante"}
    elegibilidade = {"elegivel_strike": False, "proximo_strike": 1}

    assert gerar_mensagem_strike(chamado, analise, elegibilidade) is None


def test_gerar_mensagem_strike_informa_numero_do_strike():
    chamado = {"chave": "SERV-1", "solicitante": "Ana Silva"}
    analise = {"situacao": "Aguardando demandante"}
    elegibilidade = {"elegivel_strike": True, "proximo_strike": 2}

    mensagem = gerar_mensagem_strike(
        chamado,
        analise,
        elegibilidade,
        objetivo="confirmar se o problema persiste",
    )

    assert mensagem is not None
    assert "{Strike 2}" in mensagem
    assert "SERV-1" in mensagem


def test_gerar_mensagem_strike_manual_independe_da_elegibilidade():
    chamado = {"chave": "SERV-1", "solicitante": "Ana Silva"}
    analise = {"situacao": "Aguardando demandante"}

    mensagem = gerar_mensagem_strike_manual(
        chamado,
        analise,
        2,
        objetivo="confirmar se o problema persiste",
    )

    assert mensagem is not None
    assert "{Strike 2}" in mensagem


def test_gerar_mensagem_strike_manual_rejeita_numero_invalido():
    chamado = {"chave": "SERV-1", "solicitante": "Ana Silva"}

    assert gerar_mensagem_strike_manual(chamado, {}, 4) is None
