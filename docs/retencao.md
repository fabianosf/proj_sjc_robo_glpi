# Política de retenção — artefatos locais SGC

| Campo | Valor |
|-------|--------|
| **Documento** | RET-SGC-001 |
| **Versão** | 1.0 |
| **Data** | 2026-10-13 |

## Modelo/ (ML)

| Item | Política |
|------|----------|
| Ativo | Manter `ModeloML.pkl` + `ModeloML_backup.pkl` + `metrics.json` |
| Versionados `ModeloML_v*.pkl` | O versionamento interno usa até **20** entradas (`MAX_VERSOES` em `python/ModelVersionamento.py`). Em disco, preferir manter as **últimas 5–20** versões; arquivar/remover as mais antigas após validar rollback. |
| `X.pkl` / `*_test_backup.pkl` | Não são necessários em runtime; podem ser arquivados fora do projeto. |

## log/

| Item | Política |
|------|----------|
| `log/YYYY-MM-DD.log` | Retenção sugerida: **90 dias** em disco; mais antigos compactar ou apagar. |
| `log/worker_heartbeat.json`, `agendador_state.json` | Operacionais — manter (sobrescritos). |
| `log/*_stdout.log` / `*_stderr.log` | Rotacionar ou limpar quando > **30 dias** ou > 50 MB. |

## relatorios/

| Item | Política |
|------|----------|
| PDF/TXT de assertividade e feedback | Retenção sugerida: **12 meses** no servidor de operação; cópias históricas fora do repo. |
| Geração | Produzidos pelo AgendadorSGC / tarefas ML — não versionar no Git (já em `.gitignore`). |

## Script ops (janela de manutenção)

```bat
venv\Scripts\python.exe python\aplicar_retencao.py
venv\Scripts\python.exe python\aplicar_retencao.py --apply
```

- Sem `--apply`: só lista o que seria removido (dry-run).
- Com `--apply`: remove logs >90d, stdout/stderr antigos/grandes, relatórios >12 meses, `ModeloML_v*` além das 20 mais recentes, e artefatos `X.pkl` / `ModeloML_test_backup.pkl`.
- **Não** remove `ModeloML.pkl`, `ModeloML_backup.pkl`, `metrics.json`, `conf/` nem o Worker.

O Worker de atribuição **não** chama este script automaticamente.
