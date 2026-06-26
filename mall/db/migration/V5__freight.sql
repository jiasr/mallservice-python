-- V5: 运费模板 + 配送方式字段
-- 适用场景：已有订单数据库需要升级

-- 1. 运费模板表
CREATE TABLE IF NOT EXISTS `t_mall_freight_template` (
  `id`              INT PRIMARY KEY AUTO_INCREMENT,
  `name`            VARCHAR(100) NOT NULL               COMMENT '模板名称',
  `pricing_type`    INT DEFAULT 1                       COMMENT '计费方式 0=固定运费 1=按件',
  `fixed_fee`       INT DEFAULT 0                       COMMENT '固定运费金额(分)',
  `first_unit`      INT DEFAULT 1                       COMMENT '首件数量',
  `first_fee`       INT DEFAULT 0                       COMMENT '首件费用(分)',
  `continue_unit`   INT DEFAULT 1                       COMMENT '续件数量',
  `continue_fee`    INT DEFAULT 0                       COMMENT '续件费用(分)',
  `free_threshold`  INT DEFAULT 0                       COMMENT '满额包邮门槛(分)',
  `is_default`      INT DEFAULT 0                       COMMENT '是否默认模板',
  `create_time`     DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time`     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='运费模板';

-- 2. 运费地区规则表
CREATE TABLE IF NOT EXISTS `t_mall_freight_region` (
  `id`              INT PRIMARY KEY AUTO_INCREMENT,
  `template_id`     INT NOT NULL                        COMMENT '关联模板ID',
  `region_code`     VARCHAR(20) NOT NULL                COMMENT '省份编码',
  `region_name`     VARCHAR(50) NOT NULL                COMMENT '省份名称',
  `is_free`         INT DEFAULT 0                       COMMENT '是否包邮 1=是',
  `fixed_fee`       INT DEFAULT NULL                    COMMENT '该地区固定运费(分)',
  `first_fee`       INT DEFAULT NULL                    COMMENT '该地区首费(分)',
  `continue_fee`    INT DEFAULT NULL                    COMMENT '该地区续费(分)',
  `free_threshold`  INT DEFAULT NULL                    COMMENT '该地区包邮门槛(分)',
  INDEX `idx_fr_template` (`template_id`),
  INDEX `idx_fr_region` (`region_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='运费地区规则';

-- 3. 订单表增加配送方式字段
ALTER TABLE `t_mall_order`
  ADD COLUMN IF NOT EXISTS `delivery_type` INT DEFAULT 0 COMMENT '配送方式 0=快递 1=同城配送 2=自提' AFTER `shipping_no`,
  ADD COLUMN IF NOT EXISTS `pickup_store_id` INT DEFAULT 0 COMMENT '自提门店ID' AFTER `delivery_type`,
  ADD COLUMN IF NOT EXISTS `pickup_store_name` VARCHAR(100) DEFAULT '' COMMENT '自提门店名称' AFTER `pickup_store_id`,
  ADD COLUMN IF NOT EXISTS `pickup_code` VARCHAR(10) DEFAULT '' COMMENT '自提核销码' AFTER `pickup_store_name`,
  ADD COLUMN IF NOT EXISTS `pickup_expire_time` DATETIME COMMENT '自提截止时间' AFTER `pickup_code`,
  ADD COLUMN IF NOT EXISTS `local_delivery_time` VARCHAR(50) DEFAULT '' COMMENT '同城配送时段' AFTER `pickup_expire_time`;

-- 4. 商品表增加运费模板和配送方式字段
ALTER TABLE `t_mall_goods_spu`
  ADD COLUMN IF NOT EXISTS `freight_template_id` INT DEFAULT 0 COMMENT '运费模板ID' AFTER `stock_quantity`,
  ADD COLUMN IF NOT EXISTS `delivery_type` INT DEFAULT 0 COMMENT '配送方式' AFTER `freight_template_id`;

-- 5. 微信支付配置表增加证书字段
ALTER TABLE `t_mall_wechat_pay_config`
  ADD COLUMN IF NOT EXISTS `certificate` VARCHAR(4096) DEFAULT '' COMMENT '商户证书(PEM)' AFTER `private_key`;

-- 6. 插入默认运费模板
INSERT INTO `t_mall_freight_template` (`name`, `pricing_type`, `fixed_fee`, `first_unit`, `first_fee`, `continue_unit`, `continue_fee`, `free_threshold`, `is_default`)
SELECT '默认运费模板', 1, 0, 1, 1000, 1, 500, 0, 1
WHERE NOT EXISTS (SELECT 1 FROM `t_mall_freight_template` WHERE `is_default` = 1);

-- 6. 添加菜单（如果不存在）
INSERT IGNORE INTO `t_mall_admin_menu` (`id`, `name`, `frontpath`, `icon`, `parent_id`, `sort_order`, `permission`, `visible`) VALUES
(9,  '配送管理', '/freight/list', 'Truck', 0, 9, '', 1),
(26, '运费模板', '/freight/list', 'List',   9, 1, '', 1),
(27, '添加模板', '/freight/add', 'Plus',   9, 2, 'freight:add', 1);

-- 7. 为超级管理员角色分配新菜单权限
INSERT IGNORE INTO `t_mall_admin_role_menu` (`role_id`, `menu_id`)
SELECT 1, id FROM `t_mall_admin_menu` WHERE `id` IN (9, 26, 27);
