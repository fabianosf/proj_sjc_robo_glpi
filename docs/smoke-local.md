# Smoke local — SGC (ROBO) na estação

Uso previsto: **somente na sua máquina** (não servidor corporativo).  
Data do smoke: **2026-10-03**.

---

## Como ligar

Em três terminais, a partir da raiz do projeto:

1. **Worker** (atribuição GLPI): `run.bat`
2. **API**: `run_api_dev.bat` → http://127.0.0.1:8001  
3. **Painel**: `cd frontend` → `npm run dev` → http://localhost:5173  

Health público: `GET http://127.0.0.1:8001/health` (não é `/api/v1/health`).

---

## Resultado do smoke (automático)

| Checagem | Resultado |
|----------|-----------|
| Porta **8001** (API) | OK (escutando) |
| Porta **5173** (Vite) | OK (escutando) |
| `GET /health` | **200** — body com `status` (neste smoke: `degraded`, `database: error`) |
| Frontend `/` | **200** |
| `log/worker_heartbeat.json` | Existe; neste smoke estava **stale** (`updated_at` 2026-09-28, `worker_alive: false`) |
| Código `Dat_Reg` | Presente em `python/DbMigracao.py` (`_ensure_dat_reg_ticket_new`) — coluna criada ao subir o worker |

### Interpretação

- Painel + API sobem na máquina.
- **Worker não estava vivo** no momento do smoke (heartbeat antigo; `last_assigned_id` residual **42**). Ligar `run.bat` atualiza o heartbeat e aplica migração `Dat_Reg`.
- `database: error` no `/health` indica falha de conexão MariaDB neste instante — conferir `conf/sgc.dat` / rede VPN / serviço do banco antes de operar atribuição.

---

## Smoke manual de atribuição (você no GLPI)

O agente **não** cria chamado no GLPI. Quando quiser validar ponta a ponta:

1. Garantir worker + API + MariaDB OK (`/health` com `database` ok e heartbeat fresco).
2. Abrir (ou achar) 1 chamado **Novo** recente no GLPI.
3. Em até ~1 ciclo do worker (~30s): status → Atribuído; linha em `Tb_Ticket_new` (com `Dat_Reg` se a coluna existir); painel mostra o ID (link só se estiver no SGC).
4. Conferir `log/worker_heartbeat.json`: `glpi_ok`, `last_assigned_id`, `skips_today`, `last_orphan_id` (se houver).

---

## O que monitorar no dia a dia

| Sinal | Onde |
|-------|------|
| Worker vivo | `log/worker_heartbeat.json` → `updated_at` recente; painel “Robô” |
| GLPI ok | `glpi_ok` / `last_error` |
| Skip sem técnico | `skips_today`, `last_skip_id` — chamado permanece **Novo** |
| Órfão GLPI≠SGC | `last_orphan_id` — backfill no job `verifica_atribuicoes` |
| Fila | `novos_na_fila` + lista Novo no GLPI |

Env úteis (Onda 3): `SGC_GLPI_DIAS_ABERTOS` (default 30), `SGC_GLPI_FETCH_LIMIT` (default 300), `SGC_WORKER_ALIVE_SECONDS` (default 300).
