# AgendadorSGC.py — processo independente de aprendizado e relatórios (Windows/Linux)

import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

from DbMigracao import ClDbMigracao
from logger import ClLog
from TarefasML import (
    executar_detectar_correcoes,
    executar_relatorio_assertividade,
    executar_relatorio_feedback,
    executar_retreino_diario,
    garantir_tabelas_fase3,
)

_STATE_PATH = Path(__file__).resolve().parent.parent / "log" / "agendador_state.json"


class AgendadorSGC:
    """Agendador interno em Python — não depende do Task Scheduler nem do main.py."""

    RETRAIN_HOUR = int(os.getenv("ML_RETRAIN_HOUR", "2"))
    REPORT_HOUR = int(os.getenv("ML_REPORT_HOUR", "3"))
    FEEDBACK_REPORT_WEEKDAY = int(os.getenv("ML_FEEDBACK_REPORT_WDAY", "6"))  # 0=seg … 6=dom
    FEEDBACK_REPORT_HOUR = int(os.getenv("ML_FEEDBACK_REPORT_HOUR", "4"))
    INTERVALO_SEG = int(os.getenv("SGC_AGENDADOR_INTERVALO", "60"))

    def __init__(self):
        self.running = True
        self._ultima_data_retreino = None
        self._ultima_data_relatorio = None
        self._ultima_data_relatorio_feedback = None
        self.logger = ClLog()
        self._carregar_estado()

    def _carregar_estado(self) -> None:
        """Evita re-treino/PDF de catch-up a cada reinício após o horário do dia."""
        try:
            if not _STATE_PATH.is_file():
                return
            data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            self._ultima_data_retreino = self._parse_date(data.get("retreino"))
            self._ultima_data_relatorio = self._parse_date(data.get("relatorio"))
            self._ultima_data_relatorio_feedback = self._parse_date(data.get("feedback"))
        except Exception:
            pass

    @staticmethod
    def _parse_date(value) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def _salvar_estado(self) -> None:
        try:
            _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "retreino": self._ultima_data_retreino.isoformat() if self._ultima_data_retreino else None,
                "relatorio": self._ultima_data_relatorio.isoformat() if self._ultima_data_relatorio else None,
                "feedback": (
                    self._ultima_data_relatorio_feedback.isoformat()
                    if self._ultima_data_relatorio_feedback
                    else None
                ),
            }
            _STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _ja_executou_hoje(self, ultima_data) -> bool:
        return ultima_data == datetime.now().date()

    def _deve_retreinar(self, agora: datetime) -> bool:
        if agora.hour < self.RETRAIN_HOUR:
            return False
        return not self._ja_executou_hoje(self._ultima_data_retreino)

    def _deve_relatorio_assertividade(self, agora: datetime) -> bool:
        if agora.hour < self.REPORT_HOUR:
            return False
        return not self._ja_executou_hoje(self._ultima_data_relatorio)

    def _deve_relatorio_feedback(self, agora: datetime) -> bool:
        if agora.weekday() != self.FEEDBACK_REPORT_WEEKDAY:
            return False
        if agora.hour < self.FEEDBACK_REPORT_HOUR:
            return False
        return not self._ja_executou_hoje(self._ultima_data_relatorio_feedback)

    def executar_ciclo(self):
        agora = datetime.now()
        try:
            from SchedulerHeartbeat import tick

            tick()
        except Exception:
            pass

        if self._deve_retreinar(agora):
            print(f"[{agora:%H:%M:%S}] Iniciando re-treino diário...")
            self._ultima_data_retreino = agora.date()
            self._salvar_estado()
            ok = executar_retreino_diario()
            print(f"[{datetime.now():%H:%M:%S}] Re-treino {'OK' if ok else 'FALHOU'}")

        if self._deve_relatorio_assertividade(agora):
            print(f"[{agora:%H:%M:%S}] Gerando PDF de assertividade...")
            self._ultima_data_relatorio = agora.date()
            self._salvar_estado()
            try:
                caminho = executar_relatorio_assertividade()
                print(f"[{datetime.now():%H:%M:%S}] PDF: {caminho}")
            except Exception as e:
                self.logger.registarExceptionLog("AGENDADOR", "EXCEPTION", "FALHA PDF ASSERTIVIDADE", e)
                print(f"[ERRO] PDF assertividade: {e}")
                try:
                    from SchedulerHeartbeat import note_job

                    note_job("relatorio_assertividade", False, str(e)[:300])
                except Exception:
                    pass

        if self._deve_relatorio_feedback(agora):
            print(f"[{agora:%H:%M:%S}] Gerando relatório de cobertura feedback...")
            self._ultima_data_relatorio_feedback = agora.date()
            self._salvar_estado()
            try:
                caminho = executar_relatorio_feedback()
                print(f"[{datetime.now():%H:%M:%S}] Relatório: {caminho}")
            except Exception as e:
                self.logger.registarExceptionLog("AGENDADOR", "EXCEPTION", "FALHA RELATÓRIO FEEDBACK", e)
                try:
                    from SchedulerHeartbeat import note_job

                    note_job("relatorio_feedback", False, str(e)[:300])
                except Exception:
                    pass

    def loop(self, silencioso: bool = False):
        if not silencioso:
            print("=" * 60)
            print("AGENDADOR SGC — aprendizado e relatórios")
            print("=" * 60)
            print(f"Re-treino diário        : {self.RETRAIN_HOUR:02d}:00")
            print(f"PDF assertividade       : {self.REPORT_HOUR:02d}:00")
            print(f"Relatório feedback      : dia {self.FEEDBACK_REPORT_WEEKDAY} às {self.FEEDBACK_REPORT_HOUR:02d}:00")
            print(f"Intervalo de verificação: {self.INTERVALO_SEG}s")
            print("=" * 60)

        if not garantir_tabelas_fase3():
            msg = "[AVISO] Tb_ML_Log / Tb_Correcao_Feedback não verificadas."
            print(msg) if not silencioso else None
            self.logger.registrarActionLog("AGENDADOR", "AVISO", msg)

        self.logger.registrarActionLog("AGENDADOR", "INICIO", "AGENDADOR SGC INICIADO")

        while self.running:
            try:
                self.executar_ciclo()
            except Exception as e:
                self.logger.registarExceptionLog("AGENDADOR", "EXCEPTION", "ERRO NO CICLO DO AGENDADOR", e)
                print(f"[ERRO] Ciclo agendador: {e}")
            time.sleep(self.INTERVALO_SEG)


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "retreino":
            sys.exit(0 if executar_retreino_diario() else 1)
        if cmd == "correcoes":
            executar_detectar_correcoes()
            return
        if cmd == "assertividade":
            print(executar_relatorio_assertividade())
            return
        if cmd == "feedback":
            print(executar_relatorio_feedback())
            return
        if cmd == "criar-tabelas":
            ok = ClDbMigracao().aplicar_fase3()
            print("OK" if ok else "FALHOU")
            sys.exit(0 if ok else 1)

    ag = AgendadorSGC()
    try:
        ag.loop()
    except KeyboardInterrupt:
        print("\nAgendador encerrado.")
        ag.running = False


if __name__ == "__main__":
    main()
