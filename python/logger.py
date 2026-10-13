# logger.py — logging padrão Python (arquivo por dia em log/)

import logging
import os
from datetime import datetime
from threading import Lock

from paths import LOG_DIR

_LOG_DIR = str(LOG_DIR)
_handlers = {}
_lock = Lock()


class _LinhaDiariaFormatter(logging.Formatter):
    """Formato: dd/MM/yyyy HH:mm Info|DEBUG mensagem"""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        tipo = "DEBUG" if record.levelno == logging.DEBUG else "Info"
        return f"{ts} {tipo} {record.getMessage()}"


class _ArquivoPorDiaHandler(logging.Handler):
    """Um arquivo por dia: log/dd-MM-yyyy.log"""

    def __init__(self, log_dir: str = _LOG_DIR):
        super().__init__()
        self.log_dir = log_dir
        self._dia_atual = None
        self._stream = None
        os.makedirs(self.log_dir, exist_ok=True)

    def _caminho_hoje(self) -> str:
        nome = datetime.now().strftime("%d-%m-%Y") + ".log"
        return os.path.join(self.log_dir, nome)

    def _garantir_stream(self):
        hoje = datetime.now().date()
        if self._dia_atual != hoje or self._stream is None:
            if self._stream:
                try:
                    self._stream.close()
                except Exception:
                    pass
            self._dia_atual = hoje
            self._stream = open(self._caminho_hoje(), "a", encoding="utf-8")

    def emit(self, record: logging.LogRecord):
        try:
            self._garantir_stream()
            msg = self.format(record)
            self._stream.write(msg + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        if self._stream:
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        super().close()


def _obter_logger(nome: str = "SGC") -> logging.Logger:
    with _lock:
        if nome in _handlers:
            return _handlers[nome]

        logger = logging.getLogger(nome)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        if not logger.handlers:
            handler = _ArquivoPorDiaHandler()
            handler.setFormatter(_LinhaDiariaFormatter())
            logger.addHandler(handler)

        _handlers[nome] = logger
        return logger


def _tipo_e_debug(tipo_evento: str) -> bool:
    t = (tipo_evento or "").strip().upper()
    return t in {"DEBUG", "DEPURACAO", "DEPURAÇÃO"}


class ClLog:
    """Fachada compatível com o código existente do SGC."""

    exportarlog = ""

    def __init__(self, export_path=None):
        self._logger = _obter_logger("SGC")
        if export_path:
            self.exportarlog = export_path

    def registrarActionLog(self, mod, type, action):
        mensagem = f"[{mod}] {action}"
        if _tipo_e_debug(type):
            self._logger.debug(mensagem)
        else:
            self._logger.info(mensagem)

    def registarExceptionLog(self, app_name, mod, type, exception):
        mensagem = f"EXCEÇÃO [{app_name}/{mod}/{type}]: {exception}"
        self._logger.info(mensagem)

    def info(self, mensagem: str):
        self._logger.info(mensagem)

    def debug(self, mensagem: str):
        self._logger.debug(mensagem)
