-- Histórico diário de assertividade (performance %) do SGC

CREATE TABLE IF NOT EXISTS `tb_performance` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `Performance` decimal(5,2) NOT NULL DEFAULT 0.00,
  `Data` date NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tb_performance_data` (`Data`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
