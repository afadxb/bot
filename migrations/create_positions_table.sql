CREATE TABLE `positions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `symbol` VARCHAR(20) NOT NULL,
  `entry_price` DECIMAL(18,8) NOT NULL,
  `entry_time` DATETIME NOT NULL,
  `exit_price` DECIMAL(18,8) NULL,
  `exit_time` DATETIME NULL,
  `volume` DECIMAL(18,8) NOT NULL,
  `tag` VARCHAR(32) NULL,
  `pnl` DECIMAL(18,8) NULL,
  `status` ENUM('open','closed') NOT NULL DEFAULT 'open',
  PRIMARY KEY (`id`),
  INDEX `idx_pos_symbol` (`symbol`),
  INDEX `idx_status` (`status`),
  INDEX `idx_entry_time` (`entry_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;