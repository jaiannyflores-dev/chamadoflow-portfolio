import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from .jira_access import analisar_solicitacao_acesso_jira
FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")
INICIO_HORARIO_COMERCIAL = time(7, 0)
FIM_HORARIO_COMERCIAL = time(18, 0)
HORAS_UTEIS_POR_DIA = 11
LIMITE_SLA_HORAS_UTEIS = 3 * HORAS_UTEIS_POR_DIA


STATUS_MONITORADOS = {
    "Em Impedimento",
    "Aguardando Aprovação",
    "Encaminhado",
    "Em Atendimento",
    "Aberto",
    "Reaberto"
}


def converter_data(data_texto):
    """
    Converte as datas do XML do Jira para datetime.

    Exemplo:
    Mon, 14 Sep 2026 15:50:00 -0300
    """

    if not data_texto:
        return None

    try:
        return parsedate_to_datetime(data_texto)

    except (TypeError, ValueError):
        return None


def calcular_horas(data_inicio, agora=None):
    """
    Calcula quantas horas se passaram desde uma data.
    """

    data = converter_data(data_inicio)

    if data is None:
        return None

    if agora is None:
        agora = datetime.now(FUSO_BRASILIA)

    diferenca = agora - data

    return diferenca.total_seconds() / 3600


def calcular_horas_uteis(data_inicio, agora=None):
    """Calcula horas úteis, de segunda a sexta, entre 07:00 e 18:00."""

    inicio = converter_data(data_inicio)

    if inicio is None:
        return None

    if agora is None:
        agora = datetime.now(FUSO_BRASILIA)

    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=FUSO_BRASILIA)
    else:
        inicio = inicio.astimezone(FUSO_BRASILIA)

    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=FUSO_BRASILIA)
    else:
        agora = agora.astimezone(FUSO_BRASILIA)

    if inicio >= agora:
        return 0

    horas_uteis = 0.0
    dia = inicio.date()

    while dia <= agora.date():
        if dia.weekday() < 5:
            inicio_expediente = datetime.combine(
                dia,
                INICIO_HORARIO_COMERCIAL,
                tzinfo=FUSO_BRASILIA,
            )
            fim_expediente = datetime.combine(
                dia,
                FIM_HORARIO_COMERCIAL,
                tzinfo=FUSO_BRASILIA,
            )
            inicio_periodo = max(inicio, inicio_expediente)
            fim_periodo = min(agora, fim_expediente)

            if fim_periodo > inicio_periodo:
                horas_uteis += (
                    fim_periodo - inicio_periodo
                ).total_seconds() / 3600

        dia += timedelta(days=1)

    return horas_uteis


def analisar_sla(chamado, agora=None):
    """Avalia o SLA de três dias úteis a partir da criação do chamado."""

    horas_uteis = calcular_horas_uteis(chamado.get("criado"), agora)

    return {
        "horas_uteis_desde_criacao": horas_uteis,
        "sla_estourado": (
            horas_uteis is not None
            and horas_uteis > LIMITE_SLA_HORAS_UTEIS
        ),
    }


def identificar_vip(chamado):
    """Identifica o marcador [VIP] no resumo do chamado."""

    resumo = str(chamado.get("resumo", ""))

    return bool(re.search(r"\[\s*vip\s*\]", resumo, re.IGNORECASE))


def analisar_tempo(chamado, agora=None):
    """
    Analisa tempo na fila e tempo sem atualização.
    """

    if agora is None:
        agora = datetime.now(FUSO_BRASILIA)

    horas_na_fila = calcular_horas(
        chamado.get("entrada_helpdesk"),
        agora
    )

    horas_sem_atualizacao = calcular_horas(
        chamado.get("atualizado"),
        agora
    )

    status = chamado.get("status", "")

    status_monitorado = status in STATUS_MONITORADOS

    mais_de_2h_sem_atualizacao = (
        horas_sem_atualizacao is not None
        and horas_sem_atualizacao >= 2
    )

    mais_de_2h_na_fila = (
        horas_na_fila is not None
        and horas_na_fila >= 2
    )

    precisa_analisar = (
        status_monitorado
        and mais_de_2h_sem_atualizacao
    )

    return {
        "status_monitorado": status_monitorado,
        "horas_na_fila": horas_na_fila,
        "horas_sem_atualizacao": horas_sem_atualizacao,
        "mais_de_2h_na_fila": mais_de_2h_na_fila,
        "mais_de_2h_sem_atualizacao": mais_de_2h_sem_atualizacao,
        "precisa_analisar": precisa_analisar
    }

def obter_texto_comentarios(chamado, limite=5):
    """
    Junta os comentários mais recentes para análise.
    """

    comentarios = chamado.get("comentarios", [])

    textos = []

    for comentario in comentarios[:limite]:
        texto = comentario.get("texto", "").strip()

        if texto:
            textos.append(texto.lower())

    return " ".join(textos)


def classificar_motivo(chamado):
    """
    Classifica o estado atual do chamado.

    O último comentário tem prioridade.
    Comentários anteriores serão usados posteriormente
    apenas como contexto.
    """

    status = chamado.get("status", "")

    ultimo = chamado.get("ultimo_comentario")

    if ultimo:
        texto = ultimo.get("texto", "").strip().lower()
    else:
        texto = ""

    resumo = chamado.get("resumo", "").lower()

    # --------------------------------------------------
    # SEM COMENTÁRIO / COMENTÁRIO VAZIO
    # --------------------------------------------------

    if not texto:
        if status == "Aguardando Aprovação":
            return "Aguardando aprovação"

        return "Revisão manual"

    # --------------------------------------------------
    # APROVAÇÃO JÁ REALIZADA
    # --------------------------------------------------

    texto_limpo = texto.strip(" .!,:;-")

    aprovacao_realizada_exata = {
        "de acordo",
        "de acordo, pode prosseguir",
        "de acordo pode prosseguir",
        "aprovado",
        "aprovada",
        "autorizado",
        "autorizada"
    }

    padroes_aprovacao_realizada = [
        "aprovação concedida",
        "aprovacao concedida",
        "aprovação realizada",
        "aprovacao realizada",
        "solicitação aprovada",
        "solicitacao aprovada"
    ]

    if (
        texto_limpo in aprovacao_realizada_exata
        or any(
            padrao in texto
            for padrao in padroes_aprovacao_realizada
        )
    ):
        return "Aprovação recebida - cobrar andamento"

    # --------------------------------------------------
    # CHAMADO RELACIONADO
    # --------------------------------------------------

    padroes_relacionado = [
        "chamado relacionado",
        "chamado relacionamento",
        "aguardando resolução do serv-",
        "aguardando a resolução do serv-",
        "aguardando resolução do inst-",
        "aguardando a resolução do inst-",
        "aguardando resolução do chamado serv-",
        "aguardando a resolução do chamado serv-",
        "aguardando resolução do chamado inst-",
        "aguardando a resolução do chamado inst-",
        "aguardando finalização do serv-",
        "aguardando finalização do inst-",
        "aguardando encerramento do serv-",
        "aguardando encerramento do inst-",
        "aguardando criação dos grupos"
    ]

    if any(
        padrao in texto
        for padrao in padroes_relacionado
    ):
        return "Aguardando chamado relacionado"

    # --------------------------------------------------
    # ANALISTA / TÉCNICO
    # --------------------------------------------------

    padroes_analista = [
        "aguardando retorno do analista",
        "aguardando o retorno do analista",
        "não obtive retorno do analista",
        "nao obtive retorno do analista",
        "aguardando retorno do técnico",
        "aguardando retorno do tecnico",
        "analista responsável para verificar",
        "analista responsavel para verificar"
    ]

    if any(
        padrao in texto
        for padrao in padroes_analista
    ):
        return "Aguardando analista/técnico"

    # --------------------------------------------------
    # APROVAÇÃO PENDENTE
    # --------------------------------------------------

    padroes_aprovacao = [
        "necessário aprovação",
        "necessario aprovação",
        "necessária aprovação",
        "necessaria aprovação",
        "necessário aprovaçã",
        "responsável pela aprovação",
        "responsavel pela aprovação",
        "aguardando aprovação",
        "aguardando aprovacao",
        "necessária aprovação do gestor",
        "necessaria aprovação do gestor",
        "de acordo da superintendência",
        "de acordo da superintendencia",
        "de acordo do diretor",
        "novamente o de acordo",
        "aprova por favor"
    ]

    if any(
        padrao in texto
        for padrao in padroes_aprovacao
    ):
        return "Aguardando aprovação"

    # --------------------------------------------------
    # DEMANDANTE / USUÁRIO
    # --------------------------------------------------

    padroes_usuario = [
        "aguardando retorno do demandante",
        "aguardando o retorno do demandante",
        "aguardando retorno do usuário",
        "aguardando retorno do usuario",
        "aguardando o retorno das informações",
        "aguardando o retorno das informacoes",
        "pergunta ao usuário",
        "pergunta ao usuario",
        "contato com o demandante, aguardando retorno",
        "tentativa de contato via telefone",
        "realizando tentativa de contato",
        "entrando em contato via chat",
        "verificar se o procedimento ainda é necessário",
        "verificar se o procedimento ainda e necessario",
        "verificação do monitor e cabos junto ao colaborador",
        "verificacao do monitor e cabos junto ao colaborador"
    ]

    if any(
        padrao in texto
        for padrao in padroes_usuario
    ):
        return "Aguardando demandante"

    # --------------------------------------------------
    # STATUS DE APROVAÇÃO SEM EVIDÊNCIA CONTRÁRIA
    # --------------------------------------------------

    if status == "Aguardando Aprovação":
        return "Aguardando aprovação"

    # --------------------------------------------------
    # STATUS DE APROVAÇÃO SEM EVIDÊNCIA CONTRÁRIA
    # --------------------------------------------------

    if status == "Aguardando Aprovação":
        return "Aguardando aprovação"

    # --------------------------------------------------
    # VALIDAÇÃO PELO DEMANDANTE
    # --------------------------------------------------

    padroes_validacao_usuario = [
        "favor validar o funcionamento",
        "favor validar funcionamento",
        "validar o funcionamento",
        "para mais informações",
        "para mais informacoes",
        "aguardando verificação do usuário",
        "aguardando verificacao do usuario",
        "aguardando validação do usuário",
        "aguardando validacao do usuario"
    ]

    if any(
        padrao in texto
        for padrao in padroes_validacao_usuario
    ):
        return "Aguardando demandante"

    # --------------------------------------------------
    # RESPOSTA RECEBIDA / HELPDESK PRECISA CONTINUAR
    # --------------------------------------------------

    padroes_resposta_recebida = [
        "já foi respondido",
        "ja foi respondido",
        "segue para sequência de atendimento",
        "segue para sequencia de atendimento",
        "favor encaminhar para o time de sustentação correto",
        "favor encaminhar para a equipe responsável",
        "favor encaminhar para a equipe responsavel"
    ]

    if any(
        padrao in texto
        for padrao in padroes_resposta_recebida
    ):
        return "HelpDesk precisa continuar"

    # --------------------------------------------------
    # ATENDIMENTO INICIADO, MAS SEM NOVA ATUALIZAÇÃO
    # --------------------------------------------------

    if (
        "atendimento iniciado pelo time [helpdesk" in texto
        and status in {"Em Atendimento", "Encaminhado"}
    ):
        return "Cobrar atualização do técnico"

    # --------------------------------------------------
    # CASOS QUE AINDA PRECISAM DE INTERPRETAÇÃO
    # --------------------------------------------------

    return "Revisão manual"

def identificar_autor_comentario(chamado, comentario):
    """
    Tenta identificar o papel do autor de um comentário.

    Só faz identificações que podem ser comprovadas
    pelos dados disponíveis no XML.
    """

    if not comentario:
        return "Desconhecido"

    autor = str(
        comentario.get("autor", "")
    ).strip()

    criador_id = str(
        chamado.get("criador_id", "")
    ).strip()

    if (
        autor
        and criador_id
        and autor == criador_id
    ):
        return "Criador"

    return "Desconhecido"

def detectar_resposta_a_solicitacao(chamado):
    """
    Detecta quando o comentário mais recente parece responder
    a uma solicitação feita no comentário imediatamente anterior.

    A função é propositalmente conservadora:
    não tenta identificar quem são os autores.
    Analisa apenas a sequência da conversa.
    """

    comentarios = chamado.get(
        "comentarios",
        []
    )

    if len(comentarios) < 2:
        return False

    atual = comentarios[0]
    anterior = comentarios[1]

    texto_atual = str(
        atual.get("texto", "")
    ).lower().strip()

    texto_anterior = str(
        anterior.get("texto", "")
    ).lower().strip()

    autor_atual = str(
        atual.get("autor", "")
    ).strip()

    autor_anterior = str(
        anterior.get("autor", "")
    ).strip()

    if not texto_atual or not texto_anterior:
        return False

    # Se foi a mesma pessoa que escreveu os dois comentários,
    # não assumimos que houve resposta de outra parte.
    if (
        autor_atual
        and autor_anterior
        and autor_atual == autor_anterior
    ):
        return False

    solicitacao_anterior = any(
        expressao in texto_anterior
        for expressao in [
            "solicitar mais informações",
            "solicitar mais informacoes",
            "favor informar",
            "favor fornecer",
            "poderia informar",
            "poderiam informar",
            "poderia fornecer",
            "poderiam fornecer",
            "precisamos de mais informações",
            "precisamos de mais informacoes",
            "necessário mais informações",
            "necessario mais informacoes"
        ]
    )

    if not solicitacao_anterior:
        return False

    # Evita interpretar uma simples mensagem administrativa
    # ou extremamente curta como resposta suficiente.
    resposta_substantiva = (
        len(texto_atual) >= 40
    )

    return resposta_substantiva


def analisar_strike(chamado):
    """
    Analisa o histórico de Strike sem alterar
    a situação principal do chamado.

    Retorna o maior Strike encontrado e, quando possível,
    a data do comentário correspondente.
    """

    resumo = str(
        chamado.get("resumo", "")
    )

    comentarios = chamado.get(
        "comentarios",
        []
    )

    padrao = re.compile(
        r"\bstrike\s*[-:]?\s*([123])\b",
        re.IGNORECASE
    )

    strikes_encontrados = []

    # --------------------------------------------------
    # STRIKE NO RESUMO
    # --------------------------------------------------

    for numero in padrao.findall(resumo):

        strikes_encontrados.append({
            "numero": int(numero),
            "data": None,
            "origem": "Resumo"
        })

    # --------------------------------------------------
    # STRIKES NOS COMENTÁRIOS
    # --------------------------------------------------

    for comentario in comentarios:

        texto_comentario = str(
            comentario.get(
                "texto",
                ""
            )
        )

        for numero in padrao.findall(
            texto_comentario
        ):

            strikes_encontrados.append({
                "numero": int(numero),
                "data": comentario.get(
                    "criado"
                ),
                "origem": "Comentário"
            })

    if not strikes_encontrados:

        return {
            "strike_atual": 0,
            "possui_strike": False,
            "proximo_strike": 1,
            "limite_atingido": False,
            "data_ultimo_strike": None,
            "origem_ultimo_strike": None
        }

    strike_atual = max(
        item["numero"]
        for item in strikes_encontrados
    )

    # Entre os registros do maior Strike,
    # prioriza aquele que possui data.
    registros_strike_atual = [
        item
        for item in strikes_encontrados
        if item["numero"] == strike_atual
    ]

    registro_com_data = next(
        (
            item
            for item in registros_strike_atual
            if item["data"]
        ),
        None
    )

    registro_referencia = (
        registro_com_data
        or registros_strike_atual[0]
    )

    proximo_strike = (
        None
        if strike_atual >= 3
        else strike_atual + 1
    )

    return {
        "strike_atual": strike_atual,
        "possui_strike": True,
        "proximo_strike": proximo_strike,
        "limite_atingido": strike_atual >= 3,
        "data_ultimo_strike": registro_referencia["data"],
        "origem_ultimo_strike": registro_referencia["origem"]
    }

def analisar_estado_contato(chamado, analise_acao):
    comentarios = chamado.get("comentarios", []) or []

    situacao = analise_acao.get("situacao", "")
    quem = analise_acao.get("quem_precisa_agir", "")

    # Analisa primeiro os comentários mais recentes.
    # O XML já fornece os comentários do mais novo para o mais antigo.
    comentarios_recentes = comentarios[:5]

    textos = [
        str(c.get("texto", "")).lower()
        for c in comentarios_recentes
    ]

    padroes_falha = [
        "tentamos localizá-lo sem sucesso",
        "tentamos localiza-lo sem sucesso",
        "sem sucesso no contato",
        "sem sucesso no contato com",
        "não conseguimos contato",
        "nao conseguimos contato",
        "não foi possível contato",
        "nao foi possivel contato",
        "não foi possível realizar contato",
        "nao foi possivel realizar contato",
        "não obtivemos retorno",
        "nao obtivemos retorno",
        "não houve retorno",
        "nao houve retorno",
    ]

    padroes_contato = [
        "em contato com",
        "contato realizado",
        "feito pergunta",
        "via chat",
        "via telefone",
        "entrando em contato",
        "realizando tentativa",
        "solicitando o de acordo",
        "solicitando de acordo",
        "aprova por favor",
    ]

    falha = any(
        any(padrao in texto for padrao in padroes_falha)
        for texto in textos
    )

    contato = any(
        any(padrao in texto for padrao in padroes_contato)
        for texto in textos
    )

    if falha:
        estado = "Falha de contato identificada"

    elif contato:
        estado = "Contato realizado/em andamento"

    else:
        estado = "Contato não identificado"

    if situacao == "Aguardando aprovação":
        alvo = "Aprovador"

    elif situacao == "Aguardando demandante":
        alvo = "Demandante"

    else:
        alvo = quem

    return {
        "estado_contato": estado,
        "alvo_contato": alvo,
        "falha_contato": falha,
        "contato_identificado": contato,
    }

def avaliar_elegibilidade_strike(chamado, analise_acao=None):
    """
    Avalia se o chamado está em condição de avançar
    na regra dos Três Strikes.

    IMPORTANTE:
    - Strike é controle de tentativa de contato.
    - Não substitui a situação principal do chamado.
    - O próximo Strike só é sugerido quando existe
      evidência de nova tentativa de contato sem resposta.
    - Strike 3 implica fechamento do chamado.
    """

    if analise_acao is None:
        analise_acao = analisar_acao(chamado)

    strike = analisar_strike(chamado)

    situacao = analise_acao.get(
        "situacao",
        ""
    )

    comentarios = chamado.get(
        "comentarios",
        []
    )

    # --------------------------------------------------
    # SITUAÇÕES QUE NÃO DEVEM AVANÇAR STRIKE
    # --------------------------------------------------

    situacoes_bloqueadas = {
        "Aguardando chamado relacionado",
        "Aguardando analista/técnico",
        "Cobrar atualização do técnico",
        "HelpDesk precisa continuar",
        "Informação recebida - continuar atendimento",
        "Responsável precisa retornar",
        "Sem atualização identificada",
        "Aprovação recebida - cobrar andamento",
        "Revisão manual",
    }

    if situacao in situacoes_bloqueadas:

        return {
            "elegivel_strike": False,
            "strike_atual": strike["strike_atual"],
            "proximo_strike": strike["proximo_strike"],
            "acao_strike": "Não aplicar Strike",
            "motivo_strike": (
                f"Situação atual: {situacao}"
            ),
            "requer_validacao_manual": False
        }

    # --------------------------------------------------
    # LIMITE JÁ ATINGIDO
    # --------------------------------------------------

    if strike["limite_atingido"]:

        return {
            "elegivel_strike": False,
            "strike_atual": 3,
            "proximo_strike": None,
            "acao_strike": "Verificar fechamento do chamado",
            "motivo_strike": (
                "Strike 3 já identificado no histórico"
            ),
            "requer_validacao_manual": True
        }

    # --------------------------------------------------
    # IDENTIFICA NOVA TENTATIVA SEM RESPOSTA
    # --------------------------------------------------

    padroes_sem_resposta = [
    "tentamos localizá-lo sem sucesso",
    "tentamos localiza-lo sem sucesso",
    "sem sucesso no contato",
    "sem sucesso no contato com",
    "não conseguimos contato",
    "nao conseguimos contato",
    "não foi possível contato",
    "nao foi possivel contato",
    "não foi possível realizar contato",
    "nao foi possivel realizar contato",
    "não obtivemos retorno",
    "nao obtivemos retorno",
    "não houve retorno",
    "nao houve retorno",
]

    tentativa_encontrada = None

    for comentario in comentarios:

        texto = str(
            comentario.get(
                "texto",
                ""
            )
        ).lower()

        if any(
            padrao in texto
            for padrao in padroes_sem_resposta
        ):
            tentativa_encontrada = comentario
            break

    # --------------------------------------------------
    # SEM EVIDÊNCIA DE TENTATIVA
    # --------------------------------------------------

    if tentativa_encontrada is None:

        # --------------------------------------------------
        # JÁ EXISTE STRIKE NO HISTÓRICO
        # --------------------------------------------------

        if strike["strike_atual"] > 0:

            # Verifica se existe retorno/disponibilidade
            # combinada posterior ao último Strike.
            padroes_retorno_combinado = [
                "irá retornar",
                "ira retornar",
                "vai retornar",
                "retornará",
                "retornara",
                "retorno agendado",
                "contato agendado",
                "ficou agendado",
                "agendado para",
                "ligar novamente",
                "retornar o contato",
            ]

            retorno_combinado = None

            for comentario in comentarios:

                texto = str(
                    comentario.get(
                        "texto",
                        ""
                    )
                ).lower()

                if any(
                    padrao in texto
                    for padrao in padroes_retorno_combinado
                ):
                    retorno_combinado = comentario
                    break

            # ----------------------------------------------
            # HÁ RETORNO COMBINADO
            # ----------------------------------------------

            if retorno_combinado:

                padroes_nova_necessidade_contato = [
                    "aguardando contato",
                    "aguardando contato com",
                    "aguardando o contato",
                    "aguardando de acordo",
                    "aguardando o de acordo",
                ]

                nova_necessidade_contato = None

                try:
                    data_retorno = parsedate_to_datetime(
                        retorno_combinado.get("criado")
                    )

                except (TypeError, ValueError):
                    data_retorno = None

                if data_retorno is not None:

                    for comentario in comentarios:

                        try:
                            data_comentario = parsedate_to_datetime(
                                comentario.get("criado")
                            )

                        except (TypeError, ValueError):
                            continue

                        if data_comentario <= data_retorno:
                            continue

                        texto = str(
                            comentario.get(
                                "texto",
                                ""
                            )
                        ).lower()

                        if any(
                            padrao in texto
                            for padrao
                            in padroes_nova_necessidade_contato
                        ):
                            nova_necessidade_contato = comentario
                            break

                if nova_necessidade_contato:

                    if (
                        analise_acao.get("situacao")
                        == "Aguardando aprovação"
                        and strike["proximo_strike"] == 3
                    ):
                        acao = (
                            "Realizar nova tentativa com o aprovador; "
                            "se não houver resposta, aplicar Strike 3 "
                            "e fechar chamado"
                        )

                    else:
                        acao = "Realizar nova tentativa de contato"

                    return {
                        "elegivel_strike": False,
                        "strike_atual": strike["strike_atual"],
                        "proximo_strike": strike["proximo_strike"],
                        "acao_strike": acao,
                        "motivo_strike": (
                            "Existe Strike anterior e o histórico "
                            "indica necessidade de nova tentativa "
                            "de contato"
                        ),
                        "requer_validacao_manual": False
                    }

            # ----------------------------------------------
            # STRIKE EXISTE, MAS AINDA NÃO HÁ NOVA FALHA
            # ----------------------------------------------

            return {
                "elegivel_strike": False,
                "strike_atual": strike["strike_atual"],
                "proximo_strike": strike["proximo_strike"],
                "acao_strike": "Realizar nova tentativa de contato",
                "motivo_strike": (
                    "Existe Strike anterior, mas ainda não foi "
                    "identificada nova tentativa sem resposta"
                ),
                "requer_validacao_manual": False
            }

        # --------------------------------------------------
        # AINDA NÃO EXISTE STRIKE
        # --------------------------------------------------

        return {
            "elegivel_strike": False,
            "strike_atual": 0,
            "proximo_strike": 1,
            "acao_strike": "Realizar tentativa de contato",
            "motivo_strike": (
                "Não foi identificada tentativa de contato "
                "sem resposta suficiente para aplicar Strike 1"
            ),
            "requer_validacao_manual": False
        }

    # --------------------------------------------------
    # PRIMEIRO STRIKE
    # --------------------------------------------------

    if strike["strike_atual"] == 0:

        return {
            "elegivel_strike": True,
            "strike_atual": 0,
            "proximo_strike": 1,
            "acao_strike": "Aplicar Strike 1",
            "motivo_strike": (
                "Tentativa de contato sem resposta identificada"
            ),
            "requer_validacao_manual": False
        }

    # --------------------------------------------------
    # STRIKE EXISTE, MAS NÃO TEMOS DATA DELE
    # --------------------------------------------------

    if not strike["data_ultimo_strike"]:

        return {
            "elegivel_strike": False,
            "strike_atual": strike["strike_atual"],
            "proximo_strike": strike["proximo_strike"],
            "acao_strike": (
                f"Validar antes de aplicar Strike "
                f"{strike['proximo_strike']}"
            ),
            "motivo_strike": (
                "Strike anterior identificado, mas a data "
                "não pôde ser confirmada pelo XML"
            ),
            "requer_validacao_manual": True
        }

    # --------------------------------------------------
    # VERIFICA SE A TENTATIVA É POSTERIOR AO ÚLTIMO STRIKE
    # --------------------------------------------------

    try:
        data_ultimo_strike = parsedate_to_datetime(
            strike["data_ultimo_strike"]
        )

        data_tentativa = parsedate_to_datetime(
            tentativa_encontrada.get(
                "criado"
            )
        )

    except (TypeError, ValueError):

        return {
            "elegivel_strike": False,
            "strike_atual": strike["strike_atual"],
            "proximo_strike": strike["proximo_strike"],
            "acao_strike": "Validar histórico de Strike",
            "motivo_strike": (
                "Não foi possível comparar as datas "
                "do Strike e da tentativa de contato"
            ),
            "requer_validacao_manual": True
        }

    if data_tentativa <= data_ultimo_strike:

        return {
            "elegivel_strike": False,
            "strike_atual": strike["strike_atual"],
            "proximo_strike": strike["proximo_strike"],
            "acao_strike": "Realizar nova tentativa de contato",
            "motivo_strike": (
                "Não foi identificada nova tentativa sem resposta "
                "posterior ao último Strike"
            ),
            "requer_validacao_manual": False
        }

    # --------------------------------------------------
    # RETORNO / DISPONIBILIDADE COMBINADA
    # --------------------------------------------------

    padroes_retorno_combinado = [
        "irá retornar",
        "ira retornar",
        "vai retornar",
        "retornará",
        "retornara",
        "retorno agendado",
        "contato agendado",
        "ficou agendado",
        "agendado para",
        "ligar novamente",
        "retornar o contato",
    ]

    retorno_combinado = None

    for comentario in comentarios:

        texto = str(
            comentario.get(
                "texto",
                ""
            )
        ).lower()

        if any(
            padrao in texto
            for padrao in padroes_retorno_combinado
        ):
            retorno_combinado = comentario
            break

    if retorno_combinado:

        try:
            data_retorno_registrado = parsedate_to_datetime(
                retorno_combinado.get("criado")
            )

        except (TypeError, ValueError):
            data_retorno_registrado = None

        # --------------------------------------------------
        # VERIFICA SE, DEPOIS DO RETORNO COMBINADO,
        # O HISTÓRICO VOLTOU A INDICAR NECESSIDADE DE CONTATO
        # --------------------------------------------------

        nova_necessidade_contato = None

        padroes_nova_necessidade_contato = [
            "aguardando contato",
            "aguardando contato com",
            "aguardando o contato",
            "aguardando de acordo",
            "aguardando o de acordo",
        ]

        if data_retorno_registrado is not None:

            for comentario in comentarios:

                try:
                    data_comentario = parsedate_to_datetime(
                        comentario.get("criado")
                    )

                except (TypeError, ValueError):
                    continue

                if data_comentario <= data_retorno_registrado:
                    continue

                texto = str(
                    comentario.get(
                        "texto",
                        ""
                    )
                ).lower()

                if any(
                    padrao in texto
                    for padrao in padroes_nova_necessidade_contato
                ):
                    nova_necessidade_contato = comentario
                    break

        # Existe registro posterior dizendo que o contato
        # ainda precisa ser realizado.
        if nova_necessidade_contato:

            if strike["proximo_strike"] == 3:
                acao_condicional = (
                    "Realizar nova tentativa com o aprovador; "
                    "se não houver resposta, aplicar Strike 3 "
                    "e fechar chamado"
                )
            else:
                acao_condicional = (
                    f"Realizar nova tentativa de contato; "
                    f"se não houver resposta, aplicar Strike "
                    f"{strike['proximo_strike']}"
                )

            return {
                "elegivel_strike": False,
                "strike_atual": strike["strike_atual"],
                "proximo_strike": strike["proximo_strike"],
                "acao_strike": acao_condicional,
                "motivo_strike": (
                    "Após o retorno/disponibilidade registrada, "
                    "o histórico voltou a indicar necessidade "
                    "de contato"
                ),
                "requer_validacao_manual": False
            }

        # Ainda existe um retorno combinado posterior
        # ao último Strike sem nova indicação de contato.
        if (
            data_retorno_registrado is None
            or data_retorno_registrado > data_ultimo_strike
        ):
            return {
                "elegivel_strike": False,
                "strike_atual": strike["strike_atual"],
                "proximo_strike": strike["proximo_strike"],
                "acao_strike": (
                    "Respeitar retorno combinado antes "
                    "do próximo Strike"
                ),
                "motivo_strike": (
                    "Foi identificada informação posterior ao último "
                    "Strike indicando retorno, disponibilidade ou "
                    "novo contato combinado"
                ),
                "requer_validacao_manual": False
            }

    # --------------------------------------------------
    # PRÓXIMO STRIKE
    # --------------------------------------------------

    proximo = strike["proximo_strike"]

    if proximo == 3:

        acao = "Aplicar Strike 3 e fechar chamado"

    else:

        acao = (
            f"Aplicar Strike {proximo}"
        )

    return {
        "elegivel_strike": True,
        "strike_atual": strike["strike_atual"],
        "proximo_strike": proximo,
        "acao_strike": acao,
        "motivo_strike": (
            "Nova tentativa de contato sem resposta "
            "identificada após o último Strike"
        ),
        "requer_validacao_manual": False
    }

def analisar_acao(chamado):
    """
    Transforma a classificação do chamado em uma orientação
    operacional para acompanhamento da HelpDesk.

    Não altera classificar_motivo().
    """

    motivo = classificar_motivo(chamado)

    campos = chamado.get(
        "campos_customizados",
        {}
    )

    motivo_impedimento = ""

    valores = campos.get(
        "Motivo do Impedimento",
        []
    )

    if valores:
        motivo_impedimento = valores[0]

    responsavel = chamado.get(
        "responsavel",
        ""
    )

    # --------------------------------------------------
    # QUEM ESTÁ COM A BOLA
    # --------------------------------------------------

    if motivo == "Aguardando demandante":

        quem = "Demandante"
        acao = "Aguardar/cobrar retorno do demandante"

    elif motivo == "Aguardando aprovação":

        quem = "Aprovador"
        acao = "Aguardar/cobrar aprovação"

    elif motivo == "Aguardando chamado relacionado":

        quem = "Chamado relacionado"
        acao = "Acompanhar chamado relacionado"

    elif motivo == "Aguardando analista/técnico":

        quem = responsavel or "Analista/Técnico"
        acao = "Cobrar analista/técnico"

    elif motivo == "Aprovação recebida - cobrar andamento":

        quem = responsavel or "HelpDesk"
        acao = "Dar continuidade ao atendimento"

    elif motivo == "HelpDesk precisa continuar":

        quem = responsavel or "HelpDesk"
        acao = "Dar continuidade ao atendimento"

    elif motivo == "Cobrar atualização do técnico":

        quem = responsavel or "Técnico responsável"
        acao = "Cobrar atualização do responsável"

    else:
        resposta_a_solicitacao = (
            detectar_resposta_a_solicitacao(
                chamado
            )
        )

        ultimo_comentario = chamado.get(
            "ultimo_comentario"
        )

        papel_ultimo_autor = (
            identificar_autor_comentario(
                chamado,
                ultimo_comentario
            )
        )

        texto_ultimo = ""

        if ultimo_comentario:
            texto_ultimo = str(
                ultimo_comentario.get(
                    "texto",
                    ""
                )
            ).lower()

        responsavel_mencionado = (
            responsavel
            and responsavel.lower()
            in texto_ultimo
        )

        cobranca_retorno = any(
            expressao in texto_ultimo
            for expressao in [
                "aguardando retorno",
                "aguardo retorno",
                "sem retorno",
                "não obtive retorno",
                "nao obtive retorno"
            ]
        )
        tentativa_contato_sem_sucesso = any(
            expressao in texto_ultimo
            for expressao in [
                "tentamos localizá-lo sem sucesso",
                "tentamos localiza-lo sem sucesso",
                "tentativa de contato",
                "tentativas de contato",
                "sem sucesso no contato",
                "sem sucesso no contato com",
                "não conseguimos contato",
                "nao conseguimos contato"
            ]
        )

        # O próprio criador está cobrando nominalmente
        # o responsável atual do chamado.
        if resposta_a_solicitacao:
            motivo = "Informação recebida - continuar atendimento"
            quem = responsavel or "HelpDesk"
            acao = "Dar continuidade ao atendimento"

        elif (
            papel_ultimo_autor == "Criador"
            and responsavel_mencionado
            and cobranca_retorno
        ):
            motivo = "Responsável precisa retornar"
            quem = responsavel
            acao = "Cobrar atualização do responsável"
        elif (
            motivo_impedimento == "Aguardando Retorno do Usuário"
            and tentativa_contato_sem_sucesso
        ):
            motivo = "Aguardando demandante"
            quem = "Demandante"
            acao = "Aguardar/cobrar retorno do demandante"

        elif (
            chamado.get("status") == "Em Atendimento"
            and responsavel
        ):
            motivo = "Sem atualização identificada"
            quem = responsavel
            acao = "Cobrar atualização do responsável"

        else:
            quem = "Indefinido"
            acao = "Revisar manualmente"

    # --------------------------------------------------
    # DIVERGÊNCIA ENTRE CAMPO DO JIRA E ANÁLISE
    # --------------------------------------------------

    divergencia = False

    if motivo_impedimento == "Aguardando Retorno do Usuário":

        if motivo in {
            "Aguardando aprovação",
            "Aguardando chamado relacionado",
            "Aguardando analista/técnico",
            "Aprovação recebida - cobrar andamento",
            "HelpDesk precisa continuar",
            "Cobrar atualização do técnico"
        }:
            divergencia = True

    elif motivo_impedimento == "Aguardando Chamado Relacionado":

        if motivo not in {
            "Aguardando chamado relacionado",
            "Aguardando analista/técnico"
        }:
            divergencia = True

    # --------------------------------------------------
    # CONFIANÇA
    # --------------------------------------------------

    if motivo == "Revisão manual":
        confianca = "Baixa"

    elif motivo == "Sem atualização identificada":
        confianca = "Média"

    elif divergencia:
        confianca = "Média"

    else:
        confianca = "Alta"

    return {
        "situacao": motivo,
        "quem_precisa_agir": quem,
        "acao": acao,
        "responsavel": responsavel,
        "motivo_impedimento_jira": motivo_impedimento,
        "divergencia": divergencia,
        "confianca": confianca
    }

def analisar_chamado_operacional(chamado):
    """
    Consolida as diferentes análises em uma decisão operacional única.

    Não altera as regras de classificação, contato ou Strike.
    Apenas organiza os resultados para consumo pela interface.
    """

    analise = analisar_acao(chamado)

    contato = analisar_estado_contato(
        chamado,
        analise
    )

    strike = analisar_strike(chamado)

    elegibilidade = avaliar_elegibilidade_strike(
        chamado,
        analise
    )

    tempo = analisar_tempo(chamado)
    sla = analisar_sla(chamado)
    vip = identificar_vip(chamado)
    triagem_acesso_jira = analisar_solicitacao_acesso_jira(chamado)

    situacao = analise.get(
        "situacao",
        "Revisão manual"
    )

    quem = analise.get(
        "quem_precisa_agir",
        "Revisão manual"
    )

    acao_operacional = analise.get(
        "acao",
        "Revisar chamado"
    )

    estado_contato = contato.get(
        "estado_contato"
    )

    strike_atual = strike.get(
        "strike_atual",
        0
    )

    proximo_strike = strike.get(
        "proximo_strike"
    )

    elegivel_strike = elegibilidade.get(
        "elegivel_strike",
        False
    )

    acao_strike = elegibilidade.get(
        "acao_strike",
        ""
    )

    validacao_manual = elegibilidade.get(
        "requer_validacao_manual",
        False
    )

    # --------------------------------------------------
    # 1. VALIDAÇÃO MANUAL TEM PRIORIDADE
    # --------------------------------------------------

    if validacao_manual:

        acao_final = acao_strike
        prioridade = "Alta"

    # --------------------------------------------------
    # 2. STRIKE PODE SER APLICADO AGORA
    # --------------------------------------------------

    elif elegivel_strike:

        acao_final = acao_strike
        prioridade = "Alta"

    # --------------------------------------------------
    # 3. JÁ EXISTE STRIKE E HÁ PRÓXIMA AÇÃO ESPECÍFICA
    # --------------------------------------------------

    elif (
        strike_atual > 0
        and acao_strike
        not in {
            "",
            "Não aplicar Strike",
        }
    ):

        acao_final = acao_strike
        prioridade = "Alta"

    # --------------------------------------------------
    # 4. AGUARDANDO APROVAÇÃO
    # --------------------------------------------------

    elif situacao == "Aguardando aprovação":

        if estado_contato == "Contato não identificado":

            acao_final = "Contatar aprovador"
            prioridade = "Normal"

        elif estado_contato == "Contato realizado/em andamento":

            acao_final = "Aguardar retorno do aprovador"
            prioridade = "Normal"

        elif estado_contato == "Falha de contato identificada":

            acao_final = acao_strike
            prioridade = "Alta"

        else:

            acao_final = "Revisar contato com aprovador"
            prioridade = "Normal"

    # --------------------------------------------------
    # 5. AGUARDANDO DEMANDANTE
    # --------------------------------------------------

    elif situacao == "Aguardando demandante":

        if estado_contato == "Contato não identificado":

            acao_final = "Contatar demandante"
            prioridade = "Normal"

        elif estado_contato == "Contato realizado/em andamento":

            acao_final = "Aguardar retorno do demandante"
            prioridade = "Normal"

        elif estado_contato == "Falha de contato identificada":

            acao_final = acao_strike
            prioridade = "Alta"

        else:

            acao_final = "Revisar contato com demandante"
            prioridade = "Normal"

    # --------------------------------------------------
    # 6. DEMAIS SITUAÇÕES
    # --------------------------------------------------

    else:

        acao_final = acao_operacional

        if situacao in {
            "Informação recebida - continuar atendimento",
            "Aprovação recebida - cobrar andamento",
            "HelpDesk precisa continuar",
            "Responsável precisa retornar",
            "Cobrar atualização do técnico",
            "Sem atualização identificada",
        }:
            prioridade = "Alta"

        else:
            prioridade = "Normal"

    if triagem_acesso_jira["triagem_acesso_jira"]:
        situacao = "Acesso Jira sem aprovação"
        quem = "Aprovador" if triagem_acesso_jira["aprovador_jira_sugerido"] else "HelpDesk"
        acao_final = triagem_acesso_jira["acao_acesso_jira"]
        prioridade = "Alta"

    if sla["sla_estourado"]:
        prioridade = "SLA estourado"

    return {
        "chave": chamado.get("chave"),
        "resumo": chamado.get("resumo"),
        "status_jira": chamado.get("status"),
        "responsavel": chamado.get("responsavel"),
        "fila_origem": chamado.get("fila_origem", ""),
        "horas_sem_atualizacao": tempo.get("horas_sem_atualizacao"),

        "situacao": situacao,
        "quem_precisa_agir": quem,
        "acao_operacional": acao_operacional,

        "estado_contato": estado_contato,
        "alvo_contato": contato.get("alvo_contato"),

        "strike_atual": strike_atual,
        "proximo_strike": proximo_strike,
        "elegivel_strike": elegivel_strike,
        "acao_strike": acao_strike,

        "acao_final": acao_final,
        "prioridade": prioridade,
        "vip": vip,
        **sla,

        "confianca": analise.get("confianca"),
        "divergencia": analise.get("divergencia"),
        "requer_validacao_manual": validacao_manual,
        **triagem_acesso_jira,
    }
