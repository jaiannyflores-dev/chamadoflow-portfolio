import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo


# ============================================================
# UTILITÁRIOS
# ============================================================

def limpar_texto(valor):
    if valor is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(valor)
    ).strip()

def limpar_strike_resumo(resumo):
    """
    Remove marcadores de Strike do resumo apenas para
    exibição nas mensagens.

    Exemplos:
    {STRIKE-2} Solicitação...
    {STRIKE 1} Autenticação falhou
    {Strike 2} ...
    """

    resumo = limpar_texto(resumo)

    resumo = re.sub(
        r"\{\s*strike\s*[-:]?\s*[123]\s*\}",
        "",
        resumo,
        flags=re.IGNORECASE,
    )

    return limpar_texto(resumo)

def primeiro_nome_completo(chamado):
    """
    Obtém o nome completo do cliente/demandante.

    Tenta primeiro campos estruturados do parser e,
    como fallback, o reporter.
    """

    candidatos = [
        chamado.get("solicitante"),
        chamado.get("cliente"),
        chamado.get("reporter"),
        chamado.get("demandante"),
    ]

    for valor in candidatos:
        valor = limpar_texto(valor)

        if valor:
            # Remove identificador corporativo no final, quando existir.
            valor = re.sub(
                r"\s*\([A-Z]{2,10}-\d+\)\s*$",
                "",
                valor
            )

            return valor.strip()

    return "Cliente não identificado"


# ============================================================
# OBJETIVO SUGERIDO
# ============================================================

def sugerir_objetivo(chamado, analise):
    resumo = limpar_texto(
        chamado.get("resumo")
    )

    situacao = analise.get(
        "situacao",
        ""
    )

    # --------------------------------------------------------
    # Validação com demandante
    # --------------------------------------------------------

    if situacao == "Aguardando demandante":

        resumo_lower = resumo.lower()

        if any(
            termo in resumo_lower
            for termo in [
                "falha",
                "erro",
                "não funciona",
                "nao funciona",
                "não consegue",
                "nao consegue",
                "problema",
                "instabilidade",
            ]
        ):
            return (
                "Verificar se o problema informado "
                "no chamado ainda persiste."
            )

        return (
            "Verificar com o demandante se a "
            "solicitação ainda necessita de atendimento."
        )

    # --------------------------------------------------------
    # Aprovação
    # --------------------------------------------------------

    if situacao == "Aguardando aprovação":

        return (
            "Solicitar a aprovação necessária "
            "para continuidade do atendimento."
        )

    # --------------------------------------------------------
    # Chamado relacionado
    # --------------------------------------------------------

    if situacao == "Aguardando chamado relacionado":

        return (
            "Acompanhar a conclusão do chamado "
            "relacionado para continuidade do atendimento."
        )

    # --------------------------------------------------------
    # Analista / técnico
    # --------------------------------------------------------

    if situacao == "Aguardando analista/técnico":

        return (
            "Solicitar retorno do analista ou técnico "
            "responsável para continuidade do atendimento."
        )

    # --------------------------------------------------------
    # Responsável
    # --------------------------------------------------------

    if situacao in {
        "Responsável precisa retornar",
        "Cobrar atualização do técnico",
        "Sem atualização identificada",
    }:

        return (
            "Solicitar atualização do responsável "
            "sobre o andamento do chamado."
        )

    # --------------------------------------------------------
    # HelpDesk precisa continuar
    # --------------------------------------------------------

    if situacao in {
        "HelpDesk precisa continuar",
        "Informação recebida - continuar atendimento",
        "Aprovação recebida - cobrar andamento",
    }:

        return (
            "Dar continuidade ao atendimento "
            "com base nas informações recebidas."
        )

    return (
        "Validar a situação atual do chamado "
        "para definição da próxima ação."
    )


# ============================================================
# MENSAGEM DE CONTATO
# ============================================================

def _saudacao():
    """Retorna a saudação de acordo com o horário de Brasília."""
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

    if agora.hour < 12:
        return "Bom dia"

    if agora.hour < 18:
        return "Boa tarde"

    return "Boa noite"


def _formatar_data_criacao(chamado):
    """Formata a data de criação do Jira como DD/MM/AAAA."""
    valor = limpar_texto(chamado.get("criado"))

    if not valor:
        return "Data não identificada"

    try:
        data = parsedate_to_datetime(valor)
        return data.strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return valor


def _dias_em_aberto(chamado):
    """Calcula os dias corridos desde a criação do chamado."""
    valor = limpar_texto(chamado.get("criado"))

    if not valor:
        return None

    try:
        criado = parsedate_to_datetime(valor)
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

        if criado.tzinfo is None:
            criado = criado.replace(
                tzinfo=ZoneInfo("America/Sao_Paulo")
            )

        return max(
            0,
            (agora.date() - criado.astimezone(
                ZoneInfo("America/Sao_Paulo")
            ).date()).days
        )
    except (TypeError, ValueError):
        return None


def _nome_aprovador(chamado):
    return limpar_texto(
        chamado.get("aprovador_nome")
    )


def _nome_solicitante(chamado):
    valor = limpar_texto(
        chamado.get("solicitante_nome")
    )

    if valor:
        return valor

    return primeiro_nome_completo(chamado)


def _apresentacao_atendimento():
    """Texto neutro para uma distribuição reutilizável do aplicativo."""

    return "Falo em nome da Central de Serviços."


def _paragrafo_strike_contato(analise):
    """
    Inclui o aviso somente quando o motor autorizou
    a aplicação de um Strike neste contato.
    """
    if not analise.get("elegivel_strike", False):
        return ""

    numero = analise.get("proximo_strike")

    if numero not in {1, 2, 3}:
        return ""

    return (
        f"\n\nEste contato corresponde ao {numero}º Strike. "
        f"Caso não tenhamos retorno até o 3º Strike, "
        f"o chamado poderá ser encerrado por falta de manifestação."
    )


def gerar_mensagem_contato(
    chamado,
    analise,
    objetivo=None
):
    chave = limpar_texto(
        chamado.get("chave")
    )

    resumo = limpar_strike_resumo(
        chamado.get("resumo")
    )

    situacao = limpar_texto(
        analise.get("situacao")
    )

    quem = limpar_texto(
        analise.get("quem_precisa_agir")
    )

    if not objetivo:
        objetivo = sugerir_objetivo(
            chamado,
            analise
        )

    objetivo = limpar_texto(objetivo)

    saudacao = _saudacao()
    data_criacao = _formatar_data_criacao(chamado)
    solicitante = _nome_solicitante(chamado)
    aprovador = _nome_aprovador(chamado)
    aviso_strike = _paragrafo_strike_contato(analise)
    # --------------------------------------------------------
    # APROVADOR
    # --------------------------------------------------------

    if quem == "Aprovador":
        destinatario = aprovador or "Aprovador"

        linha_solicitante = ""

        if solicitante and solicitante != "Cliente não identificado":
            linha_solicitante = (
                f"\nSolicitação para: {solicitante}"
            )

        return (
            f"{saudacao}, {destinatario}! Tudo bem?\n\n"
            f"{_apresentacao_atendimento()}\n\n"
            f"Identifiquei que o chamado abaixo está aguardando "
            f"sua avaliação para que o atendimento possa prosseguir:\n\n"
            f"{chave} – {resumo}"
            f"{linha_solicitante}\n"
            f"(Data de criação: {data_criacao})\n\n"
            f"Para darmos continuidade à tratativa, precisamos "
            f"da sua avaliação informando se a solicitação pode "
            f"ou não ser atendida.\n\n"
            f"Assim que possível, peço a gentileza de registrar "
            f"sua decisão para que possamos prosseguir com o atendimento."
            f"{aviso_strike}\n\n"
            f"Fico no aguardo do seu retorno.\n\n"
            f"Obrigada pela atenção!"
        )

    # --------------------------------------------------------
    # DEMANDANTE / SOLICITANTE
    # --------------------------------------------------------

    if quem == "Demandante":
        destinatario = solicitante
        resumo_lower = resumo.lower()

        termos_problema = [
            "falha",
            "erro",
            "não funciona",
            "nao funciona",
            "não consegue",
            "nao consegue",
            "problema",
            "instabilidade",
            "autenticação",
            "autenticacao",
            "senha",
            "acesso",
        ]

        eh_problema = any(
            termo in resumo_lower
            for termo in termos_problema
        )

        if eh_problema:
            corpo = (
                f"Gostaria de verificar se o problema informado "
                f"no chamado ainda persiste.\n\n"
                f"Caso o problema tenha sido resolvido e o serviço "
                f"esteja funcionando normalmente, peço a gentileza "
                f"de confirmar para que possamos prosseguir com o "
                f"encerramento do chamado.\n\n"
                f"Se o problema ainda estiver ocorrendo, poderia "
                f"me encaminhar uma imagem da tela com o erro "
                f"apresentado e informar o melhor horário para que "
                f"um técnico entre em contato e dê continuidade "
                f"ao atendimento?"
            )
        else:
            corpo = (
                f"Gostaria de verificar se a solicitação ainda "
                f"necessita de atendimento.\n\n"
                f"Caso a solicitação já tenha sido atendida, peço "
                f"a gentileza de confirmar para que possamos "
                f"prosseguir com o encerramento do chamado.\n\n"
                f"Se ainda for necessário dar continuidade, poderia "
                f"me informar o que permanece pendente e o melhor "
                f"horário para contato?"
            )

        return (
            f"{saudacao}, {destinatario}! Tudo bem?\n\n"
            f"{_apresentacao_atendimento()}\n\n"
            f"Estou acompanhando o chamado abaixo:\n\n"
            f"{chave} – {resumo}\n"
            f"(Data de criação: {data_criacao})\n\n"
            f"{corpo}"
            f"{aviso_strike}\n\n"
            f"Fico no aguardo do seu retorno.\n\n"
            f"Obrigada pela atenção!"
        )

    # --------------------------------------------------------
    # RESPONSÁVEL / ANALISTA / TÉCNICO
    # --------------------------------------------------------

    if quem not in {
        "",
        "Demandante",
        "Aprovador",
        "Chamado relacionado",
        "HelpDesk",
    }:
        dias = _dias_em_aberto(chamado)

        if dias is None:
            tempo_aberto = "está em aberto"
        elif dias == 1:
            tempo_aberto = "está há *1 dia* em aberto"
        else:
            tempo_aberto = f"está há *{dias} dias* em aberto"

        return (
            f"{saudacao}, {quem}! Tudo bem?\n\n"
            f"{_apresentacao_atendimento()}\n\n"
            f"Estou acompanhando o chamado abaixo:\n\n"
            f"{chave} – {resumo}\n"
            f"(Data de criação: {data_criacao})\n\n"
            f"O chamado {tempo_aberto} e gostaria de verificar "
            f"se há alguma novidade sobre o atendimento ou se você "
            f"precisa de alguma informação adicional para dar "
            f"prosseguimento à tratativa.\n\n"
            f"Fico no aguardo do seu retorno.\n\n"
            f"Obrigada pela atenção!"
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    return (
        f"{saudacao}! Tudo bem?\n\n"
        f"{_apresentacao_atendimento()}\n\n"
        f"Estou acompanhando o chamado abaixo:\n\n"
        f"{chave} – {resumo}\n"
        f"(Data de criação: {data_criacao})\n\n"
        f"{objetivo}\n\n"
        f"Fico no aguardo do seu retorno.\n\n"
        f"Obrigada pela atenção!"
    )


# ============================================================
# MENSAGEM DE STRIKE
# ============================================================

def _montar_mensagem_strike(chamado, analise, numero, objetivo=None):
    """Monta a nota de Jira para um número de Strike já validado."""

    chave = limpar_texto(
        chamado.get("chave")
    )

    cliente = primeiro_nome_completo(
        chamado
    )

    if not objetivo:
        objetivo = sugerir_objetivo(
            chamado,
            analise
        )

    objetivo = limpar_texto(
        objetivo
    )

    texto = (
        f"{{Strike {numero}}} –\n"
        f"Nota do Chamado:\n"
        f"Prezado(a) {cliente}, entramos em contato referente "
        f"ao chamado {chave} aberto com o Help Desk.\n\n"
        f"Tentamos contato sem sucesso. "
        f"Precisamos {objetivo} para dar continuidade no atendimento, "
        f"portanto agradecemos que responda por este canal ou "
        f"pelos canais oficiais da Central de Serviços.\n"
        f"Seu contato é importante.\n\n"
        f"Atenciosamente,\nCentral de Serviços"
    )

    return texto


def gerar_mensagem_strike(
    chamado,
    analise,
    elegibilidade,
    objetivo=None
):
    """
    Retorna None quando NÃO existe autorização
    do motor para aplicar Strike agora.
    """

    if not elegibilidade.get(
        "elegivel_strike",
        False
    ):
        return None

    numero = elegibilidade.get(
        "proximo_strike"
    )

    if numero not in {1, 2, 3}:
        return None

    return _montar_mensagem_strike(
        chamado,
        analise,
        numero,
        objetivo,
    )


def gerar_mensagem_strike_manual(
    chamado,
    analise,
    numero,
    objetivo=None,
):
    """
    Gera uma nota de Strike por solicitação explícita da usuária.

    A interface determina o próximo número a partir do histórico
    presente no XML e pede confirmação antes de chamar esta função.
    Não altera o chamado no Jira.
    """

    if numero not in {1, 2, 3}:
        return None

    return _montar_mensagem_strike(
        chamado,
        analise,
        numero,
        objetivo,
    )


# ============================================================
# ATUALIZAÇÃO PARA O JIRA
# ============================================================

MODELOS_ATUALIZACAO_JIRA = {
    "Contato com demandante — aguardando manifestação": (
        "Contato realizado para confirmar se a solicitação foi atendida. "
        "Aguardando manifestação do demandante."
    ),
    "Demandante informou que o problema foi resolvido": (
        "Em contato com o demandante, fui informada de que o problema "
        "já foi resolvido."
    ),
    "Demandante informou que o problema persiste": (
        "Usuário informa que o problema ainda persiste e solicita "
        "brevidade no atendimento."
    ),
    "Demandante não faz mais parte do banco": (
        "Demandante não faz mais parte do quadro de funcionários do banco, "
        "não sendo possível validar a necessidade de continuidade da demanda. "
        "Caso o atendimento ainda seja necessário, deverá ser aberto um novo "
        "chamado pelo responsável atual da unidade."
    ),
    "Empresa de manutenção fechou o chamado": (
        "Chamado fechado pela empresa de manutenção em [data e horário]."
    ),
    "Informar equipe e solicitar brevidade": (
        "Obrigada. Irei informar a equipe necessária e solicitar brevidade."
    ),
    "Contato com analista responsável": (
        "Contato realizado com o analista responsável para verificar se a "
        "solicitação ainda demanda alguma informação complementar ou se a "
        "situação já foi resolvida."
    ),
    "Demandante autorizou encerramento": (
        "Em contato com o demandante, fui informada de que o chamado pode "
        "ser encerrado."
    ),
    "Contato com demandante — aguardando retorno": (
        "Em contato com o demandante, aguardando retorno."
    ),
    "Contato com aprovador — aguardando retorno": (
        "Contato realizado com o responsável pela aprovação, aguardando retorno."
    ),
    "Aguardando encerramento de chamado relacionado": (
        "Aguardando o encerramento do chamado relacionado para dar "
        "continuidade à tratativa."
    ),
    "Transferência por mudança de turno": (
        "Chamado transferido para outro técnico em razão da mudança de turno, "
        "garantindo a continuidade do atendimento."
    ),
    "Atendimento previsto": (
        "Em contato com a área responsável, fui informada de que o atendimento "
        "está previsto para o dia [data prevista]."
    ),
}


def gerar_atualizacao_jira(tipo):
    """Retorna o modelo de atualização escolhido pela usuária."""

    return MODELOS_ATUALIZACAO_JIRA.get(tipo, "")


# ============================================================
# PACOTE COMPLETO DE MENSAGENS
# ============================================================

def gerar_mensagens(
    chamado,
    analise,
    elegibilidade,
    objetivo=None
):
    if not objetivo:
        objetivo = sugerir_objetivo(
            chamado,
            analise
        )

    return {
        "objetivo_sugerido": objetivo,

        "mensagem_contato": gerar_mensagem_contato(
            chamado,
            analise,
            objetivo
        ),

        "mensagem_strike": gerar_mensagem_strike(
            chamado,
            analise,
            elegibilidade,
            objetivo
        ),
    }
