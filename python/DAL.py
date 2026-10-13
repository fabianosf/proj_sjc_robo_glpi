# DAL.py — camada de acesso a dados (MariaDB / Oracle via CONFIGURACAO.py)

import os
import logging
import pandas as pd
import traceback
import threading
import time
import platform

from datetime import datetime
from typing import Any, Dict, Optional

from paths import CONF_DIR, DRIVERS_DIR, PROJECT_ROOT

BASE_DIR = PROJECT_ROOT


def _registrar_log_dal(level: str, evento: str, descricao: str) -> None:
    try:
        from logger import ClLog

        log = ClLog()
        if level.upper() == "ERROR":
            log.registarExceptionLog("DAL", evento, descricao, Exception(descricao))
        else:
            log.registrarActionLog("DAL", evento, descricao)
        return
    except ImportError:
        pass

    logging.getLogger("DAL").info(f"{evento} - {descricao}")


class DatabaseConnectionError(Exception):
    pass


class ConfigurationError(Exception):
    pass


def _criar_leitor_configuracao(conf_dir: Optional[str] = None):
    from CONFIGURACAO import clmain

    return clmain(pasta_conf=conf_dir)


def _obter_parametros_banco(config_file: str, conf_dir: Optional[str] = None) -> Dict[str, Any]:
    from CONFIGURACAO import ConfiguracaoError

    pasta_conf = conf_dir or str(CONF_DIR)
    leitor = _criar_leitor_configuracao(pasta_conf)
    try:
        return leitor._obter_Parametros_Configuracao(config_file)
    except ConfiguracaoError as exc:
        raise ConfigurationError(str(exc)) from exc
    except Exception as exc:
        raise ConfigurationError(
            f"Falha ao carregar parâmetros de '{config_file}': {exc}"
        ) from exc


class DALLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return
        self.initialized = True

    def log(self, level, evento, descricao):
        _registrar_log_dal(level, evento, descricao)


class QueryCache:
    def __init__(self, ttl_seconds=300):
        self.ttl = ttl_seconds
        self._data = {}
        self._time = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._data:
                if time.time() - self._time[key] < self.ttl:
                    return self._data[key].copy()
                del self._data[key]
                del self._time[key]
        return None

    def set(self, key, value):
        with self._lock:
            self._data[key] = value.copy()
            self._time[key] = time.time()


class ConnectionPool:
    def __init__(self, max_connections=10):
        self.max_connections = max_connections
        self._pool = []
        self._in_use = set()
        self._lock = threading.Lock()
        self._creator = None
        self._logger = DALLogger()

    def set_creator(self, creator):
        self._creator = creator

    def get_connection(self):
        with self._lock:
            for conn in self._pool:
                if conn not in self._in_use:
                    self._in_use.add(conn)
                    return conn

            if len(self._pool) < self.max_connections:
                conn = self._creator()
                self._pool.append(conn)
                self._in_use.add(conn)
                return conn

            raise DatabaseConnectionError("Pool esgotado")

    def return_connection(self, conn):
        with self._lock:
            self._in_use.discard(conn)

    def discard_connection(self, conn):
        with self._lock:
            self._in_use.discard(conn)
            if conn in self._pool:
                self._pool.remove(conn)
            try:
                conn.close()
            except Exception:
                pass


class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_time=30):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
        self._lock = threading.Lock()

    def call(self, func, *args, **kwargs):
        with self._lock:
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_time:
                    self.state = "HALF_OPEN"
                else:
                    raise DatabaseConnectionError("Circuit breaker OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = "CLOSED"

    def _on_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"


class _DALCore:
    def __init__(self, config_file: str, config_dir: Optional[str] = None):
        self.logger = DALLogger()
        self.config_dir = config_dir or str(CONF_DIR)
        self.config_file = config_file
        self._nome_arquivo = config_file

        self.logger.log("INFO", "INIT", f"Inicializando DAL ({config_file})")
        self.config = _obter_parametros_banco(self.config_file, self.config_dir)
        self.cache = QueryCache()
        self.pool = ConnectionPool()
        self.pool.set_creator(self._create_connection)
        self.circuit_breaker = CircuitBreaker()

    @property
    def arq(self):
        return self._nome_arquivo

    @arq.setter
    def arq(self, nome):
        if not nome or not isinstance(nome, str) or not nome.strip():
            raise ValueError("O nome do arquivo de configuração não pode ser vazio.")
        self._nome_arquivo = nome.strip()
        self.config_file = self._nome_arquivo
        self.config = _obter_parametros_banco(self.config_file, self.config_dir)

    def _get_oracle_client_path(self):
        if platform.system() == "Windows":
            paths = [
                DRIVERS_DIR / "oracle_win" / "oracle" / "instantclient_21_14",
                DRIVERS_DIR / "oracle_win" / "instantclient_21_14",
            ]
        else:
            paths = [DRIVERS_DIR / "oracle_linux" / "instantclient_21_1"]

        for path in paths:
            if path.exists():
                return str(path)
        raise DatabaseConnectionError("Oracle Client não encontrado")

    @staticmethod
    def _resolver_service_oracle(config: Dict[str, Any]) -> str:
        for chave in ("bd", "service_name", "service name", "SID", "sid", "database"):
            valor = config.get(chave)
            if valor is not None and str(valor).strip():
                return str(valor).strip()
        raise DatabaseConnectionError(
            "Service Oracle não configurado. Informe 'bd' ou 'service name' em erp.dat."
        )

    def _create_connection(self):
        config = self.config
        sgbd = config.get("sgbd", "mariadb").lower()

        if sgbd == "oracle":
            import oracledb

            lib_path = self._get_oracle_client_path()
            try:
                oracledb.init_oracle_client(lib_dir=lib_path)
                oracledb.defaults.thick_mode = True
            except Exception as exc:
                self.logger.log("WARNING", "ORACLE", str(exc))

            service = self._resolver_service_oracle(config)
            dsn = f"{config['servidor']}:{config['porta']}/{service}"
            return oracledb.connect(
                user=config["usuario"],
                password=config["senha"],
                dsn=dsn,
            )

        if sgbd in ("mariadb", "mysql"):
            import pymysql

            timeout_conexao = int(os.getenv("SGC_DB_CONNECT_TIMEOUT", "10"))
            timeout_query = int(os.getenv("SGC_DB_READ_TIMEOUT", "30"))
            return pymysql.connect(
                host=config["servidor"],
                port=int(config["porta"]),
                user=config["usuario"],
                password=config["senha"],
                database=config["bd"],
                charset="utf8mb4",
                connect_timeout=timeout_conexao,
                read_timeout=timeout_query,
                write_timeout=timeout_query,
            )

        raise DatabaseConnectionError(f"SGBD não suportado: {sgbd}")

    def execute_query(self, sql, values=None, fetch=True):
        if sql is None or not str(sql).strip():
            self.logger.log("WARNING", "QUERY", "Consulta SQL vazia ignorada")
            return pd.DataFrame() if fetch else False

        conn = None
        cursor = None
        conn_ok = True
        try:
            conn = self.circuit_breaker.call(self.pool.get_connection)
            cursor = conn.cursor()
            sgbd = self.config.get("sgbd", "mariadb").lower()

            if sgbd == "oracle" and values is not None and "?" in sql:
                if isinstance(values, (list, tuple)):
                    for i in range(len(values)):
                        sql = sql.replace("?", f":{i+1}", 1)
                else:
                    sql = sql.replace("?", ":1", 1)
                    values = [values]
            elif sgbd in ("mariadb", "mysql") and values is not None and "?" in sql:
                sql = sql.replace("?", "%s")

            if values is None:
                cursor.execute(sql)
            else:
                cursor.execute(sql, values)

            if fetch:
                cols = [c[0] for c in cursor.description]
                rows = cursor.fetchall()
                return pd.DataFrame(rows, columns=cols)

            conn.commit()
            return True

        except Exception:
            self.logger.log("ERROR", "QUERY", traceback.format_exc())
            conn_ok = False
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            # fetch: None = erro (distinto de DataFrame vazio = sem linhas)
            return None if fetch else False
        finally:
            if cursor:
                cursor.close()
            if conn:
                if conn_ok:
                    self.pool.return_connection(conn)
                else:
                    self.pool.discard_connection(conn)

    def read(self, sql, values=None):
        return self.execute_query(sql, values, True)

    def create(self, sql, values=None):
        return self.execute_query(sql, values, False)

    def update(self, sql, values=None):
        return self.execute_query(sql, values, False)

    def delete(self, sql, values=None):
        return self.execute_query(sql, values, False)

    def test_connection(self):
        sgbd = self.config.get("sgbd", "mariadb").lower()
        sql = "SELECT 1 FROM DUAL" if sgbd == "oracle" else "SELECT 1"
        result = self.execute_query(sql)
        return not result.empty


class DAL(_DALCore):
    """Compatível com a API legada: DAL(app_name=..., nome_arquivo_config='sgc.dat')."""

    def __init__(
        self,
        config_file: Optional[str] = None,
        config_dir: Optional[str] = None,
        app_name: str = "N/A",
        path: Optional[str] = None,
        nome_arquivo_config: Optional[str] = None,
        **kwargs,
    ):
        if nome_arquivo_config:
            config_file = nome_arquivo_config
        if path:
            config_dir = path
        if not config_file:
            config_file = "sgc.dat"

        self.app_name = app_name
        self.path = config_dir or str(CONF_DIR)
        super().__init__(config_file=config_file, config_dir=config_dir)
