-- 库存商品表改名：t_mall_inv_goods -> t_mall_stock_goods
-- 若已改为 stock_goods（中间名）则再次重命名；两表都不存在时跳过
SET @old := (SELECT COUNT(*) FROM information_schema.TABLES
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 't_mall_inv_goods');
SET @mid := (SELECT COUNT(*) FROM information_schema.TABLES
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stock_goods');

-- 情况1：原表还在（未改过名）
SET @sql1 := IF(@old = 1,
    'RENAME TABLE `t_mall_inv_goods` TO `t_mall_stock_goods`', 'SELECT 1');
PREPARE stmt1 FROM @sql1; EXECUTE stmt1; DEALLOCATE PREPARE stmt1;

-- 情况2：已是中间名 stock_goods
SET @sql2 := IF(@mid = 1,
    'RENAME TABLE `stock_goods` TO `t_mall_stock_goods`', 'SELECT 1');
PREPARE stmt2 FROM @sql2; EXECUTE stmt2; DEALLOCATE PREPARE stmt2;
