-- 购物车表
CREATE TABLE IF NOT EXISTS t_mall_cart (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    user_id     VARCHAR(255) NOT NULL              COMMENT '用户ID',
    spu_id      VARCHAR(255) NOT NULL              COMMENT '商品SPU ID',
    sku_id      VARCHAR(255) NOT NULL              COMMENT '商品SKU ID',
    quantity    INT NOT NULL DEFAULT 1             COMMENT '加购数量',
    is_selected TINYINT(1) DEFAULT 1               COMMENT '是否选中 1是 0否',
    create_time DATETIME DEFAULT NOW()             COMMENT '创建时间',
    update_time DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间',
    UNIQUE KEY uk_user_sku (user_id, sku_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='购物车表';
