-- Tabela temporária de feedback para treino do ML
-- Armazena chamados FECHADOS do GLPI (últimos 6 meses) com técnico e equipe inferida via Tb_Atrib

CREATE TABLE IF NOT EXISTS `Tb_Ticket_Feedback_Temp` (
  `idfb` int(11) NOT NULL AUTO_INCREMENT,
  `Id_Glpi` int(11) NOT NULL,
  `Titulo` varchar(500) NOT NULL,
  `Categoria` varchar(500) DEFAULT NULL,
  `Descricao` varchar(2500) DEFAULT NULL,
  `Localizacao` varchar(500) DEFAULT NULL,
  `Tecnico` varchar(20) DEFAULT NULL,
  `Equipe` varchar(5) DEFAULT NULL,
  `Data_Abertura` datetime DEFAULT NULL,
  `Data_Fechamento` datetime DEFAULT NULL,
  `Data_Sync` datetime DEFAULT NULL,
  PRIMARY KEY (`idfb`),
  UNIQUE KEY `uk_feedback_glpi` (`Id_Glpi`),
  KEY `idx_feedback_equipe` (`Equipe`),
  KEY `idx_feedback_fechamento` (`Data_Fechamento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
