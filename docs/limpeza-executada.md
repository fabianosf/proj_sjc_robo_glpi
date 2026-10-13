# Limpeza executada — Proj_SGC (ROBO)

**Data (onda A):** 2026-09-19  
**Data (onda B):** 2026-09-21  
**Data (onda C):** 2026-10-06  
**Aprovação A:** “aprovo .. pode executar a limpeza”  
**Aprovação B:** “pode executar” (lista Recomendado remover)  
**Aprovação C:** plano “Limpeza do aplicativo SGC” (implementar)  
**Escopo A:** SEGURO PARA REMOVER (A1–A7) + `.gitignore`  
**Escopo B:** itens B sem referência no runtime (abaixo)  
**Escopo C:** caches + docs de agente + `dist-windows` + dump SQL arquivado  
**Não tocado (C):** `conf/`, `Modelo/` ativo, worker, API, `frontend/dist`, launchers VBS

Referência: [`docs/auditoria-limpeza.md`](auditoria-limpeza.md)

---

## Removido do disco — Onda A (2026-09-19)

| # | Item | Resultado |
|---|------|-----------|
| A1 | `main.exe` | Removido (duplicata bit-a-bit de `main.py`) |
| A2 | `pip` (raiz, 0 bytes) | Removido |
| A3 | `frontend/src/assets/react.svg` | Removido |
| A4 | `frontend/src/assets/vite.svg` | Removido |
| A5 | `frontend/src/assets/hero.png` | Removido |
| A6 | `frontend/public/icons.svg` | Removido |
| A7 | `__pycache__/` (fora de `venv/` / `node_modules/`) | Removido; regenera no próximo `import` |

Também removida a pasta vazia `frontend/src/assets/` após limpar os assets do template Vite.  
`frontend/public/favicon.svg` **mantido**.

---

## Removido do disco — Onda B (2026-09-21)

| Item | Motivo |
|------|--------|
| `backup_requirements.txt` | Freeze antigo (torch/onnx); não é o requirements atual |
| `Gif.gif`, `icon.ico` | Sem referência no código |
| `ojdbc11.jar` (~7 MB) | Oracle via Instant Client em `drivers/` |
| `python/prazoExpiracao.py` | Módulo morto |
| Import `ClPrazoExpiracao` em `python/main.py` | Nunca usado |
| `yota-pop.md` | Persona de agente; fora do SGC |
| `docs/_removed_list.tmp.txt` | Artefato temporário |

---

## `.gitignore` atualizado (onda A)

Inclui: `venv/`, `frontend/node_modules/`, `__pycache__/`, `.env*`, `log/*.log`, `frontend/dist/`, `relatorios/*.pdf|*.txt`.

---

## Removido do disco — Onda C (2026-10-06)

| Item | Motivo |
|------|--------|
| `__pycache__/` (backend/python/tests) | Bytecode regenerável |
| `.pytest_cache/` | Cache de testes |
| `yota-spec.md`, `yota-chefe-arquitetura.md`, `auditor-software.md` | Docs de agente; fora do runtime |
| `log/*-07-2026.log` (9 arquivos) | Logs antigos |
| `dist-windows/` | Pacote Windows stale (~1 GB); regenerar com `build_windows_pkg.bat` se precisar |
| `dump-DB_SGC-202508211645.sql` | Arquivado fora do projeto e removido da pasta do app |

**Arquivo do dump:** `C:\Users\fabiano.freitas\Documents\SGC_backup_limpeza\dump-DB_SGC-202508211645.sql` (hash conferido antes do delete).

---

## Preservado (confirmado)

- Worker / agendador, `conf/`, `Modelo/` ativo, `sql/`, `drivers/`, `arqaux.txt`
- API + frontend (`frontend/dist`)
- Launchers: `Iniciar_SGC.vbs`, `Parar_SGC.vbs`, `start_*_hidden.*`
- Backups `conf/glpi*.dat*`, logs recentes, relatórios

---

## Validação pós-limpeza B

| Frente | Resultado |
|--------|-----------|
| Worker | Imports críticos OK; `python/main.py` sem `prazoExpiracao` → **ROBOT_OK** |

---

## Validação pós-limpeza C

| Frente | Resultado |
|--------|-----------|
| Keep-list | `main.py`, `python/main.py`, `frontend/dist`, VBS, `Modelo/ModeloML.pkl`, `conf` → OK |
| Worker import | **ROBOT_IMPORT_OK** |
| API `/health` | **ok** |
| Frontend `/` | **200** SPA |

---

## Próximo passo (opcional — Onda 3)

- Revisar retenção de `Modelo/X.pkl`, `ModeloML_v*.pkl` antigos  
- `drivers/oracle_linux/` se for só Windows  
- Deps `pillow` / `pyTelegramBotAPI` após smoke test
