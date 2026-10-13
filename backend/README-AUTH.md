# Autenticação do painel SGC

## Modelo atual

Login = **matrícula** (opcional) ou **usuário Windows** + senha AD.

Regra: técnico **ativo** (`Tb_Atrib.Sit=1`) entra com senha AD.

- **ADMIN:** matrícula em `SGC_AUTH_ADMIN_MATRICULAS`, login em `SGC_AUTH_ADMIN_AD_USERS`, ou N3 ativo com matrícula real (`SGC_AUTH_ADMIN_EQUIPES`).
- **CONSULTA:** demais técnicos Sit=1 (veem o painel; não editam técnicos/regras/redirect).

Matrículas: o AD GRBF **não** possui `employeeID`. Preencha em Técnicos → Editar, ou no mapa:

```env
SGC_AUTH_AD_USER_MAP=59817:fabiano.freitas,27237:juan.damasceno
```

Botão **Aplicar matrículas do mapa** grava esses valores em `Tb_Atrib.Matricula`.


Senhas **não** são gravadas no MariaDB. `Tb_Usuario_Painel` só guarda o registro local (id/JWT/auditoria) com placeholder.

## Pré-requisitos

1. API rodando no **Windows** com `pywin32` (`requirements-api.txt`).
2. Máquina alcança o Domain Controller (idealmente domain-joined).
3. `backend/.env` com `SGC_JWT_SECRET` e **`SGC_AD_DOMAIN`** (NetBIOS ou FQDN do domínio).
4. Tabelas `sql/criar_Tb_Auth_Painel.sql` aplicadas.

## Variáveis (`backend/.env`)

```env
SGC_JWT_SECRET=          # obrigatório, >= 32 chars
SGC_JWT_EXPIRE_MINUTES=120
SGC_JWT_ALGORITHM=HS256
SGC_AD_DOMAIN=           # obrigatório — ex.: EMPRESA
SGC_AUTH_ADMIN_MATRICULAS=59817,27237
SGC_AUTH_ADMIN_EQUIPES=N3
SGC_AUTH_AD_USER_MAP=59817:fabiano.freitas,27237:juan.damasceno
SGC_AUTH_ADMIN_AD_USERS=fabiano.freitas,juan.damasceno,andrew.silva
# SGC_CORS_ORIGINS=http://127.0.0.1:5173
# SGC_API_DOCS=0
# SGC_SERVE_FRONTEND=0
```

Login rate limit: **10 tentativas / IP / minuto** → HTTP 429.  
Logout **revoga** o `jti` do JWT em memória até a expiração (TTL padrão 120 min).

## Endpoints

- `POST /api/v1/auth/login` — público (AD + allowlist)
- `POST /api/v1/auth/logout` — JWT (auditoria)
- `GET /api/v1/auth/me` — JWT
- Demais `/api/v1/*` — JWT + perfil mínimo
- `GET /health` — público

## Perfis (hierarquia JWT)

| Perfil | Acesso |
|--------|--------|
| CONSULTA | Dashboard, chamados, equipes, técnicos, configurações |
| OPERADOR | + agendamentos (`/jobs`) |
| GESTOR | + inteligência artificial (`/ml/overview`) |
| ADMIN | Tudo (único perfil emitido no login atual) |

## CLI `criar_admin_painel.bat`

**Obsoleto para liberar acesso.** O login não usa senha local. O script só cria registro local excepcional; o acesso real depende da allowlist + AD.

## Fluxo de login

1. Allowlist (59817 ou N3 ativo) — se falhar, 401 sem consultar AD.
2. `LogonUser` Windows no domínio `SGC_AD_DOMAIN`.
3. Upsert local ADMIN + JWT + auditoria em `Tb_Auth_Audit`.
