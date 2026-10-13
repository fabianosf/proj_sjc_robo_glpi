# ----------------------------
# Deus seja Louvado!
# ----------------------------
"""
Módulo de leitura de arquivos de configuração criptografados.

Abre arquivos .dat na pasta conf/, descriptografa com Fernet + chave.key
(mesmo padrão do utilitário PROJ_GAC) e retorna o dicionário de parâmetros.

Uso:
    from python.CONFIGURACAO import clmain, ConfiguracaoError

    config = clmain()
    parametros = config._obter_Parametros_Configuracao("ad")
    parametros = config._obter_Parametros_Configuracao("seda.dat")
"""

from __future__ import annotations

import json
import os
import traceback
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from paths import CONF_DIR, PROJECT_ROOT

_DEFAULT_PROJECT_ROOT = str(PROJECT_ROOT)

CONF_FOLDER_NAME = "conf"
KEY_FILE_NAME = "chave.key"


class ConfiguracaoError(Exception):
    """Erro base ao ler ou descriptografar arquivos de configuração."""


class ChaveConfiguracaoNaoEncontradaError(ConfiguracaoError):
    """Arquivo chave.key ausente na pasta de configuração."""


class ArquivoConfiguracaoNaoEncontradoError(ConfiguracaoError):
    """Arquivo .dat solicitado não foi encontrado."""


class ArquivoConfiguracaoVazioError(ConfiguracaoError):
    """Arquivo .dat existe, porém está vazio."""


class DescriptografiaConfiguracaoError(ConfiguracaoError):
    """Falha ao descriptografar o conteúdo (chave inválida ou arquivo corrompido)."""


class JsonConfiguracaoInvalidoError(ConfiguracaoError):
    """Conteúdo descriptografado não é um JSON válido."""


class clmain:
    """
    Cliente para leitura de arquivos de configuração criptografados.

    Utiliza o mesmo algoritmo do PROJ_GAC: Fernet + conf/chave.key,
    com conteúdo interno em JSON (dicionário chave/valor).
    """

    def __init__(self, pasta_conf: Optional[str] = None):
        """
        Inicializa o leitor de configuração.

        Args:
            pasta_conf: caminho da pasta que contém os .dat e chave.key.
                        Padrão: <raiz_do_projeto>/conf
        """
        self._pasta_conf = self._resolver_pasta_conf(pasta_conf)
        self._caminho_chave = os.path.join(self._pasta_conf, KEY_FILE_NAME)

    @staticmethod
    def _resolver_pasta_conf(pasta_conf: Optional[str]) -> str:
        if pasta_conf:
            return os.path.abspath(pasta_conf)
        return str(CONF_DIR)

    @staticmethod
    def _normalizar_nome_arquivo(nome_arquivo: str) -> str:
        nome = (nome_arquivo or "").strip()
        if not nome:
            raise ConfiguracaoError("O nome do arquivo de configuração é obrigatório.")
        if not nome.lower().endswith(".dat"):
            nome += ".dat"
        return nome

    def _carregar_chave(self) -> bytes:
        if not os.path.exists(self._caminho_chave):
            raise ChaveConfiguracaoNaoEncontradaError(
                f"Arquivo de chave não encontrado: {self._caminho_chave}"
            )
        try:
            with open(self._caminho_chave, "rb") as arquivo_chave:
                chave = arquivo_chave.read()
            if not chave:
                raise ChaveConfiguracaoNaoEncontradaError(
                    f"Arquivo de chave vazio: {self._caminho_chave}"
                )
            return chave
        except OSError as exc:
            raise ConfiguracaoError(
                f"Falha ao ler o arquivo de chave '{self._caminho_chave}': {exc}"
            ) from exc

    @staticmethod
    def _descriptografar(conteudo_criptografado: str, chave: bytes) -> str:
        """
        Descriptografa o texto usando Fernet (mesma rotina do PROJ_GAC._crip decrypt).
        """
        if not conteudo_criptografado or not conteudo_criptografado.strip():
            raise ArquivoConfiguracaoVazioError("O arquivo de configuração está vazio.")

        try:
            cipher = Fernet(chave)
            texto_bytes = cipher.decrypt(conteudo_criptografado.encode("utf-8"))
            return texto_bytes.decode("utf-8")
        except InvalidToken as exc:
            raise DescriptografiaConfiguracaoError(
                "Token de criptografia inválido. "
                "O arquivo pode estar corrompido ou a chave.key não corresponde."
            ) from exc
        except Exception as exc:
            raise DescriptografiaConfiguracaoError(
                f"Falha ao descriptografar o arquivo de configuração: {exc}"
            ) from exc

    def _obter_Parametros_Configuracao(self, nome_arquivo: str) -> Dict[str, Any]:
        """
        Lê e descriptografa um arquivo .dat da pasta conf/.

        Args:
            nome_arquivo: nome do arquivo (ex.: 'ad', 'ad.dat', 'seda').

        Returns:
            Dicionário com os parâmetros gravados no arquivo.

        Raises:
            ConfiguracaoError: e subclasses em caso de falha na leitura.
        """
        nome_normalizado = self._normalizar_nome_arquivo(nome_arquivo)
        caminho_arquivo = os.path.join(self._pasta_conf, nome_normalizado)

        if not os.path.exists(caminho_arquivo):
            raise ArquivoConfiguracaoNaoEncontradoError(
                f"Arquivo '{nome_normalizado}' não encontrado em '{self._pasta_conf}'."
            )

        try:
            chave = self._carregar_chave()

            with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
                conteudo_criptografado = arquivo.read()

            json_texto = self._descriptografar(conteudo_criptografado, chave)
            dados = json.loads(json_texto)

            if not isinstance(dados, dict):
                raise JsonConfiguracaoInvalidoError(
                    f"O conteúdo de '{nome_normalizado}' deve ser um objeto JSON (dicionário)."
                )

            return dados

        except (
            ConfiguracaoError,
            ChaveConfiguracaoNaoEncontradaError,
            ArquivoConfiguracaoNaoEncontradoError,
            ArquivoConfiguracaoVazioError,
            DescriptografiaConfiguracaoError,
            JsonConfiguracaoInvalidoError,
        ):
            raise
        except json.JSONDecodeError as exc:
            raise JsonConfiguracaoInvalidoError(
                f"Falha ao decodificar JSON de '{nome_normalizado}': {exc}"
            ) from exc
        except OSError as exc:
            raise ConfiguracaoError(
                f"Falha de I/O ao ler '{caminho_arquivo}': {exc}"
            ) from exc
        except Exception as exc:
            raise ConfiguracaoError(
                f"Erro inesperado ao obter parâmetros de '{nome_normalizado}': {exc}\n"
                f"{traceback.format_exc()}"
            ) from exc


__all__ = [
    "clmain",
    "ConfiguracaoError",
    "ChaveConfiguracaoNaoEncontradaError",
    "ArquivoConfiguracaoNaoEncontradoError",
    "ArquivoConfiguracaoVazioError",
    "DescriptografiaConfiguracaoError",
    "JsonConfiguracaoInvalidoError",
]
