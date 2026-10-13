# AssertividadeMetricas.py — compara equipe classificada pelo SGC vs equipe no fechamento GLPI

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from DAL import DAL
from EquipeAssertividade import acertou_classificacao_equipe, normalizar_equipe
from logger import ClLog
from PerformanceRegistro import ClPerformanceRegistro


@dataclass
class ResumoAssertividade:
    dias_atraso_atribuicao: int
    data_referencia: str
    total_comparados: int = 0
    total_acertos: int = 0
    total_erros: int = 0
    total_pendentes_fechamento: int = 0
    total_reatribuicoes_mesma_equipe: int = 0
    taxa_assertividade: float = 0.0
    por_equipe: pd.DataFrame = field(default_factory=pd.DataFrame)
    principais_erros: pd.DataFrame = field(default_factory=pd.DataFrame)
    detalhes: pd.DataFrame = field(default_factory=pd.DataFrame)
    cobertura_feedback: dict = field(default_factory=dict)


class ClAssertividadeMetricas:
    logger = ClLog()

    SQL_COMPARACAO_DIA_REFERENCIA = """
        SELECT
            tn.Id AS id_glpi,
            tn.Titulo AS titulo,
            tn.Data AS data_atribuicao,
            UPPER(TRIM(tn.Equipe)) AS equipe_sgc,
            tn.Tecnico AS tecnico_sgc,
            fb.Tecnico AS tecnico_fechamento,
            UPPER(TRIM(ta_fim.Equipe)) AS equipe_fechamento,
            fb.Data_Fechamento AS data_fechamento,
            fb.Localizacao AS localizacao
        FROM Tb_Ticket_new tn
        INNER JOIN Tb_Ticket_Feedback_Temp fb ON fb.Id_Glpi = tn.Id
        INNER JOIN Tb_Atrib ta_fim ON UPPER(TRIM(ta_fim.Usuario)) = UPPER(TRIM(fb.Tecnico))
        WHERE DATE(tn.Data) = DATE(DATE_SUB(CURDATE(), INTERVAL %s DAY))
          AND tn.Equipe IS NOT NULL AND TRIM(tn.Equipe) <> ''
          AND ta_fim.Equipe IS NOT NULL AND TRIM(ta_fim.Equipe) <> ''
    """

    SQL_PENDENTES_FECHAMENTO = """
        SELECT COUNT(*) AS cnt
        FROM Tb_Ticket_new tn
        LEFT JOIN Tb_Ticket_Feedback_Temp fb ON fb.Id_Glpi = tn.Id
        WHERE DATE(tn.Data) = DATE(DATE_SUB(CURDATE(), INTERVAL %s DAY))
          AND fb.Id_Glpi IS NULL
    """

    def __init__(self, dal: DAL = None):
        self.dal = dal or DAL(app_name="Assertividade", nome_arquivo_config="sgc.dat")

    @staticmethod
    def _data_referencia(dias_atraso: int) -> datetime:
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=dias_atraso)

    def calcular(self, dias_atraso_atribuicao: int = 2) -> ResumoAssertividade:
        """
        Mede assertividade sobre chamados atribuídos pelo SGC na data de referência
        (padrão: 2 dias atrás) que já constam como fechados no GLPI.

        Critério de acerto: equipe classificada pelo SGC (tn.Equipe) igual à equipe
        do técnico que fechou o chamado. Reatribuição para outro membro da mesma
        equipe não conta como erro.
        """
        data_ref = self._data_referencia(dias_atraso_atribuicao)
        resumo = ResumoAssertividade(
            dias_atraso_atribuicao=dias_atraso_atribuicao,
            data_referencia=data_ref.strftime("%d/%m/%Y"),
        )
        try:
            df = self.dal.read(self.SQL_COMPARACAO_DIA_REFERENCIA, (dias_atraso_atribuicao,))
            pendentes = self.dal.read(self.SQL_PENDENTES_FECHAMENTO, (dias_atraso_atribuicao,))
            if pendentes is not None and not pendentes.empty:
                resumo.total_pendentes_fechamento = int(pendentes.iloc[0].get("cnt") or 0)

            if df is None or df.empty:
                resumo.cobertura_feedback = self._cobertura_feedback()
                ClPerformanceRegistro(dal=self.dal).registrar(0.0, resumo.data_referencia)
                return resumo

            df = df.copy()
            df["equipe_sgc"] = df["equipe_sgc"].map(normalizar_equipe)
            df["equipe_fechamento"] = df["equipe_fechamento"].map(normalizar_equipe)
            df = df[(df["equipe_sgc"] != "") & (df["equipe_fechamento"] != "")]
            df["acerto"] = df.apply(
                lambda row: acertou_classificacao_equipe(row["equipe_sgc"], row["equipe_fechamento"]),
                axis=1,
            )
            tec_sgc = df["tecnico_sgc"].astype(str).str.strip().str.upper()
            tec_fim = df["tecnico_fechamento"].astype(str).str.strip().str.upper()
            df["reatribuicao_mesma_equipe"] = df["acerto"] & (tec_sgc != tec_fim)

            resumo.total_comparados = len(df)
            resumo.total_acertos = int(df["acerto"].sum())
            resumo.total_erros = resumo.total_comparados - resumo.total_acertos
            resumo.total_reatribuicoes_mesma_equipe = int(df["reatribuicao_mesma_equipe"].sum())
            resumo.taxa_assertividade = (
                (resumo.total_acertos / resumo.total_comparados * 100) if resumo.total_comparados else 0.0
            )
            resumo.detalhes = df.sort_values("data_fechamento", ascending=False)

            por_eq = df.groupby("equipe_sgc").agg(
                total=("acerto", "count"),
                acertos=("acerto", "sum"),
            ).reset_index()
            por_eq["taxa_pct"] = (por_eq["acertos"] / por_eq["total"] * 100).round(1)
            por_eq = por_eq.sort_values("total", ascending=False)
            resumo.por_equipe = por_eq

            erros = df[~df["acerto"]].copy()
            if not erros.empty:
                erros["par_erro"] = erros["equipe_sgc"] + " → " + erros["equipe_fechamento"]
                resumo.principais_erros = (
                    erros.groupby(["equipe_sgc", "equipe_fechamento", "par_erro"])
                    .size()
                    .reset_index(name="quantidade")
                    .sort_values("quantidade", ascending=False)
                    .head(15)
                )

            resumo.cobertura_feedback = self._cobertura_feedback()
            ClPerformanceRegistro(dal=self.dal).registrar(
                resumo.taxa_assertividade,
                resumo.data_referencia,
            )
            return resumo
        except Exception as e:
            self.logger.registarExceptionLog("ASSERTIVIDADE", "EXCEPTION", "FALHA AO CALCULAR MÉTRICAS", e)
            return resumo

    def _cobertura_feedback(self) -> dict:
        sql = """
            SELECT
                COUNT(*) AS total_feedback,
                SUM(CASE WHEN Equipe IS NOT NULL AND TRIM(Equipe) <> '' THEN 1 ELSE 0 END) AS com_equipe,
                COUNT(DISTINCT UPPER(TRIM(Equipe))) AS equipes_distintas
            FROM Tb_Ticket_Feedback_Temp
        """
        df = self.dal.read(sql)
        if df is None or df.empty:
            return {"total_feedback": 0, "com_equipe": 0, "equipes_distintas": 0}
        row = df.iloc[0]
        return {
            "total_feedback": int(row.get("total_feedback") or 0),
            "com_equipe": int(row.get("com_equipe") or 0),
            "equipes_distintas": int(row.get("equipes_distintas") or 0),
        }
