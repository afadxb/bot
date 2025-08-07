CREATE TABLE `trades` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `symbol` VARCHAR(20) NOT NULL,
  `side` ENUM('buy','sell') NOT NULL,
  `price` DECIMAL(18,8) NOT NULL,
  `volume` DECIMAL(18,8) NOT NULL,
  `tag` VARCHAR(32) NULL,
  `timestamp` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_symbol` (`symbol`),
  INDEX `idx_timestamp` (`timestamp`),
  INDEX `idx_symbol_timestamp` (`symbol`, `timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
