# POP — Preenchimento de Matricula N3 (acesso ao painel)

| Campo | Valor |
|-------|--------|
| **Documento** | POP-SGC-002 |
| **Versão** | 1.0 |
| **Data** | 2026-09-19 |

## Objetivo

Garantir que técnicos **N3 ativos** tenham `Tb_Atrib.Matricula` com a matrícula real usada no Active Directory, para login no Control Center.

## Pré-requisito

- Acesso ao MariaDB SGC
- Matrículas oficiais do RH / AD

## Procedimento

1. Listar pendentes:

```bat
sgc_python.bat python\ListarMatriculasN3Pendentes.py --sql-out relatorios\update_matriculas_n3.sql
```

2. Abrir o SQL gerado e substituir `MATRICULA_REAL` em cada linha.

3. Executar os `UPDATE` no MariaDB (homologação primeiro, se houver).

4. Validar:

```bat
sgc_python.bat python\ListarMatriculasN3Pendentes.py
```

Exit code `0` = nenhum pendente; `2` = ainda há `00000`/vazio.

5. Testar login no painel com uma matrícula N3 + senha Windows.

## Regras

- Não usar `00000`, `0` ou vazio.
- Matrícula do login = identidade AD (`LogonUser`).
- Matrícula `59817` já entra pela allowlist fixa (não depende de `Tb_Atrib`).
