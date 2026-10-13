-- Log de decisões de classificação/atribuição do SGC (Fase 3)

CREATE TABLE IF NOT EXISTS `Tb_ML_Log` (
  `idml` int(11) NOT NULL AUTO_INCREMENT,
  `Id_Glpi` int(11) NOT NULL,
  `Metodo` varchar(20) DEFAULT NULL,
  `Equipe_Prevista` varchar(5) DEFAULT NULL,
  `Equipe_ML` varchar(5) DEFAULT NULL,
  `Equipe_2a` varchar(5) DEFAULT NULL,
  `Confianca` decimal(5,2) DEFAULT NULL,
  `Margem` decimal(5,2) DEFAULT NULL,
  `Motivo_Rejeicao` varchar(255) DEFAULT NULL,
  `Motivo_Atrib` varchar(500) DEFAULT NULL,
  `Categoria` varchar(500) DEFAULT NULL,
  `Localizacao` varchar(500) DEFAULT NULL,
  `Data_Registro` datetime DEFAULT NULL,
  PRIMARY KEY (`idml`),
  KEY `idx_ml_log_glpi` (`Id_Glpi`),
  KEY `idx_ml_log_data` (`Data_Registro`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
