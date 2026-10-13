# Auditoria de limpeza — Proj_SGC (ROBO)

**Data:** 2026-09-19  
**Escopo:** repositório completo após criação de `backend/` e `frontend/`  
**Modo:** somente scanner e classificação — **nenhum arquivo foi apagado ou movido**  
**Aguarda:** aprovação explícita do responsável antes de qualquer remoção

---

## Resumo executivo

O repositório contém três frentes ativas:

| Frente | Entrada | Status |
|--------|---------|--------|
| Robô legado | `main.py` / `run.bat` / `run.sh` / `proj_sgc.service` | Em produção |
| API FastAPI | `backend/` + `run_api.bat` | Ativa |
| Frontend React | `frontend/` | Ativa |

Há poucos itens **comprovadamente** seguros para remover (duplicata bit-a-bit, arquivo vazio, assets Vite não referenciados). A maior parte do “lixo aparente” é **dado operacional, backup de config ou artefato de ML** e deve ser **preservada ou arquivada com revisão humana**.

---

## Metodologia do scanner

1. Inventário da raiz e pastas (`backend`, `frontend`, `python`, `sql`, `conf`, `Modelo`, `log`, `relatorios`, `drivers`, `deploy`, `venv`).
2. Mapeamento de scripts `.bat` / `.sh`, `proj_sgc.service`, `deploy/crontab.sgc.example`.
3. Imports estáticos em `python/*.py` e `backend/app/**/*.py`.
4. Imports TypeScript em `frontend/src/**`.
5. Comparação `requirements.txt` / `requirements-api.txt` / `package.json` vs uso no código.
6. Busca de referências a candidatos a remoção (`main.exe`, `Gif.gif`, `ojdbc11.jar`, `backup_requirements.txt`, assets, etc.).
7. Hash SHA-256: `main.py` ≡ `main.exe` (**idênticos**).

**Não analisado como candidato a delete:** conteúdo de `venv/` e `frontend/node_modules/` (ambientes gerados; política = ignorar no git, não versionar).

---

## Mapa de entradas e runtime (PRESERVAR)

### Robô / agendador

| Item | Evidência |
|------|-----------|
| `main.py` (raiz) | Bootstrap → `python/main.py` |
| `python/main.py` | Loop + `AgendadorSGC` |
| `run.bat` / `run.sh` | Start Windows/Linux |
| `setup_env.bat` / `setup_env.sh` | venv + deps |
| `sgc_python.bat` / `sgc_python.sh` | Scripts avulsos |
| `proj_sgc.service` | systemd |
| `deploy/crontab.sgc.example` | Cron alternativo |
| `arqaux.txt` | Regras DIRETO/PARCIAL |
| `python/*` (worker, ML, trade, GLPI, telegram, TarefasML, …) | Cadeia de imports do `main` e CLI |
| `conf/` + `chave.key` + `*.dat` | CONFIGURACAO / DAL / GLPI |
| `Modelo/` | `ML.MODELO_ATIVO`, versionamento |
| `sql/` | `DbMigracao` + auth painel |
| `drivers/oracle_*` | DAL Oracle opcional |
| `requirements.txt` | Deps do robô |

### API / frontend

| Item | Evidência |
|------|-----------|
| `backend/app/**` | Rotas FastAPI, auth, queries |
| `backend/scripts/criar_admin.py` | CLI ADMIN |
| `run_api.bat` / `criar_admin_painel.bat` | Ops Windows |
| `requirements-api.txt` | FastAPI + JWT + bcrypt |
| `frontend/src/**` | App React |
| `frontend/package.json` + `package-lock.json` | Build |
| `frontend/public/favicon.svg` | Referenciado em `index.html` |

### Variáveis de ambiente relevantes

| Variável | Uso |
|----------|-----|
| `SGC_JWT_SECRET` / `SGC_JWT_*` | Auth API (`backend/.env`) |
| `VITE_API_BASE_URL` | Frontend |
| `SGC_AGENDADOR_AUTO`, `SGC_INTERVALO_VARREDURA`, `ML_*`, `TELEGRAM_TOKEN` | Worker |
| `SGC_API_PORT` / `SGC_API_HOST` | `run_api.bat` |

Docker: **não encontrado**.

---

## Classificação dos itens

Legenda:

- **SEGURO PARA REMOVER** — evidência forte de não uso / duplicata; remoção não afeta runtime
- **PRECISA DE REVISÃO HUMANA** — possível lixo, mas risco de uso externo/manual/histórico
- **PRESERVAR** — necessário ou proibido remover por regra

---

### A) SEGURO PARA REMOVER

| # | Item | Evidência | Impacto se remover |
|---|------|-----------|-------------------|
| A1 | `main.exe` | SHA-256 **idêntico** a `main.py`; conteúdo é script Python (`#!/usr/bin/env python3`), não PE nativo; `run.bat` chama `main.py` | Nenhum no fluxo oficial. Apenas quem digita `python main.exe` por hábito (mesmo conteúdo) |
| A2 | `pip` (raiz, 0 bytes) | Arquivo vazio; nenhuma referência em scripts/código | Nenhum |
| A3 | `frontend/src/assets/react.svg` | Nenhum import em `frontend/src` | Nenhum (template Vite) |
| A4 | `frontend/src/assets/vite.svg` | Idem | Nenhum |
| A5 | `frontend/src/assets/hero.png` | Idem | Nenhum |
| A6 | `frontend/public/icons.svg` | Só `favicon.svg` é referenciado em `index.html` | Nenhum |
| A7 | `__pycache__/` (raiz e `python/`) | Bytecode gerado; já coberto por `.gitignore` (`__pycache__/`, `*.py[cod]`) | Regenera no próximo run |

> **Nota:** após aprovação, estes itens podem ser removidos do disco. Não altera regras, GLPI, ML nem API.

---

### B) PRECISA DE REVISÃO HUMANA

| # | Item | Evidência | Risco se remover |
|---|------|-----------|------------------|
| B1 | `backup_requirements.txt` | Freeze antigo com `torch`, `onnx`, `hummingbird-ml`, `mysql-connector` — **não** é o `requirements.txt` atual; nenhuma referência em scripts | Baixo para runtime atual; pode ser histórico de experimento ML |
| B2 | `Gif.gif`, `icon.ico` | Sem referência no código Python/TS/scripts | Pode ser branding de instalador/atalho externo |
| B3 | `ojdbc11.jar` (raiz, ~7 MB) | Sem `.jar` sob `drivers/`; Oracle usa Instant Client em `drivers/oracle_*` via `oracledb` | Se alguém apontar classpath/JDBC legado manualmente, quebra |
| B4 | `dump-DB_SGC-202508211645.sql` (~1,8 MB) | Dump completo; pode conter dados sensíveis/PII; não usado pelo runtime | Perda de backup local; **não** apagar sem arquivar fora do repo |
| B5 | `python/prazoExpiracao.py` + import em `python/main.py` | Importado em `main.py` mas **nunca instanciado/usado**; módulo parece legado de thread de prazos | Remover import é mudança no worker (baixa, mas sensível); módulo pode ser reativado no futuro |
| B6 | `python/listar_chamados.py`, `python/teste_conexao.py` | Utilitários de diagnóstico; citados no README | Úteis para suporte; não são mortos |
| B7 | `backend/_smoke_test.py` | Teste manual documentado em `backend/README.md` | Útil para QA da API |
| B8 | `conf/*.bak*`, `glpi7.dat`, `glpiH.dat`, `glpi_homolo.dat`, `glpi.dat.prod_mariadb` | Backups/variantes de config criptografada | **Nunca apagar sem inventário**; risco operacional alto |
| B9 | Versões antigas em `Modelo/ModeloML_v*.pkl`, `ModeloML_test_backup.pkl` | Versionamento/`ClModelVersionamento`; ativo é `ModeloML.pkl` | Rollback de modelo pode depender delas |
| B10 | `log/*.log`, `relatorios/*` | Saídas de runtime do worker/API/agendador | Dados operacionais — política de retenção, não delete automático |
| B11 | `pyTelegramBotAPI` | **Removido na Onda D (2026-10-13)** com `telegram.py` |
| B12 | `pillow` | **Removido na Onda D (2026-10-13)** — sem `PIL` no app; PDF via ReportLab |
| B13 | `httpx` instalado no `venv` (não está em `requirements-api.txt`) | Usado só para `TestClient` ad hoc | Não versionado; limpar venv é opcional (`pip uninstall httpx`) |
| B14 | `frontend/dist/` | Build gerado; já em `frontend/.gitignore` | Regenerável com `npm run build` |

---

### C) PRESERVAR (obrigatório / crítico)

| Item | Motivo |
|------|--------|
| `conf/`, `chave.key`, `*.dat`, `.env`, `.env.example` | Segredos / templates — regra explícita |
| `Modelo/` (pelo menos `ModeloML.pkl` + backups recentes usados) | Inferência ML |
| `sql/` | Migrations worker + auth |
| `arqaux.txt` | Classificação DIRETO/PARCIAL |
| `run.bat`, `run.sh`, `setup_env.*`, `sgc_python.*`, `run_api.bat`, `criar_admin_painel.bat` | Entradas oficiais |
| `python/` módulos do worker/agendador/ML/GLPI/Telegram | Runtime |
| `backend/app/**`, `frontend/src/**` (exceto assets listados em A) | Painel |
| `requirements.txt`, `requirements-api.txt`, `package.json`, `package-lock.json` | Deps |
| `proj_sgc.service`, `deploy/crontab.sgc.example` | Deploy Linux |
| `drivers/` | Oracle opcional |
| `README.md`, docs de auth/API/frontend | Documentação |
| `venv/`, `node_modules/` | Ambientes locais (não versionar; não “limpar” como produto) |

---

## Duplicados

| Par | Conclusão |
|-----|-----------|
| `main.py` ↔ `main.exe` | **Duplicata bit-a-bit** → A1 SEGURO remover `main.exe` |
| `requirements.txt` ↔ `backup_requirements.txt` | Não são equivalentes; backup é snapshot obsoleto → B1 |
| `ojdbc11.jar` (raiz) vs Instant Client em `drivers/` | Sobreposição funcional possível (JDBC vs thick Oracle) → B3 |
| Vários `conf/glpi*.dat*` | Variantes/ambiente → PRESERVAR / B8 |
| Vários `ModeloML_v*.pkl` | Histórico de versão → B9 |

---

## Código morto provável

| Item | Evidência | Classe |
|------|-----------|--------|
| Import `ClPrazoExpiracao` em `python/main.py` | Só o `import`; zero usos | B5 (revisão; após OK, remover import + avaliar arquivo) |
| Corpo de `prazoExpiracao.py` | Não referenciado por outros módulos | B5 |
| Assets Vite padrão no frontend | Sem imports | A3–A6 |

**Não classificar como morto sem revisão:** CLIs `SincronizarFeedbackGLPI`, `LiberarChamadosGLPI`, `TreinarModeloNovo`, etc. — usados via `sgc_python` / cron / agendador.

---

## Dependências possivelmente não usadas

| Pacote | Onde | Evidência | Classe |
|--------|------|-----------|--------|
| `pyTelegramBotAPI` | `requirements.txt` | Código usa `requests` em `telegram.py` | B11 |
| `pillow` | `requirements.txt` | Sem import PIL no repo | B12 |
| `httpx` | venv apenas | Testes manuais FastAPI | B13 |
| `oracledb` | `requirements.txt` | Usado sob demanda se `sgbd=oracle` | **PRESERVAR** |
| Deps ML (`scikit-learn`, `scipy`, `joblib`, …) | `requirements.txt` | `ML.py` / avaliação | **PRESERVAR** |
| FastAPI stack + `bcrypt` + `PyJWT` | `requirements-api.txt` | Auth/API | **PRESERVAR** |
| Frontend deps listadas em `package.json` | Todas usadas (Router, Query, Lucide, Recharts, Tailwind) | **PRESERVAR** |

Nenhuma remoção de dependência nesta fase sem aprovação item a item (B11/B12).

---

## Gerados → reforçar `.gitignore`

Já ignorados (parcial): `venv/`, `__pycache__/`, `*.log`, `log/*.log`, `backend/.env`, `.env`, `frontend/node_modules`, `frontend/dist`, `frontend/.env*`.

**Proposta de reforço (após aprovação):**

```gitignore
# Ambientes
venv/
frontend/node_modules/

# Bytecode / cache
__pycache__/
*.py[cod]
.Python
frontend/dist/
frontend/dist-ssr/

# Segredos locais
.env
backend/.env
frontend/.env
frontend/.env.local

# Runtime gerado (manter pastas, ignorar conteúdo)
log/*.log
relatorios/*.pdf
relatorios/*.txt
# opcional: Modelo/*.pkl  — NÃO recomendar ignorar se o deploy leva o modelo no repo

# SO / IDE
.DS_Store
Thumbs.db
.vscode/
.idea/
```

**Não ignorar:** `sql/`, `*.example`, `README*`, `docs/`, `arqaux.txt`, migrations, `package-lock.json`, `requirements*.txt`.

---

## Política de retenção (não apagar automaticamente)

| Área | Sugestão |
|------|----------|
| `log/` | Manter 30–90 dias; arquivar zip mensal fora do servidor quente |
| `relatorios/` | Manter 90–180 dias ou conforme compliance |
| `Modelo/ModeloML_v*.pkl` | Manter últimas N versões (ex.: 5) + `ModeloML.pkl` + `ModeloML_backup.pkl`; arquivar o resto |
| `dump-DB_*.sql` | Arquivar em storage seguro (fora do git); não versionar dumps com PII |
| `conf/*.bak*` | Inventariar; manter 1 backup recente por ambiente em cofre |

---

## Itens para arquivar (não remover do negócio)

| Item | Destino sugerido |
|------|------------------|
| `dump-DB_SGC-202508211645.sql` | Backup externo criptografado |
| `backup_requirements.txt` | `archive/` ou wiki de experimentos ML |
| `ModeloML_v*` antigos | `archive/modelos/` após validar rollback |
| `conf/*.bak*` | Cofre de config (não git público) |

---

## Plano pós-aprovação (não executado)

Somente após sua confirmação explícita dos itens **A*** (e opcionalmente subset de **B**):

1. Remover A1–A7 do disco.
2. Atualizar `.gitignore` raiz (e alinhar frontend se necessário).
3. **Não** alterar `requirements.txt` / `package.json` até você aprovar B11/B12.
4. Validar: `run.bat` (ou import `python/main.py`), `run_api.bat` + `/health`, `frontend` `npm run build` / lint.
5. Gerar `docs/limpeza-executada.md`.

---

## Checklist de aprovação

Marque o que autoriza remover/alterar:

- [ ] **A1** `main.exe`
- [ ] **A2** `pip` (vazio)
- [ ] **A3–A5** assets em `frontend/src/assets/`
- [ ] **A6** `frontend/public/icons.svg`
- [ ] **A7** limpar `__pycache__` no disco
- [ ] **B1** `backup_requirements.txt` (opcional)
- [ ] **B2** `Gif.gif` / `icon.ico` (opcional)
- [ ] **B3** `ojdbc11.jar` (opcional — alto cuidado)
- [ ] **B5** remover import morto + `prazoExpiracao.py` (opcional — toca worker)
- [ ] **B11/B12** limpar deps `requirements.txt` (opcional)
- [ ] Atualizar `.gitignore` conforme proposta

**Resposta esperada para avançar:**  
ex.: *“Aprovo remoção de todos os itens A e atualização do .gitignore. Não mexer em B.”*

---

*Fim do relatório de auditoria. Aguardando aprovação explícita.*
