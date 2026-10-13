# Segurança operacional — segredos SGC

## Notificações

Telegram foi **removido** do produto. Atribuição segue sem notificação externa; o painel pode exibir notificações internas (`Tb_Notificacao`) quando configurado.

## GLPI

Credenciais **somente** em `conf/glpi.dat` (Fernet + `chave.key`).  
Scripts como `listar_chamados.py` usam `ClTrade()` sem URL/senha no código.

Não coloque App-Token, usuário ou senha GLPI em arquivos `.py` versionados.

## Painel (JWT / AD)

Ver `backend/.env` e `backend/README-AUTH.md` (`SGC_JWT_SECRET`, `SGC_AD_DOMAIN`).
