import xml.etree.ElementTree as ET

import pytest

from parser_xml import (
    analisar_historico_equipes,
    extrair_campos_customizados,
    ler_xml,
    localizar_entrada_helpdesk,
    texto,
)


def test_texto_retorna_valor_limpo_ou_padrao():
    item = ET.fromstring("<item><resumo>  Acesso  </resumo></item>")

    assert texto(item, "resumo") == "Acesso"
    assert texto(item, "status", "Aberto") == "Aberto"


def test_extrair_campos_customizados_prioriza_displayname():
    item = ET.fromstring(
        """
        <item>
          <customfields>
            <customfield>
              <customfieldname>Aprovadores</customfieldname>
              <customfieldvalues>
                <customfieldvalue displayname="Ana Silva">ana.silva</customfieldvalue>
              </customfieldvalues>
            </customfield>
          </customfields>
        </item>
        """
    )

    assert extrair_campos_customizados(item) == {"Aprovadores": ["Ana Silva"]}


def test_localizar_entrada_helpdesk_prioriza_data_de_encaminhamento():
    campos = {"Data Encaminhamento": ["Mon, 14 Sep 2026 10:00:00 -0300"]}
    comentarios = [
        {
            "criado": "Mon, 14 Sep 2026 09:00:00 -0300",
            "texto": "Atendimento iniciado pelo time [Service Desk]",
        }
    ]

    assert localizar_entrada_helpdesk(campos, comentarios) == {
        "data": "Mon, 14 Sep 2026 10:00:00 -0300",
        "origem": "Data Encaminhamento",
    }


def test_analisar_historico_equipes_remove_repeticoes_consecutivas():
    campos = {
        "1º equipe": ["Service Desk"],
        "2º equipe": ["Service Desk"],
        "3º equipe": ["Infraestrutura"],
        "Time Solucionador": ["Service Desk"],
    }

    historico = analisar_historico_equipes(campos)

    assert historico["equipes"] == [
        "Service Desk",
        "Infraestrutura",
        "Service Desk",
    ]
    assert historico["passagens_helpdesk"] == 2
    assert historico["voltou_para_helpdesk"] is True
    assert historico["veio_de_outra_equipe"] is True


def test_ler_xml_ignora_conteudo_externo_e_corrige_ampersand(tmp_path):
    arquivo = tmp_path / "exportacao.xml"
    arquivo.write_bytes(
        b"conteudo antes <rss><channel><item>"
        b"<key>SERV-1</key><summary>Acesso & suporte</summary>"
        b"<status>Aberto</status></item></channel></rss> conteudo depois"
    )

    chamados = ler_xml(arquivo)

    assert len(chamados) == 1
    assert chamados[0]["chave"] == "SERV-1"
    assert chamados[0]["resumo"] == "Acesso & suporte"


def test_ler_xml_informa_arquivo_ausente(tmp_path):
    with pytest.raises(FileNotFoundError):
        ler_xml(tmp_path / "ausente.xml")
