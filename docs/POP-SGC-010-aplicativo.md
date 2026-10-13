# POP-SGC-010 — Aplicativo SGC (completo e enxuto)

| Campo | Valor |
|-------|--------|
| **Código** | POP-SGC-010 |
| **Versão** | 2.1 |
| **Data** | 2026-10-03 |
| **Substitui** | POP-SGC-001 (visão expandida) para uso diário |
| **Owner** | Matrícula 59817 (ADMIN) |

---

## 1. O que é

Sistema interno de **atribuição automática de chamados GLPI** + **Control Center** (consulta + ações ADMIN).

| Componente | Função |
|------------|--------|
| **Worker** | Monitora GLPI, classifica equipe, atribui técnico, grava MariaDB |
| **API** | FastAPI + login AD; leituras para todos os perfis autorizados; escritas só **ADMIN** |
| **Frontend** | Control Center (React) — dashboard/chamados/ML/jobs; ADMIN: técnicos, redirect, matrícula |

- O **worker** é quem atribui chamados Novo → técnico/fila.
- Perfil **CONSULTA**: painel só leitura.
- Perfil **ADMIN**: pode redirecionar técnico no **GLPI + SGC**, sync/editar matrícula; **não** dispara agendador nem re-treino pela API.
- Telegram: opcional (desligado sem token).

---

## 2. Stack

| Camada | Tecnologia |
|--------|------------|
| Worker | Python 3.10+, pandas, scikit-learn, pymysql, requests |
| Config | `conf/*.dat` + `chave.key` (Fernet) |
| API | FastAPI, Uvicorn, PyJWT, pywin32 (LogonUser AD) |
| Frontend | React 19, TypeScript, Vite 8, Tailwind 4, TanStack Query, Recharts |
| Dados | MariaDB (SGC) |
| Integrações | GLPI REST; Telegram **opcional** (desligado sem token) |

Deps: `requirements.txt` (worker) · `requirements-api.txt` (API) · `frontend/package.json`

---

## 3. Arquitetura

```
GLPI ──► Worker (run.bat) ──► MariaDB
                                  │
                             API (run_api*.bat)  ◄── AD (senha Windows)
                                  │
                             Frontend (:5173 / dist)
```

---

## 4. Regras de negócio

### 4.1 Atribuição (worker)

1. Busca chamados GLPI com status **Novo** (ciclo ~30s).  
   Janela/limite configuráveis: `SGC_GLPI_DIAS_ABERTOS` (default 30), `SGC_GLPI_FETCH_LIMIT` (default 300).
2. Se já existe em `Tb_Ticket_new` → ignora.  
   *Erro ao consultar DB → fail-closed (não reatribui).*
3. Define equipe, nesta ordem:
   1. **DIRETO** — palavra-chave exata em `arqaux.txt`
   2. **FALLBACK_PARCIAL** — match parcial
   3. **ML** — ComplementNB + TF-IDF (limiares)
   4. **FALLBACK_CATEGORIA**
   5. **FALLBACK_N1** — equipe padrão
4. Escolhe técnico elegível em `Tb_Atrib` (Sit=1, horário H1/H2 incluindo overnight, menor carga `QtdC`; `QtdC` zera 1×/dia).
5. Sem técnico elegível → **skip**: chamado permanece **Novo** no GLPI (não há “técnico default”). Retry no próximo ciclo; log ML/skip contado 1× por ID/dia.
6. Atribui no GLPI (Ticket_User + status) → **só então** INSERT local (`Dat_Reg`) + carga.  
   *Se INSERT falhar após GLPI ok → órfão + backfill em `Verifica_Usuarios`.*
7. Telegram: só se `TELEGRAM_TOKEN` definido; senão pula.

### 4.2 Aprendizado

- Agendador (padrão ligado): re-treino ~02:00, PDF assertividade ~03:00, relatório feedback (domingo).
- Modelo ativo: `Modelo/ModeloML.pkl`.

### 4.3 Acesso ao painel

| Pode entrar | Não pode |
|-------------|----------|
| Matrícula **59817** | Qualquer outra matrícula |
| N3 ativo (`Sit=1`) com **`Matricula` real** em `Tb_Atrib` | `00000` / vazio; outras equipes; login por `nome.sobrenome` |

- Login = **matrícula** + **senha Windows (AD)** (`SGC_AD_DOMAIN`).
- Senha AD correta **não** libera quem está fora da allowlist.
- Perfil emitido: **ADMIN**.
- Rate limit: 10 tentativas / IP / minuto.
- Logout **revoga** o JWT (`jti`) até expirar (default 120 min).

### 4.4 Isolamento

- CONSULTA: API/painel não escrevem em GLPI, Telegram, `arqaux.txt` nem modelo ML.
- ADMIN: pode redirect de técnico (GLPI + `Tb_Ticket_new`) e gestão de matrícula; **não** dispara jobs do agendador nem re-treino/rollback de modelo pelo painel.

---

## 5. Estrutura (essencial)

```
Proj_SGC(ROBO)/
├── run.bat / run.sh              # Worker
├── run_api.bat / run_api_dev.bat # API prod / dev
├── build_frontend.bat
├── arqaux.txt                    # Regras DIRETO/PARCIAL
├── conf/                         # Segredos (não versionar publicamente)
├── python/                       # Worker + ML + GLPI + DAL
├── backend/                      # FastAPI + auth AD
├── frontend/                     # Control Center
├── Modelo/                       # .pkl
├── sql/                          # Inclui criar_Tb_Auth_Painel.sql
├── log/  relatorios/  docs/
```

---

## 6. Operação

### 6.1 Subir

| # | O quê | Comando |
|---|--------|---------|
| 1 | Worker | `run.bat` |
| 2 | API (dev) | `run_api_dev.bat` (porta tipicamente 8001) |
| 3 | API (prod) | `set SGC_API_PORT=8001` → `run_api.bat` |
| 4 | Frontend | `cd frontend` → `npm run dev` **ou** `build_frontend.bat` |

Ordem: MariaDB → Worker (se produção de atribuição) → API → Frontend.

### 6.2 Login

1. http://127.0.0.1:5173  
2. Matrícula + senha Windows  
3. Painel: Dashboard, Chamados, Equipes, Técnicos, IA, Agendamentos, Configurações

### 6.3 Variáveis críticas

| Variável | Uso |
|----------|-----|
| `TELEGRAM_TOKEN` | Opcional (vazio = sem Telegram) |
| `SGC_JWT_SECRET` | Obrigatório na API (≥32 chars) |
| `SGC_AD_DOMAIN` | Domínio AD (ex.: `GRBF`) |
| `SGC_AUTH_ADMIN_MATRICULAS` | Default `59817` |
| `SGC_AUTH_ADMIN_EQUIPES` | Default `N3` |
| `SGC_API_PORT` / `SGC_CORS_ORIGINS` | Bind / CORS |
| `VITE_API_BASE_URL` | Frontend → API |

Segredos GLPI/DB: só `conf/` — ver `docs/seguranca-segredos.md`.

### 6.4 Matrículas N3

```bat
sgc_python.bat python\ListarMatriculasN3Pendentes.py --sql-out relatorios\update_matriculas_n3.sql
```

Detalhe: `docs/POP-SGC-002-matriculas-n3.md`.

---

## 7. API (resumo)

| Método | Rota | Auth |
|--------|------|------|
| GET | `/health` | Público |
| POST | `/api/v1/auth/login` | Público (AD+allowlist) |
| POST | `/api/v1/auth/logout` | JWT (revoga) |
| GET | `/api/v1/auth/me` | JWT |
| GET | `/api/v1/dashboard/summary` | JWT |
| GET | `/api/v1/tickets` · `/tickets/{id}` | JWT |
| GET | `/api/v1/teams` · `/technicians` | JWT |
| GET | `/api/v1/ml/overview` | JWT (GESTOR+) |
| GET | `/api/v1/jobs` | JWT (OPERADOR+) |

Docs OpenAPI: ligadas no `run_api_dev.bat`; off no `run_api.bat` (`SGC_API_DOCS=0`).

---

## 8. Incidentes rápidos

| Sintoma | Ação |
|---------|------|
| Sem permissão no login | Conferir matrícula / N3+`Matricula` em `Tb_Atrib` |
| Senha inválida | Senha Windows / `SGC_AD_DOMAIN` |
| Health database fail | MariaDB + `conf/sgc.dat` |
| Chamados não atribuem | Worker ligado? Logs `log/`? GLPI? |
| Painel sem dados | API no ar? `VITE_API_BASE_URL`? JWT? |
| Porta ocupada | `set SGC_API_PORT=8001` |

**Prioridade:** worker + GLPI + banco. Painel é consulta.

---

## 9. Checklist “saudável”

- [ ] Worker em execução sem erro fatal
- [ ] `GET /health` → `status` e `database` ok
- [ ] Login `59817` + senha AD ok
- [ ] Fora allowlist → 401
- [ ] Dashboard/chamados carregam
- [ ] N3 com matrícula preenchida consegue entrar (se aplicável)

---

## 10. Documentos relacionados

| Doc | Path |
|-----|------|
| README geral | `README.md` |
| Auth AD | `backend/README-AUTH.md` |
| API | `backend/README.md` |
| Frontend | `frontend/README.md` |
| Segredos | `docs/seguranca-segredos.md` |
| Matrículas N3 | `docs/POP-SGC-002-matriculas-n3.md` |

---

## 11. Aprovação

| Papel | Matrícula / Nome | Data | Rubrica |
|-------|------------------|------|---------|
| Owner ADMIN | 59817 | ____/____/________ | ____________ |
| N3 (ciência) | | ____/____/________ | ____________ |

---

*POP-SGC-010 v2.0 — enxuto e completo.*
