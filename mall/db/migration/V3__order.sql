-- 订单主表
CREATE TABLE IF NOT EXISTS t_mall_order (
    id                 INT PRIMARY KEY AUTO_INCREMENT,
    order_id           VARCHAR(64) NOT NULL UNIQUE       COMMENT '订单号',
    user_id            VARCHAR(255) NOT NULL             COMMENT '用户ID',
    total_amount       INT NOT NULL DEFAULT 0            COMMENT '商品总金额(分)',
    discount_amount    INT DEFAULT 0                     COMMENT '优惠金额(分)',
    freight_amount     INT DEFAULT 0                     COMMENT '运费(分)',
    pay_amount         INT NOT NULL DEFAULT 0            COMMENT '实付金额(分)',
    pay_status         TINYINT DEFAULT 0                 COMMENT '支付状态 0未支付 1已支付 2已退款',
    order_status       TINYINT DEFAULT 0                 COMMENT '订单状态 0待付款 1已付款 2已发货 3已完成 4已取消',
    consignee_name     VARCHAR(100) NOT NULL             COMMENT '收货人姓名',
    consignee_mobile   VARCHAR(20) NOT NULL              COMMENT '收货人手机号',
    consignee_address  VARCHAR(500) NOT NULL             COMMENT '收货地址',
    remark             VARCHAR(500) DEFAULT ''           COMMENT '买家留言',
    payment_method     VARCHAR(32) DEFAULT ''            COMMENT '支付方式',
    paid_at            DATETIME                          COMMENT '支付时间',
    create_time        DATETIME DEFAULT NOW(),
    update_time        DATETIME DEFAULT NOW() ON UPDATE NOW(),
    INDEX idx_user (user_id),
    INDEX idx_order (order_id),
    INDEX idx_pay_status (pay_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单主表';

-- 订单商品明细表
CREATE TABLE IF NOT EXISTS t_mall_order_item (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    order_id        VARCHAR(64) NOT NULL                COMMENT '订单号',
    spu_id          VARCHAR(255) NOT NULL               COMMENT '商品SPU ID',
    sku_id          VARCHAR(255) NOT NULL               COMMENT '商品SKU ID',
    title           VARCHAR(500) NOT NULL               COMMENT '商品标题',
    thumb           VARCHAR(500) DEFAULT ''             COMMENT '商品图片',
    spec_label      VARCHAR(200) DEFAULT ''             COMMENT '规格描述',
    price           INT NOT NULL DEFAULT 0              COMMENT '成交价(分)',
    quantity        INT NOT NULL DEFAULT 1              COMMENT '购买数量',
    subtotal        INT NOT NULL DEFAULT 0              COMMENT '小计(分)',
    create_time     DATETIME DEFAULT NOW(),
    FOREIGN KEY (order_id) REFERENCES t_mall_order(order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单商品明细表';
