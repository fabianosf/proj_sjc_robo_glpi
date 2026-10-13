-- Correções detectadas: equipe SGC na atribuição vs equipe no fechamento GLPI (Fase 3)

CREATE TABLE IF NOT EXISTS `Tb_Correcao_Feedback` (
  `idcor` int(11) NOT NULL AUTO_INCREMENT,
  `Id_Glpi` int(11) NOT NULL,
  `Titulo` varchar(500) DEFAULT NULL,
  `Categoria` varchar(500) DEFAULT NULL,
  `Descricao` varchar(2500) DEFAULT NULL,
  `Localizacao` varchar(500) DEFAULT NULL,
  `Equipe_SGC` varchar(5) DEFAULT NULL,
  `Equipe_Correta` varchar(5) DEFAULT NULL,
  `Tecnico_Fechamento` varchar(20) DEFAULT NULL,
  `Data_Deteccao` datetime DEFAULT NULL,
  PRIMARY KEY (`idcor`),
  UNIQUE KEY `uk_correcao_glpi` (`Id_Glpi`),
  KEY `idx_correcao_equipe` (`Equipe_Correta`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
