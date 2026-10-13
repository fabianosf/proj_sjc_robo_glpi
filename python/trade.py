# trade.py — fachada SGC sobre GLPI_API (conf/glpi.dat)

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import pandas as pd

import os

from GLPI_API import DIAS_CHAMADOS_ABERTOS, GLPI_API
from logger import ClLog


def print_debug(classe, metodo, mensagem):
    pass


def _dias_chamados_abertos() -> int:
    try:
        return max(1, int(os.getenv("SGC_GLPI_DIAS_ABERTOS", str(DIAS_CHAMADOS_ABERTOS)) or DIAS_CHAMADOS_ABERTOS))
    except (TypeError, ValueError):
        return max(1, int(DIAS_CHAMADOS_ABERTOS))


def _glpi_fetch_limit() -> int:
    try:
        from GLPI_API import GLPI_FETCH_LIMIT as _default_limit
    except ImportError:
        _default_limit = 300
    try:
        return max(1, min(1000, int(os.getenv("SGC_GLPI_FETCH_LIMIT", str(_default_limit)) or _default_limit)))
    except (TypeError, ValueError):
        return 300


class ClTrade:
    """Compatibilidade com código legado; toda conexão GLPI via conf/glpi.dat."""

    logger = ClLog()

    def __init__(
        self,
        url: Optional[str] = None,
        app_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        user_token: Optional[str] = None,
        conf_dir: Optional[str] = None,
        **kwargs,
    ):
        if any([url, app_token, username, password, user_token]):
            self.logger.registrarActionLog(
                "GLPI",
                "AVISO",
                "Credenciais passadas ao ClTrade são ignoradas — usando conf/glpi.dat",
            )

        self._glpi = GLPI_API.from_config(conf_dir)
        self.base_url = self._glpi._api_url
        self.app_token = self._glpi._app_token
        self.session_token = self._glpi._session_token
        self.user_id_cache: Dict[str, int] = {}
        self.category_name_cache: Dict[int, str] = {}
        self.location_name_cache: Dict[int, str] = {}

    def _get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"
        return self._glpi._requisicao_url_completa(url, method="GET")

    def pesquisarSolicitanteDoChamado(self, ticket_id: int) -> str:
        if not ticket_id:
            return "N/A"
        try:
            ticket_users = self._glpi._requisicao(f"/Ticket/{ticket_id}/Ticket_User", method="GET")
            for user in ticket_users:
                if user.get("type") == 1:
                    return self.get_user_name_by_id(user.get("users_id"))
            return "N/A"
        except Exception as e:
            print_debug("ClTrade", "pesquisarSolicitanteDoChamado", str(e))
            return "N/A"

    def pesquisarTecnicoDoChamado(self, ticket_id: int) -> str:
        if not ticket_id:
            return ""
        try:
            return self._glpi._obter_tecnico_atribuido_chamado(ticket_id) or ""
        except Exception as e:
            print_debug("ClTrade", "pesquisarTecnicoDoChamado", str(e))
            return ""

    def get_user_name_by_id(self, user_id: int) -> str:
        if not user_id:
            return "N/A"
        try:
            data = self._glpi._requisicao(f"/User/{user_id}", method="GET")
            nome = data.get("firstname", "")
            sobrenome = data.get("realname", "")
            full = f"{nome} {sobrenome}".strip()
            return full or data.get("name", "N/A")
        except Exception:
            return "N/A"

    def get_user_login_by_id(self, user_id: int) -> str:
        if not user_id:
            return ""
        cache_key = f"login_{user_id}"
        if cache_key in self.user_id_cache:
            return str(self.user_id_cache[cache_key])
        try:
            login = str(self._glpi._requisicao(f"/User/{user_id}", method="GET").get("name", "") or "").strip()
            self.user_id_cache[cache_key] = login
            return login
        except Exception:
            return ""

    def get_category_name_by_id(self, category_id: int) -> str:
        if not category_id:
            return "N/A"
        if category_id in self.category_name_cache:
            return self.category_name_cache[category_id]
        try:
            data = self._glpi._requisicao(f"/ITILCategory/{category_id}", method="GET")
            name = data.get("completename") or data.get("name", "N/A")
            self.category_name_cache[category_id] = name
            return name
        except Exception:
            return str(category_id)

    def get_location_name_by_id(self, location_id: int) -> str:
        if not location_id:
            return "N/A"
        if location_id in self.location_name_cache:
            return self.location_name_cache[location_id]
        try:
            data = self._glpi._requisicao(f"/Location/{location_id}", method="GET")
            name = data.get("completename") or data.get("name", "N/A")
            self.location_name_cache[location_id] = name
            return name
        except Exception:
            return str(location_id)

    def pesquisarChamadosSituacao(self, status_id: int) -> Optional[pd.DataFrame]:
        if not self.session_token:
            return None
        try:
            dias = _dias_chamados_abertos()
            limit = _glpi_fetch_limit()
            limite_abertura = datetime.now() - timedelta(days=dias)
            range_end = max(0, limit - 1)
            params = {
                "is_deleted": 0,
                "sort": "date",
                "order": "desc",
                "range": f"0-{range_end}",
                "get_hateoas": "false",
                "criteria[0][field]": "status",
                "criteria[0][searchtype]": "equals",
                "criteria[0][value]": status_id,
                "_": int(time.time()),
            }
            chamados_brutos = self._get("/Ticket", params)
            if not isinstance(chamados_brutos, list):
                chamados_brutos = []
            # Página cheia ⇒ pode haver mais Novos além do range
            fetch_truncated = len(chamados_brutos) >= limit
            chamados_filtrados = [ch for ch in chamados_brutos if ch.get("status") == status_id]
            if not chamados_filtrados:
                empty = pd.DataFrame()
                empty.attrs["fetch_truncated"] = fetch_truncated
                empty.attrs["fetch_limit"] = limit
                return empty

            dados = []
            for ch in chamados_filtrados:
                ticket_id = ch.get("id")
                try:
                    data_dt = pd.to_datetime(ch.get("date"))
                except Exception:
                    continue
                if data_dt < limite_abertura:
                    continue

                tecnico_id = 0
                if ch.get("users_id_assign"):
                    assign_info = ch["users_id_assign"]
                    tecnico_id = (
                        assign_info[0]
                        if isinstance(assign_info, list) and assign_info
                        else assign_info if isinstance(assign_info, int) else 0
                    )

                dados.append(
                    {
                        "ID": ticket_id,
                        "Status": ch.get("status"),
                        "Titulo": ch.get("name", "N/A"),
                        "Categoria": self.get_category_name_by_id(ch.get("itilcategories_id", 0)),
                        "Descricao": re.sub(re.compile("<.*?>"), "", ch.get("content", "")).replace("\xa0", " "),
                        "Solicitante": self.pesquisarSolicitanteDoChamado(ticket_id),
                        "Usuario": self.get_user_name_by_id(tecnico_id),
                        "Data": ch.get("date"),
                        "Datsol": ch.get("time_to_resolve"),
                        "Localizacao": self.get_location_name_by_id(ch.get("locations_id", 0)),
                    }
                )
            df = pd.DataFrame(dados)
            df.attrs["fetch_truncated"] = fetch_truncated
            df.attrs["fetch_limit"] = limit
            if fetch_truncated:
                self.logger.registrarActionLog(
                    "GLPI",
                    "AVISO",
                    f"FETCH TRUNCADO status={status_id} limit={limit} "
                    f"brutos={len(chamados_brutos)} filtrados={len(dados)}",
                )
            return df
        except Exception as e:
            print_debug("ClTrade", "pesquisarChamadosSituacao", str(e))
            self.logger.registarExceptionLog("MAIN", "EXCEPTION", "ERRO DURANTE PESQUISA DE CHAMADOS", e)
            return None

    def _get_user_id_by_name(self, nome_usuario: str) -> Optional[int]:
        codigo = self._glpi.pesquisarCodTec(nome_usuario)
        return codigo if codigo else None

    def tecnico_existe_glpi(self, nome_tecnico: str) -> bool:
        login = str(nome_tecnico or "").strip()
        if not login:
            return False
        return bool(self._glpi.pesquisarCodTec(login))

    def atribuirChamadoTecnico(self, ticket_id: int, nome_tecnico: str) -> Optional[Dict]:
        ok = self._glpi._atribuir_Chamado_Tecnico(ticket_id, nome_tecnico)
        return {"ok": ok} if ok else None

    def count_user_tickets_by_status(self, nome_usuario: str, status_id: int) -> int:
        user_id = self._get_user_id_by_name(nome_usuario)
        if not user_id:
            return 0
        try:
            params = [
                ("criteria[0][field]", "5"),
                ("criteria[0][searchtype]", "equals"),
                ("criteria[0][value]", str(user_id)),
                ("criteria[1][link]", "AND"),
                ("criteria[1][field]", "12"),
                ("criteria[1][searchtype]", "equals"),
                ("criteria[1][value]", str(status_id)),
                ("range", "0-0"),
            ]
            url = f"{self.base_url}/search/Ticket?{urlencode(params)}"
            resposta = self._glpi._requisicao_url_completa(url, method="GET")
            return int(resposta.get("totalcount", 0))
        except Exception:
            return 0

    def verificarChamadoExiste(self) -> bool:
        try:
            params = {
                "is_deleted": 0,
                "range": "0-1",
                "criteria[0][field]": "status",
                "criteria[0][searchtype]": "equals",
                "criteria[0][value]": 1,
            }
            data = self._get("/Ticket", params)
            return isinstance(data, list) and len(data) > 0
        except Exception:
            return False

    def listarChamadosRecentes(self, limit: int = 50):
        status_map = {
            1: "Novo",
            2: "Em atendimento (atribuído)",
            3: "Em atendimento (planejado)",
            4: "Pendente",
            5: "Solucionado",
            6: "Fechado",
        }
        try:
            params = {
                "is_deleted": 0,
                "sort": "id",
                "order": "desc",
                "range": f"0-{limit}",
                "get_hateoas": "false",
            }
            chamados_brutos = self._get("/Ticket", params)
            if not chamados_brutos:
                return []
            return [
                {
                    "id": ch.get("id"),
                    "status_id": ch.get("status", 0),
                    "status_nome": status_map.get(ch.get("status", 0), "Desconhecido"),
                }
                for ch in chamados_brutos
            ]
        except Exception as e:
            print(f"[ERRO GERAL] listarChamadosRecentes: {e}")
            return None

    def pesquisarChamadosFechadosPeriodo(self, meses: int = 6, batch_size: int = 500) -> Optional[pd.DataFrame]:
        if not self.session_token:
            return None
        try:
            data_limite = datetime.now() - timedelta(days=meses * 30)
            data_limite_str = data_limite.strftime("%Y-%m-%d %H:%M:%S")
            dados = []
            start = 0

            while True:
                end = start + batch_size - 1
                params = {
                    "is_deleted": 0,
                    "range": f"{start}-{end}",
                    "sort": "closedate",
                    "order": "DESC",
                    "get_hateoas": "false",
                    "criteria[0][field]": "12",
                    "criteria[0][searchtype]": "equals",
                    "criteria[0][value]": "6",
                    "criteria[1][link]": "AND",
                    "criteria[1][field]": "16",
                    "criteria[1][searchtype]": "morethan",
                    "criteria[1][value]": data_limite_str,
                    "forcedisplay[0]": "2",
                    "forcedisplay[1]": "1",
                    "forcedisplay[2]": "21",
                    "forcedisplay[3]": "15",
                    "forcedisplay[4]": "16",
                    "forcedisplay[5]": "7",
                    "forcedisplay[6]": "5",
                    "forcedisplay[7]": "3",
                    "_": int(time.time()),
                }
                lote = self._get("/Ticket", params)
                if not lote:
                    break

                for ch in lote:
                    if ch.get("status") != 6:
                        continue

                    ticket_id = ch.get("2") if "2" in ch else ch.get("id")
                    titulo = ch.get("1") if "1" in ch else ch.get("name", "N/A")
                    descricao_raw = ch.get("21") if "21" in ch else ch.get("content", "")
                    data_abertura = ch.get("15") if "15" in ch else ch.get("date")
                    data_fechamento = ch.get("16") if "16" in ch else ch.get("closedate")
                    categoria_id = ch.get("7") if "7" in ch else ch.get("itilcategories_id", 0)
                    location_id = ch.get("3") if "3" in ch else ch.get("locations_id", 0)
                    assign_info = ch.get("5") if "5" in ch else ch.get("users_id_assign")

                    if not ticket_id:
                        continue

                    try:
                        if data_fechamento and pd.to_datetime(data_fechamento) < data_limite:
                            continue
                    except Exception:
                        pass

                    tecnico_id = 0
                    if assign_info:
                        tecnico_id = (
                            assign_info[0]
                            if isinstance(assign_info, list) and assign_info
                            else assign_info if isinstance(assign_info, int) else 0
                        )

                    tecnico_login = self.get_user_login_by_id(tecnico_id) if tecnico_id else ""
                    if not tecnico_login:
                        tecnico_login = self.pesquisarTecnicoDoChamado(int(ticket_id))

                    dados.append(
                        {
                            "ID": int(ticket_id),
                            "Titulo": titulo or "N/A",
                            "Categoria": self.get_category_name_by_id(categoria_id or 0),
                            "Descricao": re.sub(re.compile("<.*?>"), "", str(descricao_raw or "")).replace("\xa0", " "),
                            "Tecnico": tecnico_login,
                            "Localizacao": self.get_location_name_by_id(location_id or 0),
                            "Data_Abertura": data_abertura,
                            "Data_Fechamento": data_fechamento,
                        }
                    )

                if len(lote) < batch_size:
                    break
                start += batch_size
                time.sleep(0.15)

            return pd.DataFrame(dados) if dados else pd.DataFrame()
        except Exception as e:
            print_debug("ClTrade", "pesquisarChamadosFechadosPeriodo", str(e))
            self.logger.registarExceptionLog("MAIN", "EXCEPTION", "ERRO AO BUSCAR CHAMADOS FECHADOS GLPI", e)
            return None

    def __del__(self):
        try:
            self._glpi.encerrar_sessao()
        except Exception:
            pass
