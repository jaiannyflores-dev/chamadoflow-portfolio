"""Cálculos e persistência do relatório operacional diário.

O módulo compara duas fotografias da operação. As chaves dos chamados são
mantidas somente no histórico local para permitir a comparação de filas e não
aparecem no texto gerado.
"""

from __future__ import annotations

import json
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path


STATUS_FINAIS = frozenset({"cancelado", "finalizado", "concluido", "fechado"})
STATUS_APROVACAO = "aguardando aprovacao"


def _normalizar(valor):
    texto = str(valor or "").strip().casefold()
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    )


def _data_xml(valor):
    if not valor:
        return None
    try:
        return parsedate_to_datetime(str(valor))
    except (TypeError, ValueError):
        return None


def _chave_data(valor):
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def _fila_atual(chamado):
    return str(
        chamado.get("time_solucionador")
        or chamado.get("fila_origem")
        or "Sem fila identificada"
    ).strip() or "Sem fila identificada"


def _esta_finalizado(status):
    return _normalizar(status) in STATUS_FINAIS


def _esta_em_aprovacao(status):
    return _normalizar(status) == STATUS_APROVACAO


def _foi_reaberto_no_periodo(chamado, data_referencia):
    if not (
        chamado.get("reaberto_por")
        or _normalizar(chamado.get("status")) == "reaberto"
    ):
        return False
    atualizado = _data_xml(chamado.get("atualizado"))
    return atualizado is not None and atualizado.date().isoformat() == data_referencia


def _foi_finalizado_no_periodo(chamado, data_referencia):
    if not _esta_finalizado(chamado.get("status")):
        return False
    resolvido = _data_xml(chamado.get("resolvido"))
    # O fallback atende exportações filtradas para conter status finais apenas
    # quando foram atingidos no período analisado.
    return resolvido is None or resolvido.date().isoformat() == data_referencia


def criar_snapshot(chamados, coletado_em=None):
    momento = coletado_em or datetime.now().astimezone()
    tickets = {}
    filas = defaultdict(lambda: {"backlog": 0, "em_aprovacao": 0})

    for chamado in chamados:
        chave = str(chamado.get("chave") or "").strip()
        if not chave:
            continue
        fila = _fila_atual(chamado)
        status = str(chamado.get("status") or "").strip()
        finalizado = _esta_finalizado(status)
        tickets[chave] = {"fila": fila, "status": status, "finalizado": finalizado}
        if not finalizado:
            filas[fila]["backlog"] += 1
            if _esta_em_aprovacao(status):
                filas[fila]["em_aprovacao"] += 1

    return {
        "coletado_em": momento.isoformat(timespec="seconds"),
        "filas": dict(filas),
        "tickets": tickets,
    }


def carregar_historico(caminho):
    caminho = Path(caminho)
    try:
        conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"versao": 1, "dias": {}}
    if not isinstance(conteudo, dict) or not isinstance(conteudo.get("dias"), dict):
        return {"versao": 1, "dias": {}}
    return {"versao": 1, "dias": conteudo["dias"]}


def salvar_historico(caminho, historico):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(caminho)


def registrar_inicio(historico, data_referencia, snapshot, sobrescrever=False):
    chave = _chave_data(data_referencia)
    dia = historico.setdefault("dias", {}).setdefault(chave, {})
    if "inicio" in dia and not sobrescrever:
        return False
    dia["inicio"] = snapshot
    return True


def registrar_fim(historico, data_referencia, snapshot):
    chave = _chave_data(data_referencia)
    historico.setdefault("dias", {}).setdefault(chave, {})["fim"] = snapshot


def ultimo_fechamento_anterior(historico, data_referencia):
    chave_atual = _chave_data(data_referencia)
    candidatos = [
        (chave, registro["fim"])
        for chave, registro in historico.get("dias", {}).items()
        if chave < chave_atual and isinstance(registro, dict) and "fim" in registro
    ]
    return max(candidatos, default=(None, None), key=lambda item: item[0])


def _percentual(variacao, base):
    return None if not base else variacao / base * 100


def _formatar_percentual(percentual):
    return "n/a" if percentual is None else f"{percentual:+.1f}%".replace(".", ",")


def _transferencias(inicio, fim):
    transferencias = Counter()
    for chave, anterior in inicio.get("tickets", {}).items():
        atual = fim.get("tickets", {}).get(chave)
        if not atual:
            continue
        origem, destino = anterior.get("fila"), atual.get("fila")
        if origem and destino and origem != destino:
            transferencias[(origem, destino)] += 1
    return transferencias


def _nome_central_atendimento(filas):
    for fila in filas:
        nome = _normalizar(fila)
        if nome.startswith("helpdesk") or nome.startswith("service desk"):
            return fila
    return None


def montar_relatorio(inicio, fim, chamados_fim, data_referencia=None, base_inicio="fotografia inicial"):
    data_relatorio = _chave_data(data_referencia or datetime.now().date())
    finalizados_por_fila = Counter(
        _fila_atual(chamado)
        for chamado in chamados_fim
        if _foi_finalizado_no_periodo(chamado, data_relatorio)
    )
    reabertos_por_fila = Counter(
        _fila_atual(chamado)
        for chamado in chamados_fim
        if _foi_reaberto_no_periodo(chamado, data_relatorio)
    )
    filas = sorted(
        set(inicio.get("filas", {})) | set(fim.get("filas", {}))
        | set(finalizados_por_fila) | set(reabertos_por_fila),
        key=str.casefold,
    )
    linhas_filas = []
    for fila in filas:
        dados_inicio = inicio.get("filas", {}).get(fila, {})
        dados_fim = fim.get("filas", {}).get(fila, {})
        backlog_inicio, backlog_fim = dados_inicio.get("backlog", 0), dados_fim.get("backlog", 0)
        variacao = backlog_fim - backlog_inicio
        linhas_filas.append({
            "fila": fila,
            "backlog_inicio": backlog_inicio,
            "backlog_fim": backlog_fim,
            "variacao": variacao,
            "percentual": _percentual(variacao, backlog_inicio),
            "aprovacao_inicio": dados_inicio.get("em_aprovacao", 0),
            "aprovacao_fim": dados_fim.get("em_aprovacao", 0),
            "finalizados": finalizados_por_fila[fila],
            "reabertos": reabertos_por_fila[fila],
        })

    transferencias_ordenadas = sorted(
        (
            {"origem": origem, "destino": destino, "quantidade": quantidade}
            for (origem, destino), quantidade in _transferencias(inicio, fim).items()
        ),
        key=lambda item: (-item["quantidade"], item["origem"].casefold(), item["destino"].casefold()),
    )
    central = _nome_central_atendimento([linha["fila"] for linha in linhas_filas])
    saidas_central = [item for item in transferencias_ordenadas if item["origem"] == central]
    maior_saida_central = saidas_central[0] if saidas_central else None
    finalizados, reabertos = sum(finalizados_por_fila.values()), sum(reabertos_por_fila.values())
    total_inicio = sum(linha["backlog_inicio"] for linha in linhas_filas)
    total_fim = sum(linha["backlog_fim"] for linha in linhas_filas)
    variacao_total = total_fim - total_inicio

    texto = [
        f"RELATÓRIO OPERACIONAL — {data_relatorio}",
        f"Base inicial: {base_inicio}.", "", "VISÃO CONSOLIDADA",
        f"• Backlog: {total_inicio} → {total_fim} ({variacao_total:+d}; {_formatar_percentual(_percentual(variacao_total, total_inicio))})",
        f"• Finalizados no período: {finalizados}",
        f"• Reabertos identificados no período: {reabertos}", "", "POR FILA",
    ]
    for linha in linhas_filas:
        texto.append(
            f"• {linha['fila']}: backlog {linha['backlog_inicio']} → {linha['backlog_fim']} "
            f"({linha['variacao']:+d}; {_formatar_percentual(linha['percentual'])}); aprovação "
            f"{linha['aprovacao_inicio']} → {linha['aprovacao_fim']}; finalizados "
            f"{linha['finalizados']}; reabertos {linha['reabertos']}."
        )

    texto.extend(["", "TRANSFERÊNCIAS IDENTIFICADAS ENTRE AS FOTOGRAFIAS"])
    if transferencias_ordenadas:
        for item in transferencias_ordenadas:
            texto.append(f"• {item['origem']} → {item['destino']}: {item['quantidade']}.")
    else:
        texto.append("• Nenhuma transferência entre filas foi identificada.")

    texto.extend(["", "ANÁLISE"])
    if maior_saida_central:
        texto.append(
            "• Maior transferência originada na central de atendimento: "
            f"{maior_saida_central['origem']} → {maior_saida_central['destino']} "
            f"({maior_saida_central['quantidade']})."
        )
    else:
        texto.append("• Não houve transferência da central de atendimento para outra fila.")
    for linha in linhas_filas:
        recebidos = sum(item["quantidade"] for item in transferencias_ordenadas if item["destino"] == linha["fila"])
        if linha["variacao"] > 0 and recebidos:
            texto.append(
                f"• {linha['fila']} aumentou {linha['variacao']} chamado(s) no backlog "
                f"e recebeu {recebidos} transferência(s) no período."
            )
    texto.append(
        "• Transferências são comparadas entre início e fim do período; movimentações "
        "intermediárias não são inferidas sem histórico datado do sistema de chamados."
    )
    return {
        "texto": "\n".join(texto),
        "filas": linhas_filas,
        "finalizados": finalizados,
        "reabertos": reabertos,
        "transferencias": transferencias_ordenadas,
        "maior_saida_central": maior_saida_central,
    }
