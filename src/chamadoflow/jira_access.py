"""Exemplo genérico de triagem para solicitações de acesso ao Jira."""

import re
import unicodedata


FILA_ADMINISTRACAO_USUARIOS = "administracao_usuarios"

ACESSOS_JIRA = {
    "Service Management": {
        "grupo": "G_JIRA_SERVICE_MANAGEMENT",
        "aprovador": "Aprovador de Service Management",
    },
    "Confluence": {
        "grupo": "G_JIRA_CONFLUENCE",
        "aprovador": "Aprovador de Confluence",
    },
    "Software": {
        "grupo": "G_JIRA_SOFTWARE",
        "aprovador": "Aprovador de Software",
    },
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return " ".join(texto.casefold().split())


def _valores_campo(chamado, nome):
    return (chamado.get("campos_customizados", {}) or {}).get(nome, []) or []


def _texto_do_chamado(chamado):
    partes = [
        chamado.get("resumo", ""),
        chamado.get("descricao", ""),
        chamado.get("justificativa", ""),
        *_valores_campo(chamado, "Justificativa"),
        *_valores_campo(chamado, "Cargo/Função"),
    ]
    return _normalizar(" ".join(str(parte) for parte in partes if parte))


def _tipo_de_acesso(texto):
    if any(termo in texto for termo in ("base de conhecimento", "confluence", " wiki", "kb ")):
        return "Confluence"
    if any(termo in texto for termo in ("projeto", "projetos", "iniciativa", "iniciativas")):
        return "Software"
    if any(termo in texto for termo in (
        "service management", "time solucionador", "manipulacao de chamado",
        "manipulacao de chamados", "atendimento de chamados", "incidente",
    )):
        return "Service Management"
    return "Não identificado"


def analisar_solicitacao_acesso_jira(chamado):
    """Sugere a captura de acesso Jira ainda sem aprovação registrada."""

    texto = _texto_do_chamado(chamado)
    fila = _normalizar(chamado.get("fila_origem"))
    resposta = _normalizar(" ".join(_valores_campo(chamado, "acesso ao JIRA?")))
    solicita_acesso = resposta == "sim" or bool(re.search(
        r"\b(acesso|liberacao|permissao)\b.*\bjira\b", texto
    ))
    aprovacao_solicitada = bool(chamado.get("aprovador_nome")) or (
        _normalizar(chamado.get("status")) == "aguardando aprovacao"
    )
    precisa_triagem = (
        FILA_ADMINISTRACAO_USUARIOS in fila
        and not str(chamado.get("responsavel") or "").strip()
        and solicita_acesso
        and not aprovacao_solicitada
    )
    tipo = _tipo_de_acesso(texto) if precisa_triagem else ""
    dados = ACESSOS_JIRA.get(tipo)
    grupo = dados["grupo"] if dados else ""
    aprovador = dados["aprovador"] if dados else ""
    acao = ""
    if dados:
        acao = f"Capturar chamado e solicitar aprovação a {aprovador} para liberar o grupo {grupo}."
    elif precisa_triagem:
        acao = "Capturar chamado e validar o tipo de Jira, o grupo e o aprovador."

    return {
        "triagem_acesso_jira": precisa_triagem,
        "tipo_jira_sugerido": tipo,
        "grupo_jira_sugerido": grupo,
        "aprovador_jira_sugerido": aprovador,
        "acao_acesso_jira": acao,
    }
