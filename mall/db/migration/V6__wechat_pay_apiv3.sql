-- V6: 微信支付配置表新增 apiv3_key 字段 + mch_key 扩容
-- 适用场景：已有微信支付配置需要升级
-- 兼容 MySQL 5.7+（列已存在时跳过）

SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 't_mall_wechat_pay_config'
    AND COLUMN_NAME = 'apiv3_key');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE `t_mall_wechat_pay_config` ADD COLUMN `apiv3_key` VARCHAR(64) DEFAULT '' COMMENT ''APIv3密钥(32位,解密回调)'' AFTER `mch_key`',
    'SELECT ''apiv3_key already exists''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- mch_key 扩容以容纳 PEM 公钥
ALTER TABLE `t_mall_wechat_pay_config` MODIFY `mch_key` TEXT;
