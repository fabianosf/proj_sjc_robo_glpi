-- Notificações do painel SGC (redirecionamento de chamados, etc.)
-- mysql -u USER -p DB_SGC < sql/criar_Tb_Notificacao.sql

CREATE TABLE IF NOT EXISTS `Tb_Notificacao` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `destinatario` varchar(80) NOT NULL COMMENT 'Usuario AD ou matrícula do destinatário',
  `tipo` varchar(40) NOT NULL DEFAULT 'TICKETS_REDIRECTED',
  `titulo` varchar(160) NOT NULL,
  `mensagem` varchar(500) NOT NULL,
  `ref_ids` varchar(500) DEFAULT NULL COMMENT 'IDs de chamados (CSV), opcional',
  `lida` tinyint(1) NOT NULL DEFAULT 0,
  `criado_por` varchar(80) DEFAULT NULL,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `lida_em` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_notif_dest_lida` (`destinatario`, `lida`),
  KEY `idx_notif_criado` (`criado_em`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
