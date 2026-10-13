# SGC API (FastAPI) — painel de operação

API isolada do worker (`main.py` / AgendadorSGC). Reutiliza o `DAL` em `python/DAL.py` e a conexão via `conf/sgc.dat` (nunca expõe conteúdo de `conf/`, tokens ou senhas).

A maior parte das rotas é **leitura**. Escritas (ADMIN): cadastro de técnicos, redirecionamento (também no GLPI), matrículas e regras `arqaux.txt`. Simulate de IA é dry-run (não grava GLPI).

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Status da API e do banco |
| POST | `/api/v1/auth/login` | Login AD + allowlist → JWT (ADMIN ou CONSULTA) |
| POST | `/api/v1/auth/logout` | Revoga JWT (jti) + auditoria |
| GET | `/api/v1/auth/me` | Usuário autenticado |
| GET | `/api/v1/dashboard/summary` | Totais e agregados |
| GET | `/api/v1/tickets?page=1&page_size=20&search=` | Lista paginada |
| GET | `/api/v1/tickets/glpi` | Chamados ativos GLPI (notold) |
| GET | `/api/v1/tickets/{ticket_id}` | Detalhe + último `Tb_ML_Log` |
| GET | `/api/v1/teams` | Equipes (`Tb_Atrib`) |
| GET | `/api/v1/technicians` | Técnicos (sem `token`) |
| PATCH | `/api/v1/technicians/{usuario}` | ADMIN: equipe, sit, matrícula, horário, empresa |
| POST | `/api/v1/technicians/redirect` | ADMIN: redireciona no GLPI + base local |
| POST | `/api/v1/technicians/sync-matriculas` | ADMIN: Oracle/GLPI/AD/mapa |
| POST | `/api/v1/technicians/import-matriculas` | ADMIN: CSV usuario;matricula |
| GET | `/api/v1/rules` | Regras DIRETO (`arqaux.txt`) |
| PUT | `/api/v1/rules` | ADMIN: grava `arqaux.txt` |
| GET | `/api/v1/ml/overview` | Visão geral `Tb_ML_Log` |
| GET | `/api/v1/ml/corrections` | Feedback de correção |
| GET | `/api/v1/ml/accuracy-by-method` | Assertividade por método |
| GET | `/api/v1/ml/logs` | Log ML paginado |
| POST | `/api/v1/ml/simulate` | Dry-run do classificador (GESTOR+) |
| GET | `/api/v1/jobs` | Metadados dos jobs do agendador |
| GET | `/api/v1/reports/ops` | Relatório operacional (intervalo) |
| GET | `/api/v1/reports/ops.pdf` | PDF operacional (mesmo recorte + período anterior) |
| GET | `/api/v1/reports/weekly-teams` | Relatório semanal por equipe |

Auth usa POST. Escritas de cadastro exigem perfil **ADMIN**.

## Regras

- Paginação: `page >= 1`, `page_size` entre 1 e 100.
- CORS: apenas `http://localhost:5173` e `http://127.0.0.1:5173` (ou `SGC_CORS_ORIGINS`).
- Tabela/coluna ausente → `null` ou lista vazia + warning em `log/sgc_api.log`.

## Estrutura

```
backend/
  README.md
  app/
    main.py          # FastAPI app
    bootstrap.py     # sys.path → python/
    deps.py          # DAL(sgc.dat)
    db_meta.py       # SHOW TABLES / COLUMNS
    schemas.py       # Pydantic
    logging_config.py
    routers/
      health.py
      v1.py
    services/
      queries.py
```

Na raiz do projeto:

- `requirements-api.txt`
- `run_api.bat`

## Instalação (Windows)

Na raiz do projeto (com o venv do SGC já criado por `setup_env.bat`):

```bat
venv\Scripts\pip.exe install -r requirements-api.txt
```

## Execução

Desenvolvimento (reload + docs):

```bat
run_api_dev.bat
```

Produção (sem reload; docs off por default):

```bat
set SGC_API_PORT=8001
run_api.bat
```

Frontend build + preview:

```bat
build_frontend.bat
```

Opcional: `set SGC_SERVE_FRONTEND=1` para a API servir `frontend/dist`.

Se a porta 8000 estiver ocupada:

```bat
set SGC_API_PORT=8001
run_api.bat
```

Ou:

```bat
set PYTHONPATH=backend;python
venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

- API: http://127.0.0.1:8000 (ou `SGC_API_PORT`)  
- Swagger: http://127.0.0.1:8000/docs  

O worker continua sendo iniciado à parte com `run.bat`.

Smoke test (servidor já no ar):

```bat
venv\Scripts\python.exe backend\_smoke_test.py http://127.0.0.1:8001
```

## Exemplos de teste

```bat
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/dashboard/summary
curl "http://127.0.0.1:8000/api/v1/tickets?page=1&page_size=10&search=senha"
curl http://127.0.0.1:8000/api/v1/tickets/48403
curl http://127.0.0.1:8000/api/v1/teams
curl http://127.0.0.1:8000/api/v1/technicians
curl http://127.0.0.1:8000/api/v1/ml/overview
curl http://127.0.0.1:8000/api/v1/jobs
```

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/tickets?page=1&page_size=5"
```

## Segurança

- Bind padrão em `127.0.0.1` (não expõe a rede).
- Respostas não incluem `conf/`, `chave.key`, senhas, `TELEGRAM_TOKEN` nem coluna `token` de `Tb_Atrib`.
- Apenas métodos GET no CORS.
