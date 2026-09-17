"""Gera planilhas Excel com os chamados analisados."""

from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


COLUNAS_EXPORTACAO = (
    ("Fila(s)", "filas"),
    ("Chamado", "chave"),
    ("Resumo", "resumo"),
    ("Prioridade", "prioridade"),
    ("Status Jira", "status_jira"),
    ("Responsável", "responsavel"),
    ("Sem atualização", "horas_sem_atualizacao"),
    ("Situação", "situacao"),
    ("Quem precisa agir", "quem_precisa_agir"),
    ("O que fazer agora", "acao_final"),
    ("Strike atual", "strike_atual"),
    ("Próximo strike", "proximo_strike"),
    ("Elegível para strike", "elegivel_strike"),
    ("VIP", "vip"),
    ("SLA estourado", "sla_estourado"),
    ("Validação manual", "requer_validacao_manual"),
    ("Confiança", "confianca"),
)

_NAMESPACE_PLANILHA = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_CARACTERES_INVALIDOS_ABA = set("[]:*?/\\")


def _texto_seguro(valor):
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, float):
        return f"{valor:.1f}".replace(".", ",")

    texto = str(valor)
    return "".join(
        caractere
        for caractere in texto
        if caractere in "\t\n\r" or ord(caractere) >= 32
    )


def _nome_aba(nome, nomes_usados):
    base = "".join(
        " " if caractere in _CARACTERES_INVALIDOS_ABA else caractere
        for caractere in _texto_seguro(nome)
    ).strip() or "Sem fila"
    base = base[:31]
    candidato = base
    indice = 2

    while candidato.casefold() in nomes_usados:
        sufixo = f" ({indice})"
        candidato = f"{base[:31 - len(sufixo)]}{sufixo}"
        indice += 1

    nomes_usados.add(candidato.casefold())
    return candidato


def _referencia_coluna(indice):
    referencia = ""
    while indice:
        indice, resto = divmod(indice - 1, 26)
        referencia = chr(65 + resto) + referencia
    return referencia


def _criar_planilha_xml(linhas):
    planilha = ET.Element("worksheet", xmlns=_NAMESPACE_PLANILHA)
    vistas_planilha = ET.SubElement(planilha, "sheetViews")
    vista_planilha = ET.SubElement(
        vistas_planilha,
        "sheetView",
        workbookViewId="0",
    )
    vista_planilha.append(
        ET.Element("pane", ySplit="1", topLeftCell="A2", state="frozen")
    )
    colunas = ET.SubElement(planilha, "cols")
    for indice, (titulo, _) in enumerate(COLUNAS_EXPORTACAO, start=1):
        largura = min(max(len(titulo) + 2, 14), 24)
        ET.SubElement(
            colunas,
            "col",
            min=str(indice),
            max=str(indice),
            width=str(largura),
            customWidth="1",
        )

    dados = ET.SubElement(planilha, "sheetData")
    for numero_linha, linha in enumerate(linhas, start=1):
        linha_xml = ET.SubElement(dados, "row", r=str(numero_linha))
        for indice, valor in enumerate(linha, start=1):
            celula = ET.SubElement(
                linha_xml,
                "c",
                r=f"{_referencia_coluna(indice)}{numero_linha}",
                t="inlineStr",
                s="1" if numero_linha == 1 else "0",
            )
            texto = ET.SubElement(celula, "is")
            ET.SubElement(texto, "t").text = _texto_seguro(valor)

    ultima_coluna = _referencia_coluna(len(COLUNAS_EXPORTACAO))
    ET.SubElement(planilha, "autoFilter", ref=f"A1:{ultima_coluna}{len(linhas)}")
    return ET.tostring(planilha, encoding="utf-8", xml_declaration=True)


def _linhas_exportacao(resultados, chamados_por_chave):
    cabecalho = [titulo for titulo, _ in COLUNAS_EXPORTACAO]
    linhas = [cabecalho]
    for resultado in resultados:
        chamado = chamados_por_chave.get(resultado.get("chave"), {})
        valores = []
        for _, campo in COLUNAS_EXPORTACAO:
            if campo == "filas":
                valor = chamado.get("fila_origem") or resultado.get("fila_origem")
            elif campo == "horas_sem_atualizacao":
                horas = resultado.get(campo)
                valor = (
                    "Não identificado"
                    if horas is None
                    else f"{horas:.1f} h".replace(".", ",")
                )
            else:
                valor = resultado.get(campo)
            valores.append(valor)
        linhas.append(valores)
    return linhas


def exportar_filas_para_excel(caminho, resultados, chamados_por_chave, filas_por_chave):
    """Cria um XLSX com uma aba consolidada e outra para cada fila."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    nomes_usados = set()
    abas = [("Consolidado", list(resultados))]

    for fila in sorted(filas_por_chave, key=str.casefold):
        chaves = set(filas_por_chave[fila])
        abas.append(
            (fila, [resultado for resultado in resultados if resultado.get("chave") in chaves])
        )

    nomes_abas = [_nome_aba(nome, nomes_usados) for nome, _ in abas]
    with ZipFile(caminho, "w", compression=ZIP_DEFLATED) as arquivo:
        arquivo.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>"""
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{indice}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for indice in range(1, len(abas) + 1)
            )
            + "</Types>",
        )
        arquivo.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        arquivo.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>"""
            + "".join(
                f'<sheet name="{escape(nome, {"\"": "&quot;"})}" sheetId="{indice}" r:id="rId{indice}"/>'
                for indice, nome in enumerate(nomes_abas, start=1)
            )
            + "</sheets></workbook>",
        )
        arquivo.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">"""
            + "".join(
                f'<Relationship Id="rId{indice}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{indice}.xml"/>'
                for indice in range(1, len(abas) + 1)
            )
            + f'<Relationship Id="rId{len(abas) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            + "</Relationships>",
        )
        arquivo.writestr(
            "xl/styles.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border/></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>""",
        )
        for indice, (_, resultados_aba) in enumerate(abas, start=1):
            arquivo.writestr(
                f"xl/worksheets/sheet{indice}.xml",
                _criar_planilha_xml(_linhas_exportacao(resultados_aba, chamados_por_chave)),
            )

    return caminho
