-- 无码商品条码流水号表（单行计数器）：记录当前条码流水号，从 001 开始
-- 只保留一行，每次生成条码时读取 seq 并自增，保证条码连续且唯一
CREATE TABLE IF NOT EXISTS `t_mall_stock_barcode_seq` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键，固定为1（单行计数器）',
  `barcode` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '最近生成的条码',
  `seq` INT NOT NULL DEFAULT 0 COMMENT '当前条码流水号（从1开始）',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='无码商品条码流水号表(单行计数器)';

-- 初始化流水号记录
INSERT INTO `t_mall_stock_barcode_seq` (`id`, `barcode`, `seq`) VALUES (1, '', 0)
  ON DUPLICATE KEY UPDATE `id` = `id`;

-- 库存商品表：新增字段，区分条码是否为无码商品自动生成
ALTER TABLE `t_mall_stock_goods`
  ADD COLUMN `is_auto_barcode` TINYINT NOT NULL DEFAULT 0 COMMENT '条码来源: 0=手动/已有条码 1=无码商品自动生成';
