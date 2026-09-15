from chamadoflow.contatos import (
    atualizar_base,
    extrair_emails,
    localizar_contato_por_nome,
)


def test_extrair_emails_reconhece_dominios_validos():
    texto = "Falar com ANA.SILVA@empresa.com ou externo@exemplo.com."

    assert extrair_emails(texto) == {"ana.silva@empresa.com", "externo@exemplo.com"}


def test_atualizar_base_mescla_csv_xml_e_preserva_link(tmp_path):
    arquivo_csv = tmp_path / "contacts.csv"
    arquivo_csv.write_text(
        "First Name,Middle Name,Last Name,E-mail 1 - Value\n"
        "Ana,,Silva,ana.silva@empresa.com\n",
        encoding="utf-8",
    )
    arquivo_base = tmp_path / "contatos_chat.json"
    arquivo_base.write_text(
        '{"contatos": {"ana.silva@empresa.com": '
        '{"nome": "", "url_chat": "https://chat.google.com/app/chat/abc"}}}',
        encoding="utf-8",
    )

    dados = atualizar_base(
        arquivo_base,
        arquivo_csv,
        [{"comentarios": [{"texto": "novo@empresa.com"}]}],
    )

    assert dados["contatos"]["ana.silva@empresa.com"] == {
        "nome": "Ana Silva",
        "url_chat": "https://chat.google.com/app/chat/abc",
    }
    assert dados["contatos"]["novo@empresa.com"]["nome"] == ""


def test_localizar_contato_por_nome_exige_resultado_unico():
    dados = {
        "contatos": {
            "ana.silva@empresa.com": {"nome": "Ana Silva", "url_chat": ""},
            "outra@empresa.com": {"nome": "Ana Silva", "url_chat": ""},
        }
    }

    assert localizar_contato_por_nome(dados, "Ana Silva") is None
