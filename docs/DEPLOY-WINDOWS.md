# Deploy Windows — SGC (outro PC / pacote .bat)

Guia para rodar o SGC numa **segunda máquina Windows** (ou reimplantar).  
O pacote é gerado por `build_windows_pkg.bat`.

## 0. Antes de copiar

No PC de origem (este projeto):

```bat
build_windows_pkg.bat
```

Saída: `dist-windows\SGC\` (sem `venv`, sem `node_modules`, **sem** `conf` secreta).

Copie a pasta `dist-windows\SGC` para o outro PC (USB, rede, etc.).

**Importante:** rode o **worker (`run.bat`) em só uma máquina**. Dois workers atribuindo ao mesmo tempo podem duplicar/conflitar no GLPI. No segundo PC costuma bastar a **API + painel** se o robô já roda no primeiro.

---

## 1. Pré-requisitos no PC de destino

| Item | Motivo |
|------|--------|
| Windows na mesma rede / domínio AD | Login do painel (LogonUser) |
| Python 3.10+ no PATH | Worker + API |
| Acesso a MariaDB SGC | `conf\sgc.dat` |
| Acesso à API GLPI | `conf\glpi.dat` |
| Mesma `chave.key` do ambiente | Descriptografa `*.dat` |

Node.js **não** é obrigatório no destino se o pacote já trouxer `frontend\dist`.

---

## 2. Primeira vez no destino

1. Abra Prompt na pasta `SGC\`.
2. Rode:

```bat
setup_producao.bat
```

3. Copie **manualmente** para `conf\` (do PC seguro / backup):
   - `chave.key`
   - `sgc.dat`
   - `glpi.dat`

4. Configure o painel:

```bat
copy backend\.env.example backend\.env
```

Edite `backend\.env` (mínimo):

```env
SGC_JWT_SECRET=<segredo longo, único neste ambiente>
SGC_AD_DOMAIN=<seu domínio, ex. GRBF>
SGC_AUTH_ADMIN_MATRICULAS=59817
SGC_AUTH_ADMIN_AD_USERS=fabiano.freitas
SGC_AUTH_ADMIN_EQUIPES=N3
SGC_JWT_EXPIRE_MINUTES=120
```

ADMIN de escrita = matrículas em `SGC_AUTH_ADMIN_MATRICULAS` **ou** logins em `SGC_AUTH_ADMIN_AD_USERS`. N3 loga como CONSULTA.

---

## 3. Subir

**Sem prompt (recomendado neste PC):**

1. `cd frontend` → `npm run build` (se ainda não houver `frontend\dist`)
2. `install_autostart_windows.bat` — cria tarefas no logon e sobe worker + API
3. Abra http://127.0.0.1:8001  

Remover: `uninstall_autostart_windows.bat`. Detalhes: `docs\operar-redirecionamento.md`.

**Só painel (robô já em outro PC):**

```bat
set SGC_API_PORT=8001
set SGC_API_DOCS=0
set SGC_SERVE_FRONTEND=1
run_api.bat
```

**Robô + painel neste PC (com prompt):**

```bat
REM Terminal 1
run.bat

REM Terminal 2
set SGC_API_PORT=8001
set SGC_API_DOCS=0
set SGC_SERVE_FRONTEND=1
run_api.bat
```

- Health: http://127.0.0.1:8001/health  
- Painel: http://127.0.0.1:8001/  

Login: **matrícula** (ou login AD mapeado) + senha Windows.

---

## 4. Checklist

- [ ] `GET /health` → `database` ok (MariaDB alcançável)  
- [ ] Login ADMIN ok  
- [ ] Se worker neste PC: heartbeat em `log\worker_heartbeat.json` atualiza  
- [ ] Se só painel: worker do outro PC continua atribuindo  

---

## 5. Observações

- Telegram removido do produto (atribuição sem notificação externa).
- Não versionar `conf\`, `backend\.env`, dumps SQL.
- Atualização: novo `build_windows_pkg.bat` → substitua código; **preserve** `conf\`, `backend\.env` e, se quiser, `venv\` (ou rode `setup_producao.bat` de novo).
- Acesso pela LAN (outro notebook abrindo o painel): use IP do host, `SGC_API_HOST=0.0.0.0` e `SGC_CORS_ORIGINS` conforme `run_mobile.bat` / docs mobile.