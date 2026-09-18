from datetime import date, datetime

from chamadoflow.relatorio_diario import criar_snapshot, montar_relatorio


CENTRAL = "Service Desk"
ESPECIALISTA = "Equipe Especialista"


def _chamado(chave, fila, status="Em Atendimento", **campos):
    return {
        "chave": chave,
        "time_solucionador": fila,
        "status": status,
        **campos,
    }


def test_relatorio_mede_backlog_transferencia_finalizacao_e_reabertura():
    inicio = criar_snapshot([
        _chamado("DEMO-1", CENTRAL),
        _chamado("DEMO-2", CENTRAL, "Aguardando Aprovação"),
        _chamado("DEMO-3", ESPECIALISTA),
    ], coletado_em=datetime(2026, 9, 18, 8, 0))
    chamados_fim = [
        _chamado("DEMO-1", ESPECIALISTA),
        _chamado("DEMO-2", CENTRAL, "Reaberto", reaberto_por="Usuário", atualizado="Fri, 18 Sep 2026 15:00:00 -0300"),
        _chamado("DEMO-3", ESPECIALISTA, "Concluído", resolvido="Fri, 18 Sep 2026 16:00:00 -0300"),
    ]
    fim = criar_snapshot(chamados_fim, coletado_em=datetime(2026, 9, 18, 17, 0))

    relatorio = montar_relatorio(inicio, fim, chamados_fim, date(2026, 9, 18))

    assert relatorio["finalizados"] == 1
    assert relatorio["reabertos"] == 1
    assert relatorio["maior_saida_central"] == {
        "origem": CENTRAL,
        "destino": ESPECIALISTA,
        "quantidade": 1,
    }
    assert f"{CENTRAL} → {ESPECIALISTA}: 1." in relatorio["texto"]
    assert "DEMO-1" not in relatorio["texto"]
