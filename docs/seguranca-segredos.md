# Segurança operacional — segredos SGC

## Telegram

**Desabilitado por padrão.** O worker sobe sem `TELEGRAM_TOKEN` e **não** envia notificações.

Não é necessário configurar Telegram para operar atribuição GLPI + painel.

Se no futuro quiser reativar: defina `TELEGRAM_TOKEN` no ambiente (nunca hardcode no código).

## GLPI

Credenciais **somente** em `conf/glpi.dat` (Fernet + `chave.key`).  
Scripts como `listar_chamados.py` usam `ClTrade()` sem URL/senha no código.

Não coloque App-Token, usuário ou senha GLPI em arquivos `.py` versionados.

## Painel (JWT / AD)

Ver `backend/.env` e `backend/README-AUTH.md` (`SGC_JWT_SECRET`, `SGC_AD_DOMAIN`).
