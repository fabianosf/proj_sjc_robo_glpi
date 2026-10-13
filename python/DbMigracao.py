# DbMigracao.py — alterações de schema (Fase 2 dev / Fase 3 produção)

import os

from DAL import DAL
from logger import ClLog
from paths import SQL_DIR

SQL_CRIAR_FEEDBACK = (SQL_DIR / "criar_Tb_Ticket_Feedback_Temp.sql").read_text(encoding="utf-8")

SQL_CRIAR_ML_LOG = (SQL_DIR / "criar_Tb_ML_Log.sql").read_text(encoding="utf-8")

SQL_CRIAR_CORRECAO = (SQL_DIR / "criar_Tb_Correcao_Feedback.sql").read_text(encoding="utf-8")

SQL_CRIAR_PERFORMANCE = (SQL_DIR / "criar_tb_performance.sql").read_text(encoding="utf-8")


class ClDbMigracao:
    logger = ClLog()

    def __init__(self, dal: DAL = None):
        self.dal = dal or DAL(app_name="DbMigracao", nome_arquivo_config="sgc.dat")
        self.ultimo_backfill_equipe = 0

    def _coluna_existe(self, tabela: str, coluna: str) -> bool:
        sql = f"SHOW COLUMNS FROM {tabela} LIKE %s"
        df = self.dal.read(sql, (coluna,))
        return df is not None and not df.empty

    def _tabela_existe(self, tabela: str) -> bool:
        df = self.dal.read("SHOW TABLES LIKE %s", (tabela,))
        return df is not None and not df.empty

    def _criar_tabela_feedback(self) -> bool:
        try:
            self.dal.create(SQL_CRIAR_FEEDBACK)
            self.logger.registrarActionLog(
                "DB", "ATIVIDADE", "TABELA Tb_Ticket_Feedback_Temp VERIFICADA/CRIADA"
            )
            return True
        except Exception as e:
            self.logger.registarExceptionLog("DB", "EXCEPTION", "FALHA AO CRIAR Tb_Ticket_Feedback_Temp", e)
            return False

    def _backfill_equipe_ticket_new(self) -> bool:
        """Preenche Equipe em registros antigos a partir do técnico em Tb_Atrib."""
        if not self._tabela_existe("Tb_Ticket_new") or not self._coluna_existe("Tb_Ticket_new", "Equipe"):
            return True

        sql_count = """
            SELECT COUNT(*) AS cnt
            FROM Tb_Ticket_new tn
            INNER JOIN Tb_Atrib ta
                ON UPPER(TRIM(ta.Usuario)) = UPPER(TRIM(tn.Tecnico))
            WHERE (tn.Equipe IS NULL OR TRIM(tn.Equipe) = '')
              AND ta.Equipe IS NOT NULL AND TRIM(ta.Equipe) <> ''
        """
        sql_update = """
            UPDATE Tb_Ticket_new tn
            INNER JOIN Tb_Atrib ta
                ON UPPER(TRIM(ta.Usuario)) = UPPER(TRIM(tn.Tecnico))
            SET tn.Equipe = UPPER(TRIM(ta.Equipe))
            WHERE (tn.Equipe IS NULL OR TRIM(tn.Equipe) = '')
              AND ta.Equipe IS NOT NULL AND TRIM(ta.Equipe) <> ''
        """
        try:
            df = self.dal.read(sql_count)
            pendente = int(df.iloc[0]["cnt"]) if df is not None and not df.empty else 0
            if pendente == 0:
                return True

            if not self.dal.update(sql_update):
                return False

            self.ultimo_backfill_equipe = pendente
            self.logger.registrarActionLog(
                "DB",
                "ATIVIDADE",
                f"BACKFILL Equipe EM Tb_Ticket_new: {self.ultimo_backfill_equipe} REGISTRO(S)",
            )
            return True
        except Exception as e:
            self.logger.registarExceptionLog("DB", "EXCEPTION", "FALHA NO BACKFILL DE Equipe", e)
            return False

    def aplicar_fase2(self) -> bool:
        try:
            if not self._criar_tabela_feedback():
                return False

            if not self._tabela_existe("Tb_Ticket_new"):
                self.logger.registrarActionLog("DB", "AVISO", "Tb_Ticket_new NÃO ENCONTRADA — PULANDO COLUNA Equipe")
            elif not self._coluna_existe("Tb_Ticket_new", "Equipe"):
                self.dal.create(
                    "ALTER TABLE Tb_Ticket_new ADD COLUMN Equipe VARCHAR(5) NULL AFTER Tecnico"
                )
                self.logger.registrarActionLog("DB", "ATIVIDADE", "COLUNA Equipe ADICIONADA EM Tb_Ticket_new")

            if self._tabela_existe("Tb_Ticket_Feedback_Temp"):
                if not self._coluna_existe("Tb_Ticket_Feedback_Temp", "Localizacao"):
                    self.dal.create(
                        "ALTER TABLE Tb_Ticket_Feedback_Temp "
                        "ADD COLUMN Localizacao VARCHAR(500) NULL AFTER Descricao"
                    )
                    self.logger.registrarActionLog(
                        "DB", "ATIVIDADE", "COLUNA Localizacao ADICIONADA EM Tb_Ticket_Feedback_Temp"
                    )

            if not self._backfill_equipe_ticket_new():
                return False

            return True
        except Exception as e:
            self.logger.registarExceptionLog("DB", "EXCEPTION", "FALHA NA MIGRAÇÃO FASE 2", e)
            return False

    def _ensure_dat_reg_ticket_new(self) -> bool:
        """Coluna Dat_Reg = instante da atribuição local (métrica 'Hoje' do painel)."""
        if not self._tabela_existe("Tb_Ticket_new"):
            return True
        if self._coluna_existe("Tb_Ticket_new", "Dat_Reg"):
            return True
        try:
            ok = self.dal.create(
                "ALTER TABLE Tb_Ticket_new "
                "ADD COLUMN Dat_Reg DATETIME NULL COMMENT 'Instante atribuição SGC' "
                "AFTER Dat_Sol"
            )
            if ok:
                self.logger.registrarActionLog(
                    "DB", "ATIVIDADE", "COLUNA Dat_Reg ADICIONADA EM Tb_Ticket_new"
                )
            return bool(ok)
        except Exception as e:
            self.logger.registarExceptionLog(
                "DB", "EXCEPTION", "FALHA AO ADICIONAR Dat_Reg EM Tb_Ticket_new", e
            )
            return False

    def _ensure_motivo_atrib_ml_log(self) -> bool:
        """Coluna Motivo_Atrib = por que aquele técnico ganhou o chamado."""
        if not self._tabela_existe("Tb_ML_Log"):
            return True
        if self._coluna_existe("Tb_ML_Log", "Motivo_Atrib"):
            return True
        try:
            ok = self.dal.create(
                "ALTER TABLE Tb_ML_Log "
                "ADD COLUMN Motivo_Atrib VARCHAR(500) NULL "
                "COMMENT 'Por que este técnico' AFTER Motivo_Rejeicao"
            )
            if ok:
                self.logger.registrarActionLog(
                    "DB", "ATIVIDADE", "COLUNA Motivo_Atrib ADICIONADA EM Tb_ML_Log"
                )
            return bool(ok)
        except Exception as e:
            self.logger.registarExceptionLog(
                "DB", "EXCEPTION", "FALHA AO ADICIONAR Motivo_Atrib EM Tb_ML_Log", e
            )
            return False

    def aplicar_fase3(self) -> bool:
        """Cria Tb_ML_Log / Tb_Correcao_Feedback / tb_performance e garante Dat_Reg."""
        try:
            if SQL_CRIAR_ML_LOG.strip() and not self._tabela_existe("Tb_ML_Log"):
                if not self.dal.create(SQL_CRIAR_ML_LOG):
                    return False
            self.logger.registrarActionLog("DB", "ATIVIDADE", "TABELA Tb_ML_Log VERIFICADA/CRIADA")

            if SQL_CRIAR_CORRECAO.strip() and not self._tabela_existe("Tb_Correcao_Feedback"):
                if not self.dal.create(SQL_CRIAR_CORRECAO):
                    return False
            self.logger.registrarActionLog("DB", "ATIVIDADE", "TABELA Tb_Correcao_Feedback VERIFICADA/CRIADA")

            if SQL_CRIAR_PERFORMANCE.strip() and not self._tabela_existe("tb_performance"):
                if not self.dal.create(SQL_CRIAR_PERFORMANCE):
                    return False
            self.logger.registrarActionLog("DB", "ATIVIDADE", "TABELA tb_performance VERIFICADA/CRIADA")

            if not self._ensure_dat_reg_ticket_new():
                return False
            if not self._ensure_motivo_atrib_ml_log():
                return False
            return True
        except Exception as e:
            self.logger.registarExceptionLog("DB", "EXCEPTION", "FALHA NA MIGRAÇÃO FASE 3", e)
            return False

    @staticmethod
    def migracao_completa_habilitada() -> bool:
        """Dev/local: também aplica ALTER TABLE da Fase 2. Produção: deixe desligado."""
        return os.getenv("SGC_MIGRACAO_COMPLETA", "0").lower() in ("1", "true", "yes")

    def aplicar_migracao_ambiente(self) -> bool:
        """
        Padrão (produção): só Tb_ML_Log + Tb_Correcao_Feedback.
        Com SGC_MIGRACAO_COMPLETA=1: inclui migração Fase 2 (dev/local).
        """
        if self.migracao_completa_habilitada():
            return self.aplicar_migracoes()
        return self.aplicar_fase3()

    def aplicar_migracoes(self) -> bool:
        ok2 = self.aplicar_fase2()
        ok3 = self.aplicar_fase3()
        return ok2 and ok3
