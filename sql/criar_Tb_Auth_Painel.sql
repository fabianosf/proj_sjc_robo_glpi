-- Autenticacao do painel SGC (nao altera tabelas operacionais do worker)
-- Executar na base MariaDB do SGC (mesmo sgc.dat)
--
-- mysql -u USER -p DB_SGC < sql/criar_Tb_Auth_Painel.sql

CREATE TABLE IF NOT EXISTS `Tb_Usuario_Painel` (
  `id_usuario` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(80) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `perfil` enum('ADMIN','GESTOR','OPERADOR','CONSULTA') NOT NULL,
  `nome` varchar(120) DEFAULT NULL,
  `ativo` tinyint(1) NOT NULL DEFAULT 1,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `ultimo_login_em` datetime DEFAULT NULL,
  PRIMARY KEY (`id_usuario`),
  UNIQUE KEY `uk_usuario_painel_username` (`username`),
  KEY `idx_usuario_painel_perfil` (`perfil`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `Tb_Auth_Audit` (
  `id_audit` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(80) DEFAULT NULL,
  `evento` varchar(40) NOT NULL,
  `sucesso` tinyint(1) NOT NULL DEFAULT 0,
  `ip` varchar(64) DEFAULT NULL,
  `user_agent` varchar(255) DEFAULT NULL,
  `detalhe` varchar(255) DEFAULT NULL,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_audit`),
  KEY `idx_auth_audit_evento` (`evento`),
  KEY `idx_auth_audit_data` (`criado_em`),
  KEY `idx_auth_audit_user` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
