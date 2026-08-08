-- 进销存独立库存商品表：完全独立于商城SKU
-- 注意：表名已于 V11 迁移改为 stock_goods
CREATE TABLE IF NOT EXISTS `t_mall_inv_goods` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `barcode` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '商品条码',
    `name` VARCHAR(200) NOT NULL DEFAULT '' COMMENT '商品名称',
    `brand` VARCHAR(100) DEFAULT '' COMMENT '品牌',
    `spec` VARCHAR(100) DEFAULT '' COMMENT '规格',
    `unit` VARCHAR(20) DEFAULT '' COMMENT '单位(个/件/箱)',
    `category` VARCHAR(100) DEFAULT '' COMMENT '分类',
    `cost_price` DECIMAL(10,2) DEFAULT 0 COMMENT '成本价',
    `sale_price` DECIMAL(10,2) DEFAULT 0 COMMENT '参考售价',
    `stock_quantity` INT DEFAULT 0 COMMENT '当前库存',
    `warn_threshold` INT DEFAULT 0 COMMENT '库存预警阈值(低于则提示)',
    `supplier` VARCHAR(200) DEFAULT '' COMMENT '供应商',
    `shelf_life_days` INT DEFAULT 0 COMMENT '保质期天数(0=无保质期)',
    `image_url` VARCHAR(500) DEFAULT '' COMMENT '商品图片',
    `remark` VARCHAR(500) DEFAULT '' COMMENT '备注',
    `status` TINYINT DEFAULT 1 COMMENT '状态: 1=启用 0=停用',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_barcode` (`barcode`),
    KEY `idx_name` (`name`),
    KEY `idx_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='进销存独立库存商品表';

-- 入库单主表：增加入库总金额
ALTER TABLE `t_mall_stock_in_order`
    ADD COLUMN `total_amount` DECIMAL(10,2) DEFAULT 0 COMMENT '入库总金额' AFTER `total_quantity`;

-- 入库明细表：改为关联独立库存商品
ALTER TABLE `t_mall_stock_in_item`
    ADD COLUMN `goods_id` INT NOT NULL DEFAULT 0 COMMENT '关联t_mall_inv_goods.id' AFTER `order_id`,
    ADD COLUMN `cost_price` DECIMAL(10,2) DEFAULT 0 COMMENT '入库成本价' AFTER `quantity`,
    ADD KEY `idx_goods_id` (`goods_id`);

-- 库存流水表：改为关联独立库存商品
ALTER TABLE `t_mall_stock_log`
    ADD COLUMN `goods_id` INT NOT NULL DEFAULT 0 COMMENT '关联t_mall_inv_goods.id' AFTER `id`,
    ADD KEY `idx_goods_id` (`goods_id`);
