"""
Módulo de integração com a API REST (V1) do GLPI 10.0.2.

Referência: https://github.com/glpi-project/glpi/blob/10.0.2/apirest.md
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import traceback
import html
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from paths import CONF_DIR

# ---------------------------------------------------------------------------
# Configuração (credenciais em conf/glpi.dat via CONFIGURACAO.py)
# ---------------------------------------------------------------------------
GLPI_API_CONFIG_FILE = "glpi"

_DEFAULT_CONF_DIR = str(CONF_DIR)

# Timeout padrão das requisições HTTP (segundos)
GLPI_REQUEST_TIMEOUT = 30

# Tamanho máximo de registros por página na busca da API
GLPI_SEARCH_PAGE_SIZE = 500

# Janela de pesquisa: somente chamados abertos nos últimos N dias (env)
DIAS_CHAMADOS_ABERTOS = max(1, int(os.getenv("SGC_GLPI_DIAS_ABERTOS", "30") or 30))

# Quantidade máxima de tickets por busca GET /Ticket (range 0..N-1)
GLPI_FETCH_LIMIT = max(1, min(1000, int(os.getenv("SGC_GLPI_FETCH_LIMIT", "300") or 300)))

# ---------------------------------------------------------------------------
# Constantes internas da API (search options do item Ticket)
# ---------------------------------------------------------------------------
_TICKET_FIELD_ID = "2"
_TICKET_FIELD_TITLE = "1"
_TICKET_FIELD_CATEGORY = "7"
_TICKET_FIELD_STATUS = "12"
_TICKET_FIELD_OPEN_DATE = "15"
_TICKET_FIELD_CLOSE_DATE = "16"
_TICKET_FIELD_REQUESTER = "4"
_TICKET_FIELD_TECHNICIAN = "5"

_TICKET_FORCED_DISPLAY = [
    _TICKET_FIELD_ID,
    _TICKET_FIELD_TITLE,
    _TICKET_FIELD_CATEGORY,
    _TICKET_FIELD_STATUS,
    _TICKET_FIELD_OPEN_DATE,
    _TICKET_FIELD_CLOSE_DATE,
    _TICKET_FIELD_REQUESTER,
    _TICKET_FIELD_TECHNICIAN,
]

_STATUS_LABELS = {
    1: "Novo",
    2: "Em atendimento (atribuído)",
    3: "Planejado",
    4: "Pendente",
    5: "Solucionado",
    6: "Fechado",
}

_VALIDATION_ACCEPTED = 3
_VALIDATION_WAITING = 2
_VALIDATION_REFUSED = 4

GLPI_STATUS_ATRIBUIDO = 2
GLPI_STATUS_PENDENTE = 4
GLPI_STATUS_FECHADO = 6

_TICKET_USER_TYPE_ASSIGNED = 2

_MARCADOR_SGAC_ANALISADO = "SGAC: chamado analisado sem tarefa automatizada"
_MARCADORES_RESPOSTA_PROCESSADO = (
    "Prezado usuário,a matrícula citada no chamado não existe",
    "Prezado usuário,a matrícula citada no chamado já esta cadastrada",
    "Prezado usuário, o chamado foi concluído com sucesso",
    "o usuário  foi  cadastrado  no aplicativo",
    "Para realizar o cadastro do usuário, faz-se necessário",
    _MARCADOR_SGAC_ANALISADO,
)

logger = logging.getLogger(__name__)


def _data_limite_abertura_chamados() -> datetime:
    """Retorna a data/hora limite para chamados abertos nos últimos N dias."""
    return datetime.now() - timedelta(days=DIAS_CHAMADOS_ABERTOS)


def _formatar_data_limite_abertura() -> str:
    """Formata a data limite para critérios de busca da API GLPI."""
    return _data_limite_abertura_chamados().strftime("%Y-%m-%d %H:%M:%S")


def _aplicar_filtro_abertura_recente(
    criterios: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """Acrescenta filtro de data de abertura (últimos DIAS_CHAMADOS_ABERTOS dias)."""
    criterios_filtrados = list(criterios)
    criterios_filtrados.append(
        {
            "link": "AND",
            "field": _TICKET_FIELD_OPEN_DATE,
            "searchtype": "morethan",
            "value": _formatar_data_limite_abertura(),
        }
    )
    return criterios_filtrados


def _formatar_resposta_justificada(texto: str) -> str:
    """Formata texto de acompanhamento GLPI com alinhamento justificado e negrito."""
    conteudo = str(texto or "").strip()
    if not conteudo:
        return conteudo

    if "text-align:" in conteudo.lower() and ("<p" in conteudo.lower() or "<div" in conteudo.lower()):
        if "font-weight:" not in conteudo.lower():
            return conteudo.replace(
                "text-align: justify;",
                "text-align: justify; font-weight: bold;",
            )
        return conteudo

    linhas = [linha.strip() for linha in conteudo.splitlines() if linha.strip()]
    if not linhas:
        linhas = [conteudo]

    corpo = "<br />".join(html.escape(linha) for linha in linhas)
    return (
        '<div style="text-align: justify; font-weight: bold;">'
        '<p style="text-align: justify; font-weight: bold; margin: 0;">'
        f"{corpo}"
        "</p></div>"
    )


class GLPIConfigError(Exception):
    """Erro ao carregar ou interpretar conf/glpi.dat."""


def _criar_leitor_configuracao(conf_dir: Optional[str] = None):
    try:
        from python.CONFIGURACAO import clmain
    except ImportError:
        from CONFIGURACAO import clmain

    pasta = conf_dir or _DEFAULT_CONF_DIR
    return clmain(pasta_conf=pasta)


def _valor_texto_config(dados: Dict[str, Any], *chaves: str, obrigatorio: bool = True) -> str:
    for chave in chaves:
        if chave in dados and dados[chave] is not None:
            valor = str(dados[chave]).strip()
            if valor:
                return valor
    if obrigatorio:
        raise GLPIConfigError(
            f"Chave obrigatória ausente em {GLPI_API_CONFIG_FILE}.dat. "
            f"Informe uma de: {', '.join(chaves)}"
        )
    return ""


def carregar_config_glpi(conf_dir: Optional[str] = None) -> Dict[str, str]:
    """
    Carrega os parâmetros de conexão com a API REST do GLPI a partir de
    conf/glpi.dat (criptografado via CONFIGURACAO.py).

    Chaves esperadas:
      GLPI_API_URL, GLPI_APP_TOKEN, GLPI_USER, GLPI_PASSWORD, GLPI_USER_TOKEN
    """
    try:
        try:
            from python.CONFIGURACAO import ConfiguracaoError
        except ImportError:
            from CONFIGURACAO import ConfiguracaoError

        leitor = _criar_leitor_configuracao(conf_dir)
        dados = leitor._obter_Parametros_Configuracao(GLPI_API_CONFIG_FILE)
        logger.debug(
            "%s.dat carregado com %s chave(s)",
            GLPI_API_CONFIG_FILE,
            len(dados),
        )

        return {
            "api_url": _valor_texto_config(
                dados, "GLPI_API_URL", "api_url", "url", "GLPI_URL"
            ),
            "app_token": _valor_texto_config(
                dados, "GLPI_APP_TOKEN", "app_token", "token", "App-Token"
            ),
            "user": _valor_texto_config(
                dados, "GLPI_USER", "user", "usuario", "username", obrigatorio=False
            ),
            "password": _valor_texto_config(
                dados, "GLPI_PASSWORD", "password", "senha", obrigatorio=False
            ),
            "user_token": _valor_texto_config(
                dados, "GLPI_USER_TOKEN", "user_token", obrigatorio=False
            ),
            "pending_reason_id": _valor_texto_config(
                dados,
                "GLPI_PENDING_REASON_ID",
                "pendingreasons_id",
                obrigatorio=False,
            ),
        }

    except ConfiguracaoError as exc:
        logger.error("Falha ao carregar %s.dat: %s", GLPI_API_CONFIG_FILE, exc)
        raise GLPIConfigError(str(exc)) from exc
    except GLPIConfigError:
        raise
    except Exception as exc:
        logger.error("Erro inesperado ao carregar config GLPI: %s", traceback.format_exc())
        raise GLPIConfigError(
            f"Falha ao carregar {GLPI_API_CONFIG_FILE}.dat: {exc}"
        ) from exc


class GLPI_API:
    """
    Classe responsável pela conexão e integração com o GLPI via API REST V1.
    """

    _COLUNAS_CHAMADOS = [
        "Id",
        "Titulo",
        "Categoria",
        "Status",
        "Data de abertura",
        "Data de fechamento",
        "Requerente",
        "Tecnico",
    ]

    def __init__(self, conf_dir: Optional[str] = None) -> None:
        """
        Inicializa a sessão com a API REST do GLPI.

        Args:
            conf_dir: pasta que contém glpi.dat e chave.key (padrão: conf/).
        """
        config = carregar_config_glpi(conf_dir)

        self._api_url = config["api_url"].rstrip("/")
        self._app_token = config["app_token"]
        self._user = config["user"]
        self._password = config["password"]
        self._user_token = config["user_token"]
        self._pending_reason_id_config = config.get("pending_reason_id", "")
        self._pending_reason_id_resolvido: Optional[int] = None
        self._session_token: Optional[str] = None
        self._cache_usuarios: Dict[str, str] = {}

        try:
            self._iniciar_sessao()
        except Exception as exc:
            logger.exception("Falha ao iniciar sessão com a API do GLPI: %s", exc)
            raise

    @classmethod
    def from_config(cls, conf_dir: Optional[str] = None) -> "GLPI_API":
        """Instancia o cliente a partir de conf/glpi.dat (criptografado)."""
        return cls(conf_dir=conf_dir)

    # ------------------------------------------------------------------
    # Métodos públicos solicitados
    # ------------------------------------------------------------------
    def _pesquisar_Chamados_GLPI(
        self, status: Union[int, str, List[int]]
    ) -> pd.DataFrame:
        """
        Pesquisa chamados no GLPI filtrados por status.

        Retorna somente chamados abertos nos últimos DIAS_CHAMADOS_ABERTOS dias.

        Args:
            status: Código numérico do status ou lista de códigos (busca com OR).

        Returns:
            DataFrame com Id, Titulo, Categoria, Status, datas, Requerente e Tecnico.
        """
        try:
            if isinstance(status, (list, tuple)):
                statuses = [int(st) for st in status]
                if not statuses:
                    return self._dataframe_vazio()

                criterios: List[Dict[str, Any]] = []
                for indice, codigo in enumerate(statuses):
                    criterio: Dict[str, Any] = {
                        "field": _TICKET_FIELD_STATUS,
                        "searchtype": "equals",
                        "value": str(codigo),
                    }
                    if indice > 0:
                        criterio["link"] = "OR"
                    criterios.append(criterio)
                return self._buscar_chamados(criterios)

            criterios = [
                {
                    "field": _TICKET_FIELD_STATUS,
                    "searchtype": "equals",
                    "value": str(status),
                }
            ]
            return self._buscar_chamados(criterios)
        except Exception as exc:
            logger.exception(
                "Erro em _pesquisar_Chamados_GLPI (status=%s): %s", status, exc
            )
            return self._dataframe_vazio()

    def _pesquisar_Chamados_GLPI_Usuario(self, usuario: str) -> pd.DataFrame:
        """
        Pesquisa chamados associados a um usuário (técnico ou requerente).

        Retorna somente chamados abertos nos últimos DIAS_CHAMADOS_ABERTOS dias.

        Args:
            usuario: Nome/login do usuário no GLPI.

        Returns:
            DataFrame com os dados dos chamados encontrados.
        """
        try:
            if not usuario or not str(usuario).strip():
                raise ValueError("O argumento 'usuario' não pode ser vazio.")

            login = str(usuario).strip()
            user_id = self._obter_id_usuario_por_nome(login)

            if user_id:
                criterios = [
                    {
                        "field": _TICKET_FIELD_TECHNICIAN,
                        "searchtype": "equals",
                        "value": str(user_id),
                    },
                    {
                        "link": "OR",
                        "field": _TICKET_FIELD_REQUESTER,
                        "searchtype": "equals",
                        "value": str(user_id),
                    },
                ]
            else:
                criterios = [
                    {
                        "field": _TICKET_FIELD_TECHNICIAN,
                        "searchtype": "contains",
                        "value": login,
                    },
                    {
                        "link": "OR",
                        "field": _TICKET_FIELD_REQUESTER,
                        "searchtype": "contains",
                        "value": login,
                    },
                ]

            return self._buscar_chamados(criterios)
        except Exception as exc:
            logger.exception(
                "Erro em _pesquisar_Chamados_GLPI_Usuario (usuario=%s): %s",
                usuario,
                exc,
            )
            return self._dataframe_vazio()

    def _atribuir_Chamado_Tecnico(
        self, numero_chamado: Union[int, str], tecnico: str
    ) -> bool:
        """
        Atribui o chamado ao técnico informado e define status Atribuído (2).

        Args:
            numero_chamado: Identificador do chamado.
            tecnico: Login/nome do técnico no GLPI.

        Returns:
            True se a atribuição foi realizada com sucesso; False caso contrário.
        """
        try:
            ticket_id = int(numero_chamado)
            login_tecnico = str(tecnico or "").strip()
            if not login_tecnico:
                raise ValueError("O argumento 'tecnico' não pode ser vazio.")

            user_id = self.pesquisarCodTec(login_tecnico)
            if user_id == 0:
                logger.error("Técnico '%s' não encontrado no GLPI.", login_tecnico)
                return False

            payload = {
                "input": {
                    "tickets_id": ticket_id,
                    "users_id": user_id,
                    "type": _TICKET_USER_TYPE_ASSIGNED,
                    "use_notification": 1,
                }
            }
            try:
                self._requisicao(
                    f"/Ticket/{ticket_id}/Ticket_User",
                    method="POST",
                    payload=payload,
                    session_write=True,
                )
            except Exception as exc:
                if self._ticket_ja_atribuido_ao_tecnico(ticket_id, user_id):
                    logger.info(
                        "Ticket_User já vincula técnico %s ao chamado %s — seguindo para status.",
                        login_tecnico,
                        ticket_id,
                    )
                else:
                    logger.error(
                        "Falha ao vincular técnico %s ao chamado %s: %s",
                        login_tecnico,
                        ticket_id,
                        exc,
                    )
                    return False

            return self._atribuir_Chamado_Usuario(ticket_id, GLPI_STATUS_ATRIBUIDO)
        except Exception as exc:
            logger.exception(
                "Erro em _atribuir_Chamado_Tecnico (chamado=%s, tecnico=%s): %s",
                numero_chamado,
                tecnico,
                exc,
            )
            return False

    def _obter_motivo_pendencia_id(self) -> Optional[int]:
        """Retorna o ID do motivo de pendência configurado ou o padrão do GLPI."""
        if self._pending_reason_id_resolvido is not None:
            return self._pending_reason_id_resolvido

        if self._pending_reason_id_config:
            try:
                self._pending_reason_id_resolvido = int(self._pending_reason_id_config)
                return self._pending_reason_id_resolvido
            except ValueError:
                logger.warning(
                    "GLPI_PENDING_REASON_ID invalido: %r",
                    self._pending_reason_id_config,
                )

        try:
            resposta = self._requisicao("/PendingReason/", method="GET")
            if isinstance(resposta, list) and resposta:
                for item in resposta:
                    if int(item.get("is_default", 0)) == 1:
                        self._pending_reason_id_resolvido = int(item["id"])
                        return self._pending_reason_id_resolvido
                self._pending_reason_id_resolvido = int(resposta[0]["id"])
                return self._pending_reason_id_resolvido
        except Exception as exc:
            logger.warning("Nao foi possivel obter motivo de pendencia no GLPI: %s", exc)

        return None

    def _chamado_esta_pendente(self, numero_chamado: Union[int, str]) -> bool:
        """Verifica se o chamado esta com status Pendente (4)."""
        try:
            ticket = self._obter_ticket(int(numero_chamado))
            return int(ticket.get("status", 0)) == GLPI_STATUS_PENDENTE
        except Exception as exc:
            logger.warning(
                "Erro ao verificar status pendente do chamado %s: %s",
                numero_chamado,
                exc,
            )
            return False

    def _colocar_Chamado_Pendente(self, numero_chamado: Union[int, str]) -> bool:
        """Define o chamado como Pendente, incluindo motivo quando exigido pelo GLPI."""
        try:
            ticket_id = int(numero_chamado)
            payload_input: Dict[str, Any] = {"status": GLPI_STATUS_PENDENTE}
            motivo_id = self._obter_motivo_pendencia_id()
            if motivo_id is not None:
                payload_input["pendingreasons_id"] = motivo_id

            self._requisicao(
                f"/Ticket/{ticket_id}",
                method="PUT",
                payload={"input": payload_input},
                session_write=True,
            )

            if self._chamado_esta_pendente(ticket_id):
                logger.info("Chamado %s atualizado para status Pendente.", ticket_id)
                return True

            logger.error(
                "Chamado %s nao ficou Pendente apos atualizacao (status atual pode exigir motivo).",
                ticket_id,
            )
            return False
        except Exception as exc:
            logger.exception(
                "Erro em _colocar_Chamado_Pendente (chamado=%s): %s",
                numero_chamado,
                exc,
            )
            return False

    def _atribuir_Chamado_Usuario(
        self, numero_chamado: Union[int, str], situacao: Union[int, str]
    ) -> bool:
        """
        Atualiza a situação (status) de um chamado no GLPI.

        Args:
            numero_chamado: Identificador do chamado.
            situacao: Código numérico do novo status.

        Returns:
            True se a atualização foi realizada com sucesso; False caso contrário.
        """
        try:
            ticket_id = int(numero_chamado)
            novo_status = int(situacao)

            if novo_status == GLPI_STATUS_PENDENTE:
                return self._colocar_Chamado_Pendente(ticket_id)

            payload = {"input": {"status": novo_status}}
            self._requisicao(
                f"/Ticket/{ticket_id}",
                method="PUT",
                payload=payload,
                session_write=True,
            )
            return True
        except Exception as exc:
            logger.exception(
                "Erro em _atribuir_Chamado_Usuario (chamado=%s, situacao=%s): %s",
                numero_chamado,
                situacao,
                exc,
            )
            return False

    def _chamado_Autorizado(self, numero_chamado: Union[int, str]) -> bool:
        """
        Verifica se o chamado foi autorizado (aprovado) no fluxo de validação.

        Args:
            numero_chamado: Identificador do chamado.

        Returns:
            True se global_validation == Aprovado (3); False nos demais casos.
        """
        try:
            ticket = self._obter_ticket(int(numero_chamado))
            return int(ticket.get("global_validation", 0)) == _VALIDATION_ACCEPTED
        except Exception as exc:
            logger.exception(
                "Erro em _chamado_Autorizado (chamado=%s): %s", numero_chamado, exc
            )
            return False

    def _chamado_Avaliado(self, numero_chamado: Union[int, str]) -> bool:
        """
        Verifica se o chamado possui avaliação de satisfação respondida.

        Args:
            numero_chamado: Identificador do chamado.

        Returns:
            True se existir registro de satisfação com data de resposta.
        """
        try:
            satisfacao = self._obter_satisfacao_chamado(int(numero_chamado))
            if not satisfacao:
                return False

            for registro in satisfacao:
                if registro.get("date_answered"):
                    return True
            return False
        except Exception as exc:
            logger.exception(
                "Erro em _chamado_Avaliado (chamado=%s): %s", numero_chamado, exc
            )
            return False

    def _nota_Chamado_Avaliado(self, numero_chamado: Union[int, str]) -> float:
        """
        Retorna a nota de satisfação atribuída ao chamado.

        Args:
            numero_chamado: Identificador do chamado.

        Returns:
            Nota numérica da avaliação ou 0.0 se não houver avaliação respondida.
        """
        try:
            satisfacao = self._obter_satisfacao_chamado(int(numero_chamado))
            if not satisfacao:
                return 0.0

            for registro in satisfacao:
                if registro.get("date_answered") and registro.get("satisfaction") is not None:
                    return float(registro["satisfaction"])
            return 0.0
        except Exception as exc:
            logger.exception(
                "Erro em _nota_Chamado_Avaliado (chamado=%s): %s", numero_chamado, exc
            )
            return 0.0

    def _Adicionar_Resposta_Chamado(
        self,
        resposta: str,
        numero_chamado: Union[int, str],
        is_private: int = 0,
        colocar_pendente: bool = False,
    ) -> bool:
        """
        Adiciona uma resposta (acompanhamento) ao chamado no GLPI.

        Args:
            resposta: Texto da resposta a ser registrada no chamado.
            numero_chamado: Identificador do chamado.
            is_private: 1 para acompanhamento privado; 0 para público.
            colocar_pendente: Se True, marca o chamado como Pendente no acompanhamento.

        Returns:
            True se a resposta foi adicionada com sucesso; False caso contrário.
        """
        try:
            if not resposta or not str(resposta).strip():
                raise ValueError("O argumento 'resposta' não pode ser vazio.")

            ticket_id = int(numero_chamado)
            conteudo_formatado = _formatar_resposta_justificada(str(resposta).strip())
            input_payload: Dict[str, Any] = {
                "itemtype": "Ticket",
                "items_id": ticket_id,
                "content": conteudo_formatado,
                "is_private": int(is_private),
                "requesttypes_id": 1,
            }
            if colocar_pendente:
                input_payload["pending"] = 1
                motivo_id = self._obter_motivo_pendencia_id()
                if motivo_id is not None:
                    input_payload["pendingreasons_id"] = motivo_id

            payload = {"input": input_payload}
            self._requisicao(
                "/ITILFollowup",
                method="POST",
                payload=payload,
                session_write=True,
            )
            return True
        except Exception as exc:
            logger.exception(
                "Erro em _Adicionar_Resposta_Chamado (chamado=%s): %s",
                numero_chamado,
                exc,
            )
            return False

    def _Ler_Resposta_Chamado(
        self, numero_chamado: Union[int, str]
    ) -> List[Dict[str, Any]]:
        """
        Retorna todas as respostas (acompanhamentos) do chamado.

        Args:
            numero_chamado: Identificador do chamado.

        Returns:
            Lista de registros de acompanhamento do chamado.
        """
        try:
            return self._obter_followups_chamado(int(numero_chamado))
        except Exception as exc:
            logger.exception(
                "Erro em _Ler_Resposta_Chamado (chamado=%s): %s",
                numero_chamado,
                exc,
            )
            return []

    def _chamado_existe_no_GLPI(self, numero_chamado: Union[int, str]) -> bool:
        """
        Verifica se o chamado existe no GLPI.

        Args:
            numero_chamado: Identificador do chamado.

        Returns:
            True se o chamado existir; False caso contrário.
        """
        try:
            ticket = self._obter_ticket(int(numero_chamado))
            return bool(ticket and ticket.get("id"))
        except Exception as exc:
            logger.warning(
                "Erro ao verificar existencia do chamado %s: %s", numero_chamado, exc
            )
            return False

    @staticmethod
    def _normalizar_texto_resposta(conteudo: Any) -> str:
        """Remove tags HTML e normaliza texto de acompanhamentos GLPI."""
        texto = html.unescape(str(conteudo or ""))
        texto = re.sub(r"<[^>]+>", " ", texto)
        return " ".join(texto.split()).lower()

    def _conteudo_e_resposta_sgac(self, conteudo: object) -> bool:
        """Indica se o acompanhamento foi gerado pela aplicacao SGAC."""
        texto = self._normalizar_texto_resposta(conteudo)
        for marcador in _MARCADORES_RESPOSTA_PROCESSADO:
            if marcador.lower() in texto:
                return True
        return False

    def _chamado_possui_resposta_usuario_apos_sgac(
        self, numero_chamado: Union[int, str]
    ) -> bool:
        """Verifica se houve resposta do usuario apos o ultimo acompanhamento SGAC."""
        try:
            respostas = self._Ler_Resposta_Chamado(int(numero_chamado))
            if not respostas:
                return False

            respostas_ordenadas = sorted(
                respostas,
                key=lambda registro: str(
                    registro.get("date") or registro.get("date_creation") or ""
                ),
            )

            ultimo_indice_sgac = -1
            for indice, registro in enumerate(respostas_ordenadas):
                if self._conteudo_e_resposta_sgac(registro.get("content")):
                    ultimo_indice_sgac = indice

            if ultimo_indice_sgac < 0:
                return False

            for registro in respostas_ordenadas[ultimo_indice_sgac + 1 :]:
                if int(registro.get("is_private", 0)) == 1:
                    continue
                if self._conteudo_e_resposta_sgac(registro.get("content")):
                    continue
                if self._normalizar_texto_resposta(registro.get("content")):
                    return True

            return False
        except Exception as exc:
            logger.warning(
                "Erro ao verificar respostas do usuario no chamado %s: %s",
                numero_chamado,
                exc,
            )
            return False

    def _chamado_possui_resposta_processamento(self, numero_chamado: Union[int, str]) -> bool:
        """Verifica se o chamado já possui resposta registrada pela aplicação SGAC."""
        try:
            respostas = self._Ler_Resposta_Chamado(int(numero_chamado))
            for registro in respostas:
                if self._conteudo_e_resposta_sgac(registro.get("content")):
                    return True
            return False
        except Exception as exc:
            logger.warning(
                "Erro ao verificar respostas do chamado %s: %s", numero_chamado, exc
            )
            return False

    def _chamado_ja_processado_no_GLPI(self, numero_chamado: Union[int, str]) -> bool:
        """
        Verifica no GLPI se o chamado já foi tratado pela aplicação.

        Considera processado quando:
          - o chamado não existe;
          - o status não é Atribuído (2) nem Pendente (4);
          - já existe acompanhamento SGAC e não há nova resposta do usuário (pendente).
        """
        try:
            if not self._chamado_existe_no_GLPI(numero_chamado):
                logger.info(
                    "Chamado %s nao encontrado no GLPI — ignorado.", numero_chamado
                )
                return True

            ticket = self._obter_ticket(int(numero_chamado))
            status = int(ticket.get("status", 0))
            if status not in (GLPI_STATUS_ATRIBUIDO, GLPI_STATUS_PENDENTE):
                logger.debug(
                    "Chamado %s com status %s — ja tratado ou fora do monitoramento.",
                    numero_chamado,
                    status,
                )
                return True

            if not self._chamado_possui_resposta_processamento(numero_chamado):
                return False

            if status == GLPI_STATUS_PENDENTE:
                if self._chamado_possui_resposta_usuario_apos_sgac(numero_chamado):
                    logger.info(
                        "Chamado %s pendente com nova resposta do usuario — reprocessar.",
                        numero_chamado,
                    )
                    return False

                logger.debug(
                    "Chamado %s pendente aguardando retorno do usuario.", numero_chamado
                )
                return True

            logger.debug(
                "Chamado %s possui resposta SGAC — ja processado.", numero_chamado
            )
            return True
        except Exception as exc:
            logger.exception(
                "Erro em _chamado_ja_processado_no_GLPI (chamado=%s): %s",
                numero_chamado,
                exc,
            )
            return True

    def _Registrar_Chamado_Analisado_SGAC(
        self, numero_chamado: Union[int, str]
    ) -> bool:
        """
        Registra acompanhamento privado indicando analise sem tarefa automatizada.

        Args:
            numero_chamado: Identificador do chamado.

        Returns:
            True se o registro foi realizado; False em caso de erro.
        """
        return self._Adicionar_Resposta_Chamado(
            _MARCADOR_SGAC_ANALISADO,
            numero_chamado,
            is_private=1,
        )

    def pesquisarQtdChamadosTec(self, ref_usu: str) -> int:
        """
        Retorna a quantidade de chamados atribuídos ao técnico informado.

        Considera chamados com status 2 (Em atendimento) ou 3 (Planejado),
        equivalente à consulta SQL utilizada no módulo GLPI legado.

        Args:
            ref_usu: Login/nome do técnico no GLPI.

        Returns:
            Total de chamados atribuídos ao técnico ou 0 em caso de erro.
        """
        try:
            if not ref_usu or not str(ref_usu).strip():
                raise ValueError("O argumento 'ref_usu' não pode ser vazio.")

            user_id = self.pesquisarCodTec(ref_usu)
            if user_id == 0:
                return 0

            total = 0
            for status in (2, 3):
                criterios = [
                    {
                        "field": _TICKET_FIELD_TECHNICIAN,
                        "searchtype": "equals",
                        "value": str(user_id),
                    },
                    {
                        "link": "AND",
                        "field": _TICKET_FIELD_STATUS,
                        "searchtype": "equals",
                        "value": str(status),
                    },
                ]
                total += self._contar_chamados(criterios)

            return total
        except Exception as exc:
            logger.exception(
                "Erro em pesquisarQtdChamadosTec (ref_usu=%s): %s", ref_usu, exc
            )
            return 0

    def pesquisarCodTec(self, ref_usu: str) -> int:
        """
        Retorna o código (ID) do usuário/técnico no GLPI.

        Args:
            ref_usu: Login/nome do usuário no GLPI.

        Returns:
            ID numérico do usuário ou 0 se não encontrado.
        """
        try:
            if not ref_usu or not str(ref_usu).strip():
                raise ValueError("O argumento 'ref_usu' não pode ser vazio.")

            user_id = self._obter_id_usuario_por_nome(str(ref_usu).strip())
            return int(user_id) if user_id else 0
        except Exception as exc:
            logger.exception(
                "Erro em pesquisarCodTec (ref_usu=%s): %s", ref_usu, exc
            )
            return 0

    def encerrar_sessao(self) -> None:
        """Encerra a sessão ativa na API do GLPI, se existir."""
        if not self._session_token:
            return

        try:
            self._requisicao("/killSession", method="GET")
        except Exception as exc:
            logger.warning("Erro ao encerrar sessão GLPI: %s", exc)
        finally:
            self._session_token = None

    def search_tickets_ativos(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Mesma lógica do front GLPI (ticket.php): status = notold, sort date_mod DESC.

        Não aplica o filtro de N dias do worker — lista todos os ativos como o GLPI.
        """
        offset = max(0, int(offset))
        limit = max(1, min(100, int(limit)))
        fim = offset + limit - 1

        criterios: List[Dict[str, str]] = [
            {
                "field": _TICKET_FIELD_STATUS,
                "searchtype": "equals",
                "value": "notold",
            }
        ]
        q = (search or "").strip()
        if q:
            if q.isdigit():
                criterios.append(
                    {
                        "link": "AND",
                        "field": _TICKET_FIELD_ID,
                        "searchtype": "equals",
                        "value": q,
                    }
                )
            else:
                criterios.append(
                    {
                        "link": "AND",
                        "field": _TICKET_FIELD_TITLE,
                        "searchtype": "contains",
                        "value": q,
                    }
                )

        parametros = self._montar_parametros_busca(criterios, offset, fim)
        # field 19 = date_mod (última alteração) — igual ao sort do front
        parametros.append(("sort[0]", "19"))
        parametros.append(("order[0]", "DESC"))
        parametros.append((f"forcedisplay[{len(_TICKET_FORCED_DISPLAY)}]", "19"))

        url = f"{self._api_url}/search/Ticket?{urlencode(parametros, doseq=True)}"
        resposta = self._requisicao_url_completa(url, method="GET")
        total = int(resposta.get("totalcount", 0) or 0)
        items: List[Dict[str, Any]] = []
        for linha in resposta.get("data") or []:
            norm = self._normalizar_linha_chamado(linha)
            items.append(
                {
                    "id": int(norm["Id"]) if norm.get("Id") is not None else None,
                    "titulo": norm.get("Titulo"),
                    "categoria": norm.get("Categoria"),
                    "status": norm.get("Status"),
                    "status_id": linha.get(_TICKET_FIELD_STATUS),
                    "data_abertura": norm.get("Data de abertura"),
                    "data_fechamento": norm.get("Data de fechamento"),
                    "data_mod": linha.get("19"),
                    "solicitante": norm.get("Requerente"),
                    "tecnico": norm.get("Tecnico"),
                }
            )
        return total, items

    # ------------------------------------------------------------------
    # Métodos internos de suporte
    # ------------------------------------------------------------------
    def _iniciar_sessao(self) -> None:
        """Obtém session_token via initSession."""
        headers = {
            "Content-Type": "application/json",
            "App-Token": self._app_token,
        }

        if self._user and self._password:
            credenciais = base64.b64encode(
                f"{self._user}:{self._password}".encode("utf-8")
            ).decode("utf-8")
            headers["Authorization"] = f"Basic {credenciais}"
        elif self._user_token:
            headers["Authorization"] = f"user_token {self._user_token}"
        else:
            raise ValueError(
                "Informe GLPI_USER/GLPI_PASSWORD ou GLPI_USER_TOKEN em "
                f"{GLPI_API_CONFIG_FILE}.dat para autenticação."
            )

        resposta = self._executar_http(
            f"{self._api_url}/initSession",
            method="GET",
            headers=headers,
        )
        self._session_token = resposta.get("session_token")

        if not self._session_token:
            raise ConnectionError("A API do GLPI não retornou session_token.")

    def _buscar_chamados(self, criterios: List[Dict[str, str]]) -> pd.DataFrame:
        """Executa busca paginada de chamados e retorna DataFrame normalizado."""
        criterios = _aplicar_filtro_abertura_recente(criterios)
        registros: List[Dict[str, Any]] = []
        inicio = 0

        while True:
            fim = inicio + GLPI_SEARCH_PAGE_SIZE - 1
            parametros = self._montar_parametros_busca(criterios, inicio, fim)
            url = f"{self._api_url}/search/Ticket?{urlencode(parametros, doseq=True)}"

            resposta = self._requisicao_url_completa(url, method="GET")
            dados = resposta.get("data", [])

            for linha in dados:
                registros.append(self._normalizar_linha_chamado(linha))

            total = int(resposta.get("totalcount", 0))
            if fim + 1 >= total:
                break
            inicio += GLPI_SEARCH_PAGE_SIZE

        return pd.DataFrame(registros, columns=self._COLUNAS_CHAMADOS)

    def _contar_chamados(self, criterios: List[Dict[str, str]]) -> int:
        """Retorna apenas a quantidade total de chamados para os critérios informados."""
        parametros = self._montar_parametros_busca(criterios, 0, 0)
        parametros = [
            param for param in parametros if not param[0].startswith("forcedisplay")
        ]
        url = f"{self._api_url}/search/Ticket?{urlencode(parametros, doseq=True)}"
        resposta = self._requisicao_url_completa(url, method="GET")
        return int(resposta.get("totalcount", 0))

    def _montar_parametros_busca(
        self, criterios: List[Dict[str, str]], inicio: int, fim: int
    ) -> List[tuple]:
        """Monta parâmetros da URL para o endpoint search/Ticket."""
        parametros: List[tuple] = [("range", f"{inicio}-{fim}")]

        for indice, criterio in enumerate(criterios):
            for chave, valor in criterio.items():
                parametros.append((f"criteria[{indice}][{chave}]", str(valor)))

        for indice, campo in enumerate(_TICKET_FORCED_DISPLAY):
            parametros.append((f"forcedisplay[{indice}]", campo))

        return parametros

    def _normalizar_linha_chamado(self, linha: Dict[str, Any]) -> Dict[str, Any]:
        """Converte uma linha da busca GLPI para o formato do DataFrame."""
        status_bruto = linha.get(_TICKET_FIELD_STATUS)
        status_texto = _STATUS_LABELS.get(int(status_bruto), str(status_bruto))

        return {
            "Id": linha.get(_TICKET_FIELD_ID),
            "Titulo": linha.get(_TICKET_FIELD_TITLE),
            "Categoria": linha.get(_TICKET_FIELD_CATEGORY),
            "Status": status_texto,
            "Data de abertura": linha.get(_TICKET_FIELD_OPEN_DATE),
            "Data de fechamento": linha.get(_TICKET_FIELD_CLOSE_DATE),
            "Requerente": self._resolver_nome_usuario(linha.get(_TICKET_FIELD_REQUESTER)),
            "Tecnico": self._resolver_nome_usuario(linha.get(_TICKET_FIELD_TECHNICIAN)),
        }

    def _resolver_nome_usuario(self, valor: Any) -> Optional[str]:
        """Converte ID numérico de usuário em login/nome via API User."""
        if valor is None or valor == "":
            return None

        valor_str = str(valor).strip()
        if not valor_str.isdigit():
            return valor_str

        if valor_str in self._cache_usuarios:
            return self._cache_usuarios[valor_str]

        try:
            usuario = self._requisicao(f"/User/{valor_str}", method="GET")
            nome = usuario.get("name", valor_str)
            self._cache_usuarios[valor_str] = nome
            return nome
        except Exception as exc:
            logger.warning("Não foi possível resolver usuário %s: %s", valor_str, exc)
            return valor_str

    def _obter_id_usuario_por_nome(self, login: str) -> Optional[str]:
        """Localiza o ID do usuário GLPI a partir do login."""
        parametros = [
            ("criteria[0][field]", "1"),
            ("criteria[0][searchtype]", "under"),
            ("criteria[0][value]", login),
            ("forcedisplay[0]", "2"),
            ("forcedisplay[1]", "1"),
            ("range", "0-49"),
        ]
        url = f"{self._api_url}/search/User?{urlencode(parametros)}"

        try:
            resposta = self._requisicao_url_completa(url, method="GET")
            dados = resposta.get("data", [])
            if not dados:
                return None

            login_normalizado = login.strip().lower()
            for linha in dados:
                nome = str(linha.get("1", "")).strip()
                if nome.lower() == login_normalizado:
                    return str(linha.get("2"))

            return str(dados[0].get("2"))
        except Exception as exc:
            logger.warning("Não foi possível localizar usuário '%s': %s", login, exc)
            return None

    def _obter_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """Obtém os dados completos de um chamado."""
        return self._requisicao(f"/Ticket/{ticket_id}", method="GET")

    def _ticket_ja_atribuido_ao_tecnico(
        self, ticket_id: int, user_id: int
    ) -> bool:
        """True se o Ticket_User type=assigned já aponta para este users_id."""
        try:
            resposta = self._requisicao(
                f"/Ticket/{ticket_id}/Ticket_User",
                method="GET",
            )
            if not isinstance(resposta, list):
                return False
            uid = int(user_id)
            for registro in resposta:
                if int(registro.get("type", 0)) != _TICKET_USER_TYPE_ASSIGNED:
                    continue
                try:
                    if int(registro.get("users_id", 0)) == uid:
                        return True
                except (TypeError, ValueError):
                    continue
            return False
        except Exception as exc:
            logger.warning(
                "Não foi possível verificar Ticket_User do chamado %s: %s",
                ticket_id,
                exc,
            )
            return False

    def _obter_tecnico_atribuido_chamado(
        self, numero_chamado: Union[int, str]
    ) -> Optional[str]:
        """
        Retorna o login/nome do técnico atribuído ao chamado no GLPI.

        Args:
            numero_chamado: Identificador do chamado.

        Returns:
            Login do técnico atribuído ou None se não houver.
        """
        try:
            ticket_id = int(numero_chamado)
            resposta = self._requisicao(
                f"/Ticket/{ticket_id}/Ticket_User",
                method="GET",
            )
            if not isinstance(resposta, list):
                return None

            for registro in resposta:
                if int(registro.get("type", 0)) != _TICKET_USER_TYPE_ASSIGNED:
                    continue
                nome = self._resolver_nome_usuario(registro.get("users_id"))
                if nome:
                    return str(nome).strip()
            return None
        except Exception as exc:
            logger.warning(
                "Erro ao obter tecnico do chamado %s: %s", numero_chamado, exc
            )
            return None

    def _obter_satisfacao_chamado(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Obtém registros de satisfação vinculados ao chamado."""
        resposta = self._requisicao(
            f"/Ticket/{ticket_id}/TicketSatisfaction",
            method="GET",
        )
        if isinstance(resposta, list):
            return resposta
        return []

    def _obter_followups_chamado(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Obtém acompanhamentos (respostas) vinculados ao chamado."""
        resposta = self._requisicao(
            f"/Ticket/{ticket_id}/ITILFollowup",
            method="GET",
        )
        if isinstance(resposta, list):
            return resposta
        return []

    def _requisicao(
        self,
        endpoint: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        session_write: bool = False,
    ) -> Any:
        """Executa requisição autenticada com renovação automática de sessão."""
        url = f"{self._api_url}{endpoint}"
        if session_write:
            separador = "&" if "?" in url else "?"
            url = f"{url}{separador}session_write=true"
        return self._requisicao_url_completa(url, method, payload)

    def _requisicao_url_completa(
        self,
        url: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Executa HTTP autenticado; tenta reautenticar uma vez em caso de sessão inválida."""
        try:
            return self._executar_http(url, method, payload, autenticado=True)
        except HTTPError as exc:
            if self._sessao_invalida(exc):
                logger.warning("Sessão GLPI inválida. Reautenticando...")
                self._iniciar_sessao()
                return self._executar_http(url, method, payload, autenticado=True)
            raise

    def _executar_http(
        self,
        url: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        autenticado: bool = False,
    ) -> Any:
        """Executa uma requisição HTTP e decodifica a resposta JSON."""
        cabecalhos = {"Content-Type": "application/json"}
        if headers:
            cabecalhos.update(headers)

        if autenticado:
            if not self._session_token:
                raise ConnectionError("Sessão GLPI não iniciada.")
            cabecalhos["Session-Token"] = self._session_token
            cabecalhos["App-Token"] = self._app_token

        dados = None
        if payload is not None:
            dados = json.dumps(payload).encode("utf-8")

        requisicao = Request(url, data=dados, headers=cabecalhos, method=method.upper())

        try:
            with urlopen(requisicao, timeout=GLPI_REQUEST_TIMEOUT) as resposta:
                conteudo = resposta.read().decode("utf-8")
                if not conteudo:
                    return {}
                return json.loads(conteudo)
        except HTTPError as exc:
            mensagem = exc.read().decode("utf-8", errors="replace")
            logger.error("Erro HTTP %s em %s: %s", exc.code, url, mensagem)
            raise
        except URLError as exc:
            logger.error("Erro de conexão em %s: %s", url, exc)
            raise

    @staticmethod
    def _sessao_invalida(exc: HTTPError) -> bool:
        """Verifica se o erro HTTP indica sessão inválida."""
        try:
            corpo = exc.read().decode("utf-8", errors="replace")
            return "ERROR_SESSION_TOKEN_INVALID" in corpo
        except Exception:
            return exc.code in (401, 403)

    @classmethod
    def _dataframe_vazio(cls) -> pd.DataFrame:
        """Retorna DataFrame vazio com colunas padronizadas."""
        return pd.DataFrame(columns=cls._COLUNAS_CHAMADOS)

    def __del__(self) -> None:
        try:
            self.encerrar_sessao()
        except Exception:
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    api = GLPI_API()

    usuarios_teste = ["andrew.silva", "ana.oliveira", "usuario.inexistente"]

    print("=== Testes pesquisarCodTec / pesquisarQtdChamadosTec ===")
    for usuario in usuarios_teste:
        codigo = api.pesquisarCodTec(usuario)
        quantidade = api.pesquisarQtdChamadosTec(usuario)
        print(f"Usuario: {usuario} | Codigo: {codigo} | Qtd chamados (status 2/3): {quantidade}")

    api.encerrar_sessao()
