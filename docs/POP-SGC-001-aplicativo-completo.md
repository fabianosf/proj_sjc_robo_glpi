# POP — Sistema SGC (ROBO) Completo

| Campo | Valor |
|-------|--------|
| **Documento** | POP-SGC-001 |
| **Título** | Procedimento Operacional Padrão — Aplicativo SGC completo |
| **Versão** | 1.1 |
| **Data** | 2026-10-03 |
| **Escopo** | Robô de atribuição, API FastAPI, Frontend Control Center, auth AD, ML, GLPI, MariaDB |
| **Público** | ADMIN (matrícula 59817), time N3, suporte técnico, DevOps |
| **Owner** | Administrador do painel (matrícula 59817) |

---

## 1. Objetivo

Padronizar instalação, operação, acesso, monitoramento, incidentes e manutenção do **Proj SGC (ROBO)** — sistema interno de atribuição automática de chamados GLPI com Control Center (consulta + ações ADMIN).

Este POP é o documento mestre. Em conflito com anotações informais, **vale este POP** (após revisão do owner).

Requisitos formais: [`requisitos.md`](requisitos.md).  
Retenção de artefatos: [`retencao.md`](retencao.md).

---

## 2. Escopo e fora de escopo

### 2.1 Em escopo

| Frente | Descrição |
|--------|-----------|
| **Worker (robô)** | Loop de monitoramento, classificação, atribuição GLPI, agendador ML |
| **API (`backend/`)** | FastAPI + autenticação AD; escritas restritas a ADMIN |
| **Frontend (`frontend/`)** | React Control Center (consulta; ADMIN: técnicos/redirect/matrícula) |
| **Dados** | MariaDB SGC, `conf/`, `Modelo/`, `log/`, `relatorios/` |
| **Acesso** | Allowlist: matrícula `59817` + time N3 ativo |

### 2.2 Fora de escopo

- Alterar regras de negócio do GLPI fora do SGC
- Expor `conf/`, `chave.key` ou senhas AD
- Criar/editar/excluir chamados pela UI — **não existe** (atribuição só pelo worker)
- Disparar agendador / re-treino / rollback de modelo pela API
- LDAP Linux / autenticação fora do Windows LogonUser

---

## 3. Glossário

| Termo | Significado |
|-------|-------------|
| **Worker / Robô** | Processo `main.py` / `run.bat` que atribui chamados |
| **Painel / Control Center** | UI React em `frontend/` |
| **API** | FastAPI em `backend/` |
| **Allowlist** | Quem pode logar: `59817` ou N3 com `Matricula` válida |
| **DIRETO / REGRA_DIRETA** | Classificação por palavra-chave em `arqaux.txt` |
| **ML** | Modelo ComplementNB + TF-IDF |
| **Tb_Atrib** | Técnicos × equipes (elegibilidade, carga, matrícula) |

---

## 4. Visão geral do sistema

```
                    ┌─────────────────┐
                    │  GLPI (API)     │
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │  WORKER (python/main.py)    │
              │  - varredura Novos          │
              │  - regras + ML              │
              │  - atribui técnico          │
              │  - AgendadorSGC (ML/PDF)    │
              └──────────────┬──────────────┘
                             │
                    ┌────────▼────────┐
                    │  MariaDB SGC    │
                    │  conf/sgc.dat   │
                    └────────┬────────┘
                             │ leitura (+ escritas ADMIN)
              ┌──────────────▼──────────────┐
              │  API FastAPI (backend/)     │
              │  JWT + AD LogonUser         │
              └──────────────┬──────────────┘
                             │ HTTP JSON
              ┌──────────────▼──────────────┐
              │  Frontend Vite/React        │
              │  :5173 → API :8001          │
              └─────────────────────────────┘
```

**Regra de ouro:** o painel **nunca** atribui chamados Novo (só o worker). CONSULTA é leitura. ADMIN pode redirect de técnico (GLPI+SGC) e matrícula; **não** altera modelo ML nem dispara o agendador.

---

## 5. Stack tecnológica

### 5.1 Worker

| Camada | Tecnologia |
|--------|------------|
| Runtime | Python 3.10+ |
| Dados | pandas, pymysql (MariaDB); oracledb opcional |
| ML | scikit-learn (ComplementNB + TF-IDF), numpy |
| HTTP | requests (GLPI) |
| Notificação | Internas no painel (`Tb_Notificacao`); Telegram **fora de escopo** |
| PDF | reportlab |
| Config | cryptography/Fernet (`conf/*.dat` + `chave.key`) |
| HTML | beautifulsoup4 |

Dependências: `requirements.txt` · Setup: `setup_env.bat` / `setup_env.sh`

### 5.2 API (backend)

| Camada | Tecnologia |
|--------|------------|
| Framework | FastAPI + Uvicorn |
| Validação | Pydantic v2 |
| Auth | PyJWT + Windows `LogonUser` (pywin32) |
| Env | python-dotenv (`backend/.env`) |
| Dados | Reutiliza `python/DAL.py` + `conf/sgc.dat` |

Dependências: `requirements-api.txt` · Start: `run_api.bat`

### 5.3 Frontend

| Camada | Tecnologia |
|--------|------------|
| UI | React 19 + TypeScript |
| Build | Vite 8 |
| Rotas | React Router 7 |
| Dados | TanStack Query |
| Estilo | Tailwind CSS v4 |
| Charts | Recharts |
| Ícones | Lucide |

Dependências: `frontend/package.json` · Dev: `npm run dev` · Prod: `npm run build`

### 5.4 Infraestrutura de apoio

| Item | Uso |
|------|-----|
| MariaDB | Base operacional SGC |
| GLPI | Origem/destino dos chamados |
| Active Directory (domínio ex.: `GRBF`) | Senha do login do painel |
| Windows (recomendado para API) | LogonUser AD |
| Linux opcional | Worker via `run.sh` / `proj_sgc.service` |

---

## 6. Estrutura do repositório

```
Proj_SGC(ROBO)/
├── main.py / run.bat / run.sh          # Entrada do worker
├── setup_env.bat / .sh                 # venv + requirements.txt
├── sgc_python.bat / .sh                # Scripts avulsos no venv
├── run_api.bat                         # API FastAPI
├── criar_admin_painel.bat              # Obsoleto p/ login (só registro local)
├── requirements.txt / requirements-api.txt
├── arqaux.txt                          # Regras DIRETO/PARCIAL por equipe
├── proj_sgc.service / deploy/          # Linux / cron exemplo
├── conf/                               # sgc.dat, glpi.dat, chave.key (SECRETO)
├── python/                             # Worker, ML, GLPI, agendador, DAL
├── backend/                            # API FastAPI + auth AD
├── frontend/                           # Control Center React
├── sql/                                # Scripts de tabelas (ML, auth, etc.)
├── Modelo/                             # ModeloML.pkl e versões
├── log/                                # Logs diários + sgc_api.log
├── relatorios/                         # PDFs gerados
├── drivers/                            # Oracle Instant Client (opcional)
└── docs/                               # Auditoria, limpeza, este POP
```

---

## 7. Responsabilidades (RACI simplificado)

| Atividade | 59817 (ADMIN) | Time N3 | Suporte Infra |
|-----------|---------------|---------|---------------|
| Operar painel (consulta) | A/R | R | I |
| Liberar matrícula N3 em `Tb_Atrib.Matricula` | A | C | I |
| Subir/parar worker e API | A/R | C | R |
| Credenciais `conf/`, AD | A | I | R |
| Alterar `arqaux.txt` / regras | A | C | I |
| Re-treino / rollback ML | A | C | I |
| Incidentes produção | A | R | R |

R = Responsible · A = Accountable · C = Consulted · I = Informed

---

## 8. Pré-requisitos de ambiente

### 8.1 Máquina do worker

1. Python 3.10+
2. Acesso de rede ao MariaDB e à API GLPI
3. Pasta `conf/` com `chave.key`, `sgc.dat`, `glpi.dat`
4. Telegram **não faz parte** do produto
5. Após clone: executar `setup_env.bat` (Windows) ou `./setup_env.sh` (Linux)

### 8.2 Máquina da API + painel (Windows)

1. Mesmo `venv` do SGC + `pip install -r requirements-api.txt` (inclui `pywin32`)
2. Máquina **domain-joined** ou com alcance ao DC
3. Arquivo `backend/.env` (nunca commitar valores reais):

```env
SGC_JWT_SECRET=<segredo >= 32 chars>
SGC_JWT_EXPIRE_MINUTES=480
SGC_JWT_ALGORITHM=HS256
SGC_AD_DOMAIN=GRBF
SGC_AUTH_ADMIN_MATRICULAS=59817
SGC_AUTH_ADMIN_EQUIPES=N3
```

4. Frontend: Node.js LTS + `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

5. SQL auth aplicado uma vez:

```text
sql/criar_Tb_Auth_Painel.sql
```

### 8.3 Dados obrigatórios para login N3

Em `Tb_Atrib`, para cada técnico N3 que deve acessar o painel:

| Campo | Valor esperado |
|-------|----------------|
| `Equipe` | `N3` |
| `Sit` | `1` (ativo) |
| `Matricula` | Matrícula real (não `00000`) |

Sem matrícula real → **não entra**, mesmo com senha AD correta.

---

## 9. POP — Instalação inicial (checklist)

### 9.1 Worker

1. Copiar projeto para o servidor.
2. Garantir `conf/` completo (não versionar publicamente).
3. Executar `setup_env.bat`.
4. Diagnóstico: `sgc_python.bat python\teste_conexao.py` (ou equivalente).
5. Aplicar SQLs necessários (`sql/` + migrações `DbMigracao` na subida).
6. Subir worker: `run.bat` — validar logs em `log/`.

### 9.2 API

1. `venv\Scripts\python.exe -m pip install -r requirements-api.txt`
2. Criar `backend/.env` a partir de `backend/.env.example`.
3. Gerar JWT: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
4. Definir `SGC_AD_DOMAIN` (ex.: `GRBF`).
5. Aplicar `sql/criar_Tb_Auth_Painel.sql`.
6. `set SGC_API_PORT=8001` → `run_api.bat`
7. Validar: `http://127.0.0.1:8001/health` → `{"status":"ok","database":"ok",...}`

### 9.3 Frontend

1. `cd frontend` → `npm install`
2. Configurar `VITE_API_BASE_URL` alinhado à porta da API
3. `npm run dev` → `http://127.0.0.1:5173`
4. Login com matrícula allowlist + senha Windows

**Ordem de subida:** MariaDB disponível → Worker (se produção de atribuição) → API → Frontend.

---

## 10. POP — Operação diária

### 10.1 Subir o sistema (Windows)

| # | Processo | Comando | URL / resultado |
|---|----------|---------|-----------------|
| 1 | Worker | `run.bat` | Loop contínuo; logs em `log/` |
| 2 | API | `set SGC_API_PORT=8001` + `run_api.bat` | http://127.0.0.1:8001/docs |
| 3 | Frontend | `cd frontend` + `npm run dev` | http://127.0.0.1:5173 |

Três terminais distintos. Encerrar com `Ctrl+C` ou matar o PID da porta.

### 10.2 Parar o sistema

1. Encerrar frontend (porta `5173`).
2. Encerrar API (porta `8001` / processo uvicorn).
3. Encerrar worker (`Ctrl+C` no `run.bat` ou stop do serviço).

### 10.3 Login no painel

1. Abrir http://127.0.0.1:5173
2. **Matrícula** (ex.: `59817`) — não usar `nome.sobrenome`
3. **Senha do Windows (AD)**
4. Sucesso → JWT em sessão local; perfil **ADMIN**
5. Falha comum:
   - Fora allowlist → "Sem permissão"
   - Senha errada → "Usuário ou senha inválidos"
   - AD/domínio → "Autenticação AD indisponível" (503)

### 10.4 Quem pode logar (regra absoluta)

| Pode | Não pode |
|------|----------|
| Matrícula `59817` | Qualquer outra matrícula |
| N3 ativo com `Matricula` preenchida | N1/N2/N4…, `admin` local antigo, login por `Usuario` tipo `juan.damasceno` |

Senha AD correta **não** libera quem está fora da allowlist.

---

## 11. Funcionamento do Worker (detalhe)

### 11.1 Ciclo de monitoramento

1. Consulta GLPI por chamados **Novo** (intervalo padrão 30s — `SGC_INTERVALO_VARREDURA`).  
   Limites: `SGC_GLPI_DIAS_ABERTOS` (default 30), `SGC_GLPI_FETCH_LIMIT` (default 300).
2. Se já existe em `Tb_Ticket_new` → ignora (DB erro → fail-closed, não reatribui).
3. `resolver_equipe_chamado()` na ordem:
   1. **DIRETO** — match exato `arqaux.txt`
   2. **FALLBACK_PARCIAL** — match parcial
   3. **ML** — modelo com limiares
   4. **FALLBACK_CATEGORIA**
   5. **FALLBACK_N1** — equipe padrão
4. Lista técnicos elegíveis (`Tb_Atrib`: H1/H2 com overnight, Sit=1, carga QtdC; QtdC zera 1×/dia).
5. Sem elegível → **skip** (fica Novo; sem técnico default). Retry no ciclo; ML/skip 1× por ID/dia.
6. Atribui no GLPI (Ticket_User + status; falha de vínculo ≠ sucesso).
7. Persiste ticket (`Dat_Reg`) + incrementa carga; órfão → backfill em Verifica_Usuarios.
8. Não notifica via Telegram (feature removida).
9. Registra decisão em `Tb_ML_Log` (exceto re-skip do mesmo ID no mesmo dia).

### 11.2 Agendador (background)

Com `SGC_AGENDADOR_AUTO=1` (padrão):

| Job | Horário padrão | Função |
|-----|----------------|--------|
| Re-treino ML | 02:00 | Sync feedback, correções, treina, implanta se F1 ok |
| PDF assertividade | 03:00 | Relatório diário |
| Relatório feedback | Dom 04:00 | Cobertura do treino |

Manual: `sgc_python.bat python\AgendadorSGC.py` ou scripts em `python/`.

### 11.3 Artefatos críticos do worker

| Path | Função | Cuidado |
|------|--------|--------|
| `arqaux.txt` | Regras por equipe | Prioridade sobre ML; backup antes de editar |
| `Modelo/ModeloML.pkl` | Modelo ativo | Rollback via scripts de versionamento |
| `conf/*` | Segredos | Nunca commit público |
| `log/` | Auditoria operacional | Rotação/limpeza sob política local |
| `relatorios/` | PDFs | Arquivar periodicamente |

---

## 12. Funcionamento da API

### 12.1 Princípios

- Leituras de negócio via **GET** (+ auth POST login/logout)
- CONSULTA não altera GLPI/ML/atribuição
- ADMIN pode redirect de técnico (GLPI+SGC) e sync/edição de matrícula; **não** dispara jobs do agendador
- Não devolve tokens de `Tb_Atrib`, conteúdo de `conf/` nem senhas
- CORS: apenas `http://localhost:5173` e `http://127.0.0.1:5173`

### 12.2 Endpoints

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/health` | Público | API + banco |
| POST | `/api/v1/auth/login` | Público | AD + allowlist → JWT |
| POST | `/api/v1/auth/logout` | JWT | Auditoria |
| GET | `/api/v1/auth/me` | JWT | Usuário atual |
| GET | `/api/v1/dashboard/summary` | JWT | Totais |
| GET | `/api/v1/tickets` | JWT | Lista paginada |
| GET | `/api/v1/tickets/{id}` | JWT | Detalhe + ML log |
| GET | `/api/v1/teams` | JWT | Equipes |
| GET | `/api/v1/technicians` | JWT | Técnicos (sem token) |
| PATCH/POST | `/api/v1/technicians…` | JWT ADMIN | Edição, redirect GLPI, sync matrícula |
| GET | `/api/v1/ml/overview` | JWT (GESTOR+) | Overview ML |
| GET | `/api/v1/jobs` | JWT (OPERADOR+) | Status (somente leitura — não dispara) |

Paginação: `page >= 1`, `page_size` 1–100.

### 12.3 Fluxo de autenticação

```
POST /login (matrícula + senha)
    │
    ├─ Allowlist? ──N──► 401 fora_allowlist (não chama AD)
    │
    ├─ LogonUser(domínio, matrícula, senha) ──N──► 401
    │
    ├─ Upsert Tb_Usuario_Painel (ADMIN, hash placeholder)
    ├─ Audit Tb_Auth_Audit
    └─ JWT (perfil ADMIN)
```

Documentação complementar: `backend/README-AUTH.md`.

---

## 13. Funcionamento do Frontend

### 13.1 Páginas

| Rota | Conteúdo |
|------|----------|
| `/login` | Matrícula + senha Windows |
| `/` | Dashboard |
| `/chamados` | Lista + busca |
| `/chamados/:ticketId` | Detalhe + log ML |
| `/equipes` | Equipes |
| `/tecnicos` | Técnicos |
| `/ia` | Inteligência artificial |
| `/agendamentos` | Jobs |
| `/configuracoes` | URL API + health |

### 13.2 Comportamento

- Token JWT no cliente; 401 → limpa sessão e redireciona `/login`
- Métodos de classificação: API grava `DIRETO`; UI exibe **REGRA_DIRETA**
- Lista de chamados: método pode aparecer “Não disponível” (detalhe/overview têm o dado)

### 13.3 Build produção

```bat
cd frontend
npm run build
npm run preview
```

Artefato: `frontend/dist/` (ignorado no git).

---

## 14. Banco de dados (tabelas principais)

| Tabela | Uso |
|--------|-----|
| `Tb_Ticket_new` | Chamados processados pelo robô |
| `Tb_Atrib` | Técnicos, equipes, Sit, Matricula, carga |
| `Tb_ML_Log` | Log de classificação |
| `Tb_Ticket_Feedback_Temp` | Feedback fechados (treino) |
| `Tb_Correcao_Feedback` | Divergências SGC vs GLPI |
| `tb_performance` | Métricas de assertividade |
| `Tb_Usuario_Painel` | Registro local do painel (sem senha AD) |
| `Tb_Auth_Audit` | Auditoria de login/logout |

Scripts: pasta `sql/`.

---

## 15. Variáveis de ambiente (referência)

### Worker

| Variável | Padrão | Função |
|----------|--------|--------|
| `SGC_AGENDADOR_AUTO` | `1` | Liga agendador no main |
| `SGC_INTERVALO_VARREDURA` | `30` | Segundos entre ciclos |
| `SGC_MONITOR_HEARTBEAT` | `60` | Heartbeat em log |
| `ML_RETRAIN_HOUR` | `2` | Hora re-treino |
| `ML_REPORT_HOUR` | `3` | Hora PDF |
| `ML_FEEDBACK_MESES` | `6` | Janela treino |
| `ML_FORCAR_IMPLANTACAO` | — | Força deploy do modelo |

### API

| Variável | Função |
|----------|--------|
| `SGC_JWT_SECRET` | Assinatura JWT (obrigatório) |
| `SGC_AD_DOMAIN` | Domínio Windows/AD (obrigatório) |
| `SGC_AUTH_ADMIN_MATRICULAS` | CSV allowlist (default `59817`) |
| `SGC_AUTH_ADMIN_EQUIPES` | CSV equipes (default `N3`) |
| `SGC_API_HOST` / `SGC_API_PORT` | Bind da API |

### Frontend

| Variável | Função |
|----------|--------|
| `VITE_API_BASE_URL` | Base da API (ex.: `http://127.0.0.1:8001`) |

---

## 16. POP — Manutenção recorrente

| Frequência | Ação | Responsável |
|------------|------|-------------|
| Diária | Verificar worker rodando + `/health` ok | N3 / ADMIN |
| Diária | Glance dashboard + chamados sem atribuição anômala | N3 |
| Semanal | Revisar `log/` e `Tb_Auth_Audit` (logins falhos) | ADMIN |
| Semanal | Conferir PDFs em `relatorios/` | ADMIN |
| Mensal | Validar `arqaux.txt` vs realidade das equipes | ADMIN + N3 |
| Mensal | Revisar matrículas N3 em `Tb_Atrib` | ADMIN |
| Sob demanda | Re-treino manual / rollback modelo | ADMIN |
| Sob demanda | Liberar chamado para reprocessar (`LiberarChamadosGLPI.py`) | ADMIN |

---

## 17. POP — Incidentes (triagem rápida)

| Sintoma | Verificar | Ação |
|---------|-----------|------|
| Painel não abre | Frontend `:5173` | Reiniciar `npm run dev` |
| Login 401 “sem permissão” | Allowlist / `Matricula` N3 | Corrigir `Tb_Atrib` ou matrícula digitada |
| Login 401 credencial | Senha AD / domínio | Validar Windows; checar `SGC_AD_DOMAIN` |
| Login 503 AD | pywin32 / DC / `.env` | Instalar deps; rede ao DC |
| Health database fail | MariaDB / `sgc.dat` | Rede, serviço DB, `conf/` |
| Chamados não atribuem | Worker parado / GLPI / `arqaux` / técnicos Sit | Subir `run.bat`; logs; `Tb_Atrib` |
| ML ruim | Assertividade / modelo | Relatório; rollback `Modelo/` |
| Porta 8000/8001 ocupada | Outro processo | `SGC_API_PORT=8001` (ou outra) |

### 17.1 Rollback de modelo ML

1. Parar necessidade de implantação forçada.
2. Usar `RestaurarModeloML.py` / versionamento em `Modelo/`.
3. Confirmar worker recarregou o `.pkl`.
4. Registrar incidente e horário.

### 17.2 Contingência se o painel cair

O **worker continua atribuindo** independentemente do painel. Prioridade: restaurar worker + GLPI + banco. Painel é consulta.

---

## 18. Segurança e compliance

1. Não versionar `backend/.env`, `chave.key`, `*.dat`, dumps com PII.
2. Não logar senhas AD.
3. JWT só em HTTPS em ambientes expostos (hoje bind local `127.0.0.1` é o padrão seguro em estação).
4. Painel: CONSULTA é leitura; escritas ADMIN só nas rotas previstas — não “contornar” com scripts ad hoc sem aprovação.
5. Allowlist é a fronteira de acesso: mudanças em `SGC_AUTH_*` só com aprovação do ADMIN 59817.
6. `criar_admin_painel.bat` **não** libera acesso; auth real = AD + allowlist.

---

## 19. Scripts utilitários (worker)

```bat
sgc_python.bat python\VerificarFase2Local.py
sgc_python.bat python\SincronizarFeedbackGLPI.py
sgc_python.bat python\ExecutarRetreinoDiario.py
sgc_python.bat python\GerarRelatorioAssertividade.py
sgc_python.bat python\AgendadorSGC.py retreino
sgc_python.bat python\LiberarChamadosGLPI.py
sgc_python.bat python\teste_conexao.py
sgc_python.bat python\listar_chamados.py
```

Linux: `./sgc_python.sh` no lugar do `.bat`.

---

## 20. Critérios de aceite (sistema “saudável”)

- [ ] `run.bat` em execução sem erro fatal em `log/`
- [ ] `GET /health` → status ok e database ok
- [ ] Login `59817` + senha AD → painel abre
- [ ] Matrícula fora allowlist → 401
- [ ] N3 com matrícula real + Sit=1 → login ok
- [ ] Dashboard/chamados carregam dados
- [ ] Worker atribui Novo do GLPI em ciclo normal
- [ ] Agendador sem falha silenciosa recorrente (checar jobs/logs)

---

## 21. Documentos relacionados

| Documento | Path |
|-----------|------|
| README geral | `README.md` |
| API | `backend/README.md` |
| Auth AD | `backend/README-AUTH.md` |
| Frontend | `frontend/README.md` |
| Auditoria limpeza | `docs/auditoria-limpeza.md` |
| Limpeza executada | `docs/limpeza-executada.md` |
| SQL auth | `sql/criar_Tb_Auth_Painel.sql` |

---

## 22. Controle de mudanças deste POP

| Versão | Data | Autor | Mudança |
|--------|------|-------|---------|
| 1.0 | 2026-09-19 | Dev POP Especialista / SGC | Emissão inicial — app completo (worker + API + FE + AD) |

**Próxima revisão sugerida:** após preenchimento das matrículas N3 em `Tb_Atrib` ou mudança de domínio/portas de produção.

---

## 23. Aprovação

| Papel | Nome / Matrícula | Data | Assinatura |
|-------|------------------|------|------------|
| Owner / ADMIN | 59817 | ____/____/________ | ____________ |
| Representante N3 | | ____/____/________ | ____________ |

---

*Fim do POP-SGC-001 — Aplicativo SGC completo.*
