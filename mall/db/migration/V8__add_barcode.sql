-- 商品SKU表增加国际编码字段
ALTER TABLE t_mall_goods_sku ADD COLUMN barcode VARCHAR(64) DEFAULT '' COMMENT '国际编码(条形码/EAN-13)' AFTER price;

