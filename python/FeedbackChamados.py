# FeedbackChamados.py
# Importa chamados FECHADOS do GLPI para Tb_Ticket_Feedback_Temp.
# O GLPI informa o técnico (login); a equipe é resolvida pela aplicação via Tb_Atrib.

from datetime import datetime, timedelta

import pandas as pd

from DAL import DAL
from DbMigracao import ClDbMigracao
from logger import ClLog
from paths import SQL_DIR

SQL_CRIAR_TABELA = (SQL_DIR / "criar_Tb_Ticket_Feedback_Temp.sql").read_text(encoding="utf-8")

SQL_UPSERT = """
INSERT INTO Tb_Ticket_Feedback_Temp
    (Id_Glpi, Titulo, Categoria, Descricao, Localizacao, Tecnico, Equipe, Data_Abertura, Data_Fechamento, Data_Sync)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    Titulo = VALUES(Titulo),
    Categoria = VALUES(Categoria),
    Descricao = VALUES(Descricao),
    Localizacao = VALUES(Localizacao),
    Tecnico = VALUES(Tecnico),
    Equipe = VALUES(Equipe),
    Data_Abertura = VALUES(Data_Abertura),
    Data_Fechamento = VALUES(Data_Fechamento),
    Data_Sync = VALUES(Data_Sync)
"""


class ClFeedbackChamados:
    logger = ClLog()

    def __init__(self, trade, dal: DAL = None):
        self.trade = trade
        self.dal = dal or DAL(app_name="Feedback_GLPI", nome_arquivo_config="sgc.dat")
        self._mapa_equipe = {}
        self._ultimo_total_glpi = 0
        self._ultimo_total_gravados = 0
        self._ultimo_total_com_equipe = 0

    @property
    def ultimo_total_glpi(self):
        return self._ultimo_total_glpi

    @property
    def ultimo_total_gravados(self):
        return self._ultimo_total_gravados

    @property
    def ultimo_total_com_equipe(self):
        return self._ultimo_total_com_equipe

    def criar_tabela_se_necessario(self) -> bool:
        try:
            self.dal.create(SQL_CRIAR_TABELA)
            self.logger.registrarActionLog("FEEDBACK", "ATIVIDADE", "TABELA Tb_Ticket_Feedback_Temp VERIFICADA/CRIADA")
            return True
        except Exception as e:
            self.logger.registarExceptionLog("FEEDBACK", "EXCEPTION", "FALHA AO CRIAR TABELA FEEDBACK", e)
            return False

    def _carregar_mapa_equipes(self):
        sql = """
            SELECT UPPER(TRIM(Usuario)) AS Usuario, UPPER(TRIM(Equipe)) AS Equipe
            FROM Tb_Atrib
            WHERE TRIM(Equipe) <> ''
        """
        df = self.dal.read(sql)
        if df is None or df.empty:
            self._mapa_equipe = {}
            return
        self._mapa_equipe = dict(zip(df["Usuario"], df["Equipe"]))

    def _resolver_equipe(self, login_tecnico: str) -> str:
        if not login_tecnico:
            return ""
        chave = login_tecnico.strip().upper().replace(" ", ".")
        return self._mapa_equipe.get(chave, "")

    @staticmethod
    def _truncar(titulo, categoria, descricao):
        return (
            str(titulo)[:500],
            str(categoria)[:500],
            str(descricao)[:2500],
        )

    def _limpar_registros_antigos(self, meses: int):
        limite = datetime.now() - timedelta(days=meses * 30)
        sql = "DELETE FROM Tb_Ticket_Feedback_Temp WHERE Data_Fechamento IS NOT NULL AND Data_Fechamento < %s"
        self.dal.delete(sql, (limite.strftime("%Y-%m-%d %H:%M:%S"),))

    def sincronizar_glpi(self, meses: int = 6) -> int:
        """
        Importa chamados fechados do GLPI dos últimos N meses.
        Grava título, categoria, descrição e técnico; a equipe é mapeada via Tb_Atrib.
        """
        gravados = 0
        com_equipe = 0
        try:
            if not self.criar_tabela_se_necessario():
                return 0

            ClDbMigracao(dal=self.dal).aplicar_migracao_ambiente()

            self._carregar_mapa_equipes()
            if not self._mapa_equipe:
                self.logger.registrarActionLog("FEEDBACK", "AVISO", "MAPA DE EQUIPES (Tb_Atrib) VAZIO")

            self._limpar_registros_antigos(meses)

            df = self.trade.pesquisarChamadosFechadosPeriodo(meses=meses)
            if df is None or df.empty:
                self.logger.registrarActionLog("FEEDBACK", "AVISO", "NENHUM CHAMADO FECHADO RETORNADO PELO GLPI")
                self._ultimo_total_glpi = 0
                self._ultimo_total_gravados = 0
                self._ultimo_total_com_equipe = 0
                return 0

            self._ultimo_total_glpi = len(df)
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for _, row in df.iterrows():
                titulo, categoria, descricao = self._truncar(
                    row.get("Titulo", ""),
                    row.get("Categoria", ""),
                    row.get("Descricao", ""),
                )
                tecnico = str(row.get("Tecnico", "") or "").strip()[:20]
                equipe = self._resolver_equipe(tecnico)
                if equipe:
                    com_equipe += 1

                localizacao = str(row.get("Localizacao", "") or "")[:500]

                params = (
                    int(row["ID"]),
                    titulo,
                    categoria,
                    descricao,
                    localizacao or None,
                    tecnico or None,
                    equipe or None,
                    row.get("Data_Abertura"),
                    row.get("Data_Fechamento"),
                    agora,
                )

                if self.dal.create(SQL_UPSERT, params):
                    gravados += 1

            self._ultimo_total_gravados = gravados
            self._ultimo_total_com_equipe = com_equipe
            self.logger.registrarActionLog(
                "FEEDBACK",
                "ATIVIDADE",
                (
                    f"SYNC GLPI: {len(df)} CHAMADOS | GRAVADOS: {gravados} | "
                    f"COM EQUIPE: {com_equipe} | PERÍODO: {meses} MESES"
                ),
            )
            return gravados
        except Exception as e:
            self.logger.registarExceptionLog("FEEDBACK", "EXCEPTION", "FALHA NA SINCRONIZAÇÃO FEEDBACK GLPI", e)
            return gravados

    def contar_registros_treino(self) -> int:
        sql = """
            SELECT COUNT(*) AS cnt
            FROM Tb_Ticket_Feedback_Temp fb
            INNER JOIN Tb_Atrib ta ON UPPER(TRIM(ta.Usuario)) = UPPER(TRIM(fb.Tecnico))
            WHERE fb.Tecnico IS NOT NULL AND TRIM(fb.Tecnico) <> ''
              AND ta.Equipe IS NOT NULL AND TRIM(ta.Equipe) <> ''
        """
        df = self.dal.read(sql)
        if df is None or df.empty:
            return 0
        return int(df.iloc[0]["cnt"])
