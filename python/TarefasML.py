# TarefasML.py — tarefas de aprendizado e relatórios (usadas pelo AgendadorSGC)

import os

from CorrecaoFeedback import ClCorrecaoFeedback
from DbMigracao import ClDbMigracao
from ML import ClML
from RelatorioAssertividade import ClRelatorioAssertividade
from RelatorioFeedback import ClRelatorioFeedback
from logger import ClLog
from trade import ClTrade


def _note_job(job_id: str, ok: bool, message: str = "") -> None:
    try:
        from SchedulerHeartbeat import note_job

        note_job(job_id, ok, message)
    except Exception:
        pass


def _credenciais_glpi():
    """Mantido por compatibilidade; conexão GLPI usa conf/glpi.dat via ClTrade()."""
    return {}


def garantir_tabelas_fase3() -> bool:
    return ClDbMigracao().aplicar_fase3()


def executar_detectar_correcoes() -> int:
    logger = ClLog()
    garantir_tabelas_fase3()
    corr = ClCorrecaoFeedback()
    total = corr.detectar_e_gravar()
    logger.registrarActionLog(
        "AGENDADOR",
        "CORRECAO",
        f"CORREÇÕES: {corr.ultimo_total_detectado} DETECTADAS | {total} GRAVADAS",
    )
    _note_job(
        "correcoes",
        True,
        f"{corr.ultimo_total_detectado} detectadas | {total} gravadas",
    )
    return total


def executar_retreino_diario(forcar_implantacao: bool = False) -> bool:
    logger = ClLog()
    meses = int(os.getenv("ML_FEEDBACK_MESES", "6"))
    forcar = forcar_implantacao or os.getenv("ML_FORCAR_IMPLANTACAO", "").lower() in ("1", "true", "yes")

    if not garantir_tabelas_fase3():
        logger.registrarActionLog("AGENDADOR", "AVISO", "TABELAS FASE 3 NÃO VERIFICADAS")

    try:
        trade = ClTrade()
    except Exception as e:
        logger.registarExceptionLog("AGENDADOR", "EXCEPTION", "FALHA CONEXÃO GLPI NO RE-TREINO", e)
        _note_job("retreino_diario", False, "Falha conexão GLPI")
        return False

    executar_detectar_correcoes()

    clml = ClML()
    ok = clml.geracao_automatica_modelo(
        trade=trade,
        meses_feedback=meses,
        sincronizar_feedback=True,
        forcar_implantacao=forcar,
    )

    if ok:
        msg = (
            f"F1: {clml.ultimo_f1_macro} | "
            f"SYNC: {clml.ultimos_feedback_sync} | TREINO: {clml.ultimos_feedback_treino}"
        )
        logger.registrarActionLog("AGENDADOR", "RETREINO", f"RE-TREINO OK | {msg}")
        _note_job("retreino_diario", True, msg)
    else:
        logger.registrarActionLog("AGENDADOR", "AVISO", "RE-TREINO NÃO IMPLANTOU MODELO")
        _note_job("retreino_diario", False, "Não implantou modelo")

    return ok


def executar_relatorio_assertividade() -> str:
    logger = ClLog()
    dias = int(os.getenv("RELATORIO_DIAS_ATRASO", "2"))
    rel = ClRelatorioAssertividade(dias_atraso_atribuicao=dias)
    caminho = rel.gerar_relatorio_pdf()
    logger.registrarActionLog("AGENDADOR", "RELATORIO", f"PDF ASSERTIVIDADE: {caminho}")
    _note_job("relatorio_assertividade", True, str(caminho)[-220:])
    return caminho


def executar_relatorio_feedback() -> str:
    logger = ClLog()
    rel = ClRelatorioFeedback()
    caminho = rel.gerar_txt()
    logger.registrarActionLog("AGENDADOR", "RELATORIO", f"RELATÓRIO FEEDBACK: {caminho}")
    _note_job("relatorio_feedback", True, str(caminho)[-220:])
    return caminho
