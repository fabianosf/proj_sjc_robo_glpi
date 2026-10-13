# RelatorioFeedback.py — cobertura de feedback e gaps operacionais (Fase 3)

from datetime import datetime
from pathlib import Path

import pandas as pd

from DAL import DAL
from DbMigracao import ClDbMigracao
from logger import ClLog
from paths import RELATORIOS_DIR

RELATORIO_DIR = RELATORIOS_DIR


class ClRelatorioFeedback:
    logger = ClLog()

    def __init__(self, dal: DAL = None):
        self.dal = dal or DAL(app_name="RelatorioFeedback", nome_arquivo_config="sgc.dat")

    def gerar_resumo(self) -> dict:
        ClDbMigracao(dal=self.dal).aplicar_fase3()
        resumo = {
            "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "total_feedback": 0,
            "por_equipe": pd.DataFrame(),
            "tecnicos_sem_equipe": pd.DataFrame(),
            "total_correcoes": 0,
            "total_ml_log": 0,
            "ml_log_por_metodo": pd.DataFrame(),
        }

        fb = self.dal.read("SELECT COUNT(*) AS cnt FROM Tb_Ticket_Feedback_Temp")
        resumo["total_feedback"] = int(fb.iloc[0]["cnt"]) if fb is not None and not fb.empty else 0

        por_eq = self.dal.read("""
            SELECT UPPER(TRIM(Equipe)) AS equipe, COUNT(*) AS total
            FROM Tb_Ticket_Feedback_Temp
            WHERE Equipe IS NOT NULL AND TRIM(Equipe) <> ''
            GROUP BY UPPER(TRIM(Equipe))
            ORDER BY total DESC
        """)
        resumo["por_equipe"] = por_eq if por_eq is not None else pd.DataFrame()

        sem_eq = self.dal.read("""
            SELECT DISTINCT UPPER(TRIM(fb.Tecnico)) AS tecnico, COUNT(*) AS chamados
            FROM Tb_Ticket_Feedback_Temp fb
            LEFT JOIN Tb_Atrib ta ON UPPER(TRIM(ta.Usuario)) = UPPER(TRIM(fb.Tecnico))
            WHERE fb.Tecnico IS NOT NULL AND TRIM(fb.Tecnico) <> ''
              AND (ta.Equipe IS NULL OR TRIM(ta.Equipe) = '')
            GROUP BY UPPER(TRIM(fb.Tecnico))
            ORDER BY chamados DESC
            LIMIT 30
        """)
        resumo["tecnicos_sem_equipe"] = sem_eq if sem_eq is not None else pd.DataFrame()

        cor = self.dal.read("SELECT COUNT(*) AS cnt FROM Tb_Correcao_Feedback")
        resumo["total_correcoes"] = int(cor.iloc[0]["cnt"]) if cor is not None and not cor.empty else 0

        if self._tabela_existe("Tb_ML_Log"):
            ml = self.dal.read("SELECT COUNT(*) AS cnt FROM Tb_ML_Log")
            resumo["total_ml_log"] = int(ml.iloc[0]["cnt"]) if ml is not None and not ml.empty else 0

            met = self.dal.read("""
                SELECT Metodo, COUNT(*) AS total
                FROM Tb_ML_Log
                GROUP BY Metodo
                ORDER BY total DESC
            """)
            resumo["ml_log_por_metodo"] = met if met is not None else pd.DataFrame()

        return resumo

    def _tabela_existe(self, tabela: str) -> bool:
        df = self.dal.read("SHOW TABLES LIKE %s", (tabela,))
        return df is not None and not df.empty

    def gerar_txt(self) -> str:
        RELATORIO_DIR.mkdir(parents=True, exist_ok=True)
        caminho = RELATORIO_DIR / f"Feedback_Cobertura_{datetime.now().strftime('%Y%m%d')}.txt"
        r = self.gerar_resumo()

        linhas = [
            "RELATÓRIO DE COBERTURA — FEEDBACK ML (Fase 3)",
            f"Gerado em: {r['data']}",
            "",
            f"Total feedback GLPI      : {r['total_feedback']}",
            f"Correções detectadas     : {r['total_correcoes']}",
            f"Registros Tb_ML_Log      : {r['total_ml_log']}",
            "",
            "— Cobertura por equipe (feedback) —",
        ]

        if r["por_equipe"].empty:
            linhas.append("  (vazio)")
        else:
            for _, row in r["por_equipe"].iterrows():
                linhas.append(f"  {row['equipe']:>4} : {int(row['total'])}")

        linhas.extend(["", "— Técnicos GLPI sem equipe em Tb_Atrib —"])
        if r["tecnicos_sem_equipe"].empty:
            linhas.append("  (nenhum)")
        else:
            for _, row in r["tecnicos_sem_equipe"].iterrows():
                linhas.append(f"  {row['tecnico']:<25} {int(row['chamados'])} chamado(s)")

        if not r["ml_log_por_metodo"].empty:
            linhas.extend(["", "— Decisões por método (Tb_ML_Log) —"])
            for _, row in r["ml_log_por_metodo"].iterrows():
                linhas.append(f"  {row['Metodo']:<20} {int(row['total'])}")

        conteudo = "\n".join(linhas)
        caminho.write_text(conteudo, encoding="utf-8")
        self.logger.registrarActionLog("RELATORIO", "ATIVIDADE", f"RELATÓRIO FEEDBACK: {caminho}")
        return str(caminho)
