"""Base local de contatos e links de conversas do Google Chat."""

import csv
import json
import re
import unicodedata
from pathlib import Path


PADRAO_EMAIL = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)


def normalizar_nome(nome):
    texto = unicodedata.normalize("NFKD", str(nome or ""))
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return " ".join(texto.casefold().split())


def carregar_base(caminho):
    caminho = Path(caminho)

    if not caminho.exists():
        return {"contatos": {}}

    with caminho.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    if not isinstance(dados.get("contatos"), dict):
        return {"contatos": {}}

    return dados


def salvar_base(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def carregar_contatos_csv(caminho):
    caminho = Path(caminho)

    if not caminho.exists():
        return {}

    contatos = {}

    with caminho.open("r", encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)

        for linha in leitor:
            nome = " ".join(
                str(linha.get(campo, "")).strip()
                for campo in ("First Name", "Middle Name", "Last Name")
                if str(linha.get(campo, "")).strip()
            )

            for campo, valor in linha.items():
                if not campo or "e-mail" not in campo.casefold():
                    continue
                if not campo.casefold().endswith("- value"):
                    continue

                for email in extrair_emails_corporativos(valor):
                    contatos[email] = nome

    return contatos


def extrair_emails(valor):
    return {
        email.casefold()
        for email in PADRAO_EMAIL.findall(str(valor or ""))
    }


def _extrair_emails_de_valor(valor):
    if isinstance(valor, dict):
        emails = set()
        for item in valor.values():
            emails.update(_extrair_emails_de_valor(item))
        return emails

    if isinstance(valor, (list, tuple, set)):
        emails = set()
        for item in valor:
            emails.update(_extrair_emails_de_valor(item))
        return emails

    return extrair_emails(valor)


def atualizar_base(caminho_base, caminho_csv, chamados):
    dados = carregar_base(caminho_base)
    registros = dados["contatos"]
    alterado = False

    contatos_csv = carregar_contatos_csv(caminho_csv)
    emails_xml = _extrair_emails_de_valor(chamados)

    for email in sorted(set(contatos_csv) | emails_xml):
        novo_contato = email not in registros
        registro = registros.setdefault(email, {"nome": "", "url_chat": ""})
        nome = contatos_csv.get(email, "")

        if novo_contato:
            alterado = True

        if nome and registro.get("nome") != nome:
            registro["nome"] = nome
            alterado = True

        if "url_chat" not in registro:
            registro["url_chat"] = ""
            alterado = True

    if alterado or not Path(caminho_base).exists():
        salvar_base(caminho_base, dados)

    return dados


def localizar_contato_por_nome(dados, nome):
    nome_normalizado = normalizar_nome(nome)

    if not nome_normalizado:
        return None

    encontrados = [
        (email, registro)
        for email, registro in dados.get("contatos", {}).items()
        if normalizar_nome(registro.get("nome")) == nome_normalizado
    ]

    if len(encontrados) != 1:
        return None

    email, registro = encontrados[0]
    return {"email": email, **registro}
