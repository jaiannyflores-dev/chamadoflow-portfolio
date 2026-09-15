from datetime import datetime
from zoneinfo import ZoneInfo

from rules import (
    analisar_estado_contato,
    analisar_sla,
    analisar_strike,
    analisar_tempo,
    avaliar_elegibilidade_strike,
    classificar_motivo,
    converter_data,
    identificar_vip,
)


FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")


def test_converter_data_retorna_none_para_valor_invalido():
    assert converter_data("data inválida") is None


def test_analisar_tempo_usa_referencia_injetada():
    chamado = {
        "entrada_helpdesk": "Mon, 14 Sep 2026 08:00:00 -0300",
        "atualizado": "Mon, 14 Sep 2026 09:00:00 -0300",
        "status": "Aberto",
    }
    agora = datetime(2026, 9, 14, 11, tzinfo=FUSO_BRASILIA)

    analise = analisar_tempo(chamado, agora)

    assert analise["horas_na_fila"] == 3
    assert analise["horas_sem_atualizacao"] == 2
    assert analise["precisa_analisar"] is True


def test_analisar_sla_conta_apenas_horario_comercial_em_dias_uteis():
    chamado = {"criado": "Fri, 11 Sep 2026 17:00:00 -0300"}
    agora = datetime(2026, 9, 14, 8, tzinfo=FUSO_BRASILIA)

    sla = analisar_sla(chamado, agora)

    assert sla["horas_uteis_desde_criacao"] == 2
    assert sla["sla_estourado"] is False


def test_analisar_sla_estoura_somente_acima_de_tres_dias_uteis():
    chamado = {"criado": "Mon, 7 Sep 2026 07:00:00 -0300"}
    agora = datetime(2026, 9, 10, 7, 1, tzinfo=FUSO_BRASILIA)

    sla = analisar_sla(chamado, agora)

    assert sla["horas_uteis_desde_criacao"] == 33 + (1 / 60)
    assert sla["sla_estourado"] is True


def test_identificar_vip_exige_o_marcador_no_resumo():
    assert identificar_vip({"resumo": "[vip] Falha no acesso"}) is True
    assert identificar_vip({"resumo": "Cliente vip sem marcador"}) is False


def test_classificar_motivo_reconhece_aprovacao_recebida():
    chamado = {
        "status": "Aguardando Aprovação",
        "ultimo_comentario": {"texto": "Aprovado"},
        "resumo": "Liberação de acesso",
    }

    assert classificar_motivo(chamado) == "Aprovação recebida - cobrar andamento"


def test_analisar_strike_prioriza_maior_strike_com_data_de_comentario():
    chamado = {
        "resumo": "{Strike 1} Solicitação de acesso",
        "comentarios": [
            {"texto": "Aplicado Strike 2", "criado": "Mon, 14 Sep 2026 10:00:00 -0300"},
            {"texto": "Novo Strike 1", "criado": "Mon, 14 Sep 2026 09:00:00 -0300"},
        ],
    }

    assert analisar_strike(chamado) == {
        "strike_atual": 2,
        "possui_strike": True,
        "proximo_strike": 3,
        "limite_atingido": False,
        "data_ultimo_strike": "Mon, 14 Sep 2026 10:00:00 -0300",
        "origem_ultimo_strike": "Comentário",
    }


def test_analisar_estado_contato_prioriza_falha_sobre_contato():
    chamado = {
        "comentarios": [
            {"texto": "Realizando tentativa, mas não obtivemos retorno."},
        ]
    }
    analise_acao = {"situacao": "Aguardando demandante", "quem_precisa_agir": "Demandante"}

    contato = analisar_estado_contato(chamado, analise_acao)

    assert contato == {
        "estado_contato": "Falha de contato identificada",
        "alvo_contato": "Demandante",
        "falha_contato": True,
        "contato_identificado": True,
    }


def test_elegibilidade_bloqueia_strike_para_situacao_operacional():
    chamado = {"resumo": "Solicitação", "comentarios": []}
    analise_acao = {"situacao": "HelpDesk precisa continuar"}

    elegibilidade = avaliar_elegibilidade_strike(chamado, analise_acao)

    assert elegibilidade["elegivel_strike"] is False
    assert elegibilidade["acao_strike"] == "Não aplicar Strike"
    assert elegibilidade["requer_validacao_manual"] is False
