import xml.etree.ElementTree as ET
import re
from pathlib import Path


def texto(elemento, caminho, padrao=""):
    """
    Retorna o texto de um elemento XML.
    Se o elemento não existir, retorna o valor padrão.
    """
    encontrado = elemento.find(caminho)

    if encontrado is None or encontrado.text is None:
        return padrao

    return encontrado.text.strip()


def extrair_comentarios(item):
    """
    Extrai os comentários de um chamado.
    """
    comentarios = []

    comments = item.find("comments")

    if comments is None:
        return comentarios

    for comentario in comments.findall("comment"):
        comentarios.append({
            "autor": comentario.attrib.get("author", ""),
            "criado": comentario.attrib.get("created", ""),
            "texto": "".join(comentario.itertext()).strip()
        })

    return comentarios


def extrair_campos_customizados(item):
    """
    Extrai todos os campos customizados do chamado.
    Retorna um dicionário:
    {
        "Nome do Campo": ["valor1", "valor2"]
    }
    """
    campos = {}

    customfields = item.find("customfields")

    if customfields is None:
        return campos

    for campo in customfields.findall("customfield"):

        nome_elemento = campo.find("customfieldname")

        if nome_elemento is None or not nome_elemento.text:
            continue

        nome = nome_elemento.text.strip()

        valores = []


        customfieldvalues = campo.find("customfieldvalues")

        if customfieldvalues is not None:

            for valor in customfieldvalues:

                # Alguns campos de usuário do Jira armazenam
                # o nome completo no atributo displayname.
                displayname = valor.attrib.get(
                    "displayname",
                    ""
                ).strip()

                texto_valor = "".join(
                    valor.itertext()
                ).strip()

                if displayname:
                    valores.append(displayname)

                elif texto_valor:
                    valores.append(texto_valor)

        campos[nome] = valores

    return campos


def primeiro_valor(campos, nome, padrao=""):
    """
    Retorna o primeiro valor de um campo customizado.
    """
    valores = campos.get(nome, [])

    if not valores:
        return padrao

    return valores[0]

def extrair_usuario_customizado(item, nome_campo):
    """
    Extrai nome completo e identificador técnico
    de um campo customizado de usuário do Jira.
    """

    customfields = item.find("customfields")

    if customfields is None:
        return {
            "nome": "",
            "id": ""
        }

    for campo in customfields.findall("customfield"):

        nome_elemento = campo.find(
            "customfieldname"
        )

        if (
            nome_elemento is None
            or not nome_elemento.text
            or nome_elemento.text.strip() != nome_campo
        ):
            continue

        customfieldvalues = campo.find(
            "customfieldvalues"
        )

        if customfieldvalues is None:
            break

        valor = customfieldvalues.find(
            "customfieldvalue"
        )

        if valor is None:
            break

        return {
            "nome": valor.attrib.get(
                "displayname",
                ""
            ).strip(),

            "id": "".join(
                valor.itertext()
            ).strip()
        }

    return {
        "nome": "",
        "id": ""
    }

def localizar_entrada_helpdesk(campos, comentarios):
    """
    Localiza a entrada atual do chamado na fila HelpDesk.

    Prioridade:
    1. Data Encaminhamento
    2. Comentário "Atendimento iniciado pelo time [HelpDesk...]"
    3. Não identificada
    """

    data_encaminhamento = primeiro_valor(
        campos,
        "Data Encaminhamento"
    )

    if data_encaminhamento:
        return {
            "data": data_encaminhamento,
            "origem": "Data Encaminhamento"
        }

    for comentario in comentarios:
        texto_comentario = comentario["texto"].casefold()
        if (
            "atendimento iniciado pelo time" in texto_comentario
            and any(
                equipe in texto_comentario
                for equipe in ("helpdesk", "service desk", "central de serviços")
            )
        ):
            return {
                "data": comentario["criado"],
                "origem": "Comentário da Central de Serviços"
            }

    return {
        "data": "",
        "origem": "Não identificada"
    }

def analisar_historico_equipes(campos):
    """
    Reconstrói a sequência real das equipes do chamado.

    Os campos numerados do Jira nem sempre incluem a equipe atual.
    Por isso, Time Solucionador é acrescentado ao final quando necessário.
    """

    equipes_xml = []

    for numero in range(1, 30):

        equipe = (
            primeiro_valor(campos, f"{numero}º equipe")
            or primeiro_valor(campos, f"{numero}ª equipe")
        )

        if equipe:
            equipes_xml.append(equipe)

    equipe_atual = primeiro_valor(
        campos,
        "Time Solucionador"
    )

    # Começa com o histórico registrado pelo Jira
    equipes = list(equipes_xml)

    # O Jira pode não registrar a equipe atual nos campos numerados.
    if (
        equipe_atual
        and (
            not equipes
            or equipes[-1] != equipe_atual
        )
    ):
        equipes.append(equipe_atual)

    # Remove apenas duplicações consecutivas.
    sequencia = []

    for equipe in equipes:

        if (
            not sequencia
            or sequencia[-1] != equipe
        ):
            sequencia.append(equipe)

    def eh_equipe_central_servicos(equipe):
        equipe_normalizada = str(equipe or "").casefold()
        return any(
            termo in equipe_normalizada
            for termo in ("helpdesk", "service desk", "central de serviços")
        )

    passagens_helpdesk = sum(
        1
        for equipe in sequencia
        if eh_equipe_central_servicos(equipe)
    )

    voltou_para_helpdesk = (
        passagens_helpdesk >= 2
    )

    veio_de_outra_equipe = (
        len(sequencia) >= 2
        and eh_equipe_central_servicos(sequencia[-1])
        and not eh_equipe_central_servicos(sequencia[-2])
    )

    return {
        "equipes": sequencia,
        "equipes_xml": equipes_xml,
        "passagens_helpdesk": passagens_helpdesk,
        "voltou_para_helpdesk": voltou_para_helpdesk,
        "veio_de_outra_equipe": veio_de_outra_equipe
    }

def extrair_chamado(item):
    """
    Converte um <item> do XML do Jira em um dicionário Python.
    """

    campos = extrair_campos_customizados(item)
    comentarios = extrair_comentarios(item)
    criador = extrair_usuario_customizado(
        item,
        "Criador"
    )

    entrada_helpdesk = localizar_entrada_helpdesk(
        campos,
        comentarios
    )
    historico_equipes = analisar_historico_equipes(
        campos
    )

    chamado = {
        "chave": texto(item, "key"),
        "resumo": texto(item, "summary"),
        "descricao": texto(item, "description"),
        "status": texto(item, "status"),
        "criado": texto(item, "created"),
        "atualizado": texto(item, "updated"),
        "resolvido": texto(item, "resolved"),

        "responsavel": texto(item, "assignee"),
        "solicitante": texto(item, "reporter"),

            "solicitante_nome": texto(
        item,
        "reporter"
    ),

    "aprovadores": campos.get(
        "Aprovadores",
        []
    ),

    "aprovador_nome": primeiro_valor(
        campos,
        "Aprovadores"
    ),

        "justificativa": primeiro_valor(
            campos,
            "Justificativa"
        ),

        # ID do criador do chamado.
        # Será usado para identificar quando um comentário
        # foi feito pela própria pessoa que criou o chamado.
        "criador_id": criador["id"],
        "criador_nome": criador["nome"],

        "comentarios": comentarios,
        "campos_customizados": campos,

        "comentarios": comentarios,
        "campos_customizados": campos,

        # Comentário mais recente.
        # O XML do Jira traz os comentários do mais novo para o mais antigo.
        "ultimo_comentario": comentarios[0] if comentarios else None,

        # Entrada atual identificada na HelpDesk
        "entrada_helpdesk": entrada_helpdesk["data"],
        "origem_entrada_helpdesk": entrada_helpdesk["origem"],
        "historico_equipes": historico_equipes["equipes"],
        "passagens_helpdesk": historico_equipes["passagens_helpdesk"],
        "voltou_para_helpdesk": historico_equipes["voltou_para_helpdesk"],

        "time_solucionador": primeiro_valor(
            campos,
            "Time Solucionador"
        ),

        "time_anterior": primeiro_valor(
            campos,
            "Time Anterior"
        ),

        "data_encaminhamento": primeiro_valor(
            campos,
            "Data Encaminhamento"
        ),

        "reaberto_por": primeiro_valor(
            campos,
            "Reaberto por"
        )
    }

    return chamado


def ler_xml(caminho_xml):
    """
    Lê a exportação XML do Jira.

    Tolera textos adicionados pelo navegador antes ou depois
    do XML verdadeiro e corrige & não escapados.
    """

    caminho = Path(caminho_xml)

    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {caminho}"
        )

    conteudo = caminho.read_bytes()

    # Procura o início real do RSS do Jira
    inicio = conteudo.find(b"<rss")

    if inicio == -1:
        raise ValueError(
            "Não encontrei o início <rss> da exportação do Jira."
        )

    # Procura o fechamento do RSS
    fim = conteudo.rfind(b"</rss>")

    if fim == -1:
        raise ValueError(
            "Encontrei o início do XML, mas não encontrei </rss>."
        )

    # Inclui o próprio </rss>
    fim += len(b"</rss>")

    # Mantém somente o XML verdadeiro
    conteudo_xml = conteudo[inicio:fim]

    # Corrige "&" não escapados gerados nas URLs.
    # Mantém entidades XML válidas como:
    # &amp; &lt; &gt; &quot; &apos; &#123;
    conteudo_xml = re.sub(
        rb'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)',
        b'&amp;',
        conteudo_xml
    )

    try:
        raiz = ET.fromstring(conteudo_xml)

    except ET.ParseError as erro:
        raise ValueError(
            f"O XML do Jira foi localizado, mas contém erro: {erro}"
        ) from erro

    chamados = []

    for item in raiz.findall(".//item"):
        chamados.append(
            extrair_chamado(item)
        )

    return chamados


if __name__ == "__main__":
    print("parser_xml.py carregado com sucesso.")
