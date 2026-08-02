-- 库存管理相关表

-- 1. 入库单主表
CREATE TABLE IF NOT EXISTS `t_mall_stock_in_order` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `order_no` VARCHAR(64) NOT NULL COMMENT '入库单号(RK+年月日+4位流水)',
    `type` TINYINT DEFAULT 1 COMMENT '入库类型: 1=采购入库 2=退货入库 3=调拨入库 4=盘盈入库',
    `total_quantity` INT DEFAULT 0 COMMENT '入库总数量',
    `status` TINYINT DEFAULT 0 COMMENT '状态: 0=草稿 1=已提交 2=已取消',
    `operator_id` INT DEFAULT 0 COMMENT '操作人ID',
    `operator_name` VARCHAR(100) DEFAULT '' COMMENT '操作人姓名',
    `remark` VARCHAR(500) DEFAULT '' COMMENT '备注',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_order_no` (`order_no`),
    KEY `idx_status` (`status`),
    KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='入库单主表';

-- 2. 入库明细表
CREATE TABLE IF NOT EXISTS `t_mall_stock_in_item` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `order_id` INT NOT NULL COMMENT '关联入库单ID',
    `sku_id` VARCHAR(255) NOT NULL COMMENT 'SKU ID(对应t_mall_goods_sku.id)',
    `spu_id` VARCHAR(255) NOT NULL COMMENT 'SPU ID(对应t_mall_goods_spu.id)',
    `quantity` INT DEFAULT 0 COMMENT '入库数量',
    `batch_no` VARCHAR(64) DEFAULT '' COMMENT '批次号',
    `remark` VARCHAR(500) DEFAULT '' COMMENT '备注',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY `idx_order_id` (`order_id`),
    KEY `idx_sku_id` (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='入库明细表';

-- 3. 库存流水表
CREATE TABLE IF NOT EXISTS `t_mall_stock_log` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `sku_id` VARCHAR(255) NOT NULL COMMENT 'SKU ID',
    `spu_id` VARCHAR(255) NOT NULL COMMENT 'SPU ID',
    `change_qty` INT NOT NULL COMMENT '变动数量(正=入库/盘盈, 负=出库/盘亏)',
    `balance_after` INT DEFAULT 0 COMMENT '变动后结存数量',
    `biz_type` VARCHAR(32) NOT NULL COMMENT '业务类型: stock_in=入库 stock_out=出库 stock_check=盘点',
    `biz_no` VARCHAR(64) DEFAULT '' COMMENT '业务单号(入库单号/出库单号等)',
    `operator_id` INT DEFAULT 0 COMMENT '操作人ID',
    `operator_name` VARCHAR(100) DEFAULT '' COMMENT '操作人姓名',
    `remark` VARCHAR(500) DEFAULT '' COMMENT '备注',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY `idx_sku_id` (`sku_id`),
    KEY `idx_biz_type` (`biz_type`),
    KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存流水表';
