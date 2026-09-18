from chamadoflow.jira_access import analisar_solicitacao_acesso_jira
from chamadoflow.rules import analisar_chamado_operacional


def _chamado(**sobrescritas):
    chamado = {
        "fila_origem": "Administracao_Usuarios",
        "responsavel": "",
        "resumo": "Solicitação de acesso ao Jira",
        "descricao": "",
        "justificativa": "",
        "status": "Aberto",
        "campos_customizados": {"acesso ao JIRA?": ["Sim"]},
        "comentarios": [],
    }
    chamado.update(sobrescritas)
    return chamado


def test_sugere_grupo_e_aprovador_para_confluence():
    analise = analisar_solicitacao_acesso_jira(_chamado(
        descricao="Preciso consultar a base de conhecimento no Confluence."
    ))

    assert analise["triagem_acesso_jira"] is True
    assert analise["grupo_jira_sugerido"] == "G_JIRA_CONFLUENCE"
    assert analise["aprovador_jira_sugerido"] == "Aprovador de Confluence"


def test_nao_sugere_quando_o_chamado_ja_tem_responsavel():
    analise = analisar_solicitacao_acesso_jira(_chamado(
        responsavel="Analista",
        descricao="Acesso ao Confluence",
    ))

    assert analise["triagem_acesso_jira"] is False


def test_analise_operacional_destaca_captura_do_chamado():
    resultado = analisar_chamado_operacional(_chamado(
        chave="DEMO-1",
        descricao="Acesso para manipulação de chamados.",
    ))

    assert resultado["situacao"] == "Acesso Jira sem aprovação"
    assert resultado["prioridade"] == "Alta"
