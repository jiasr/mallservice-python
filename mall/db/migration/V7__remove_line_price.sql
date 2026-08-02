-- 移除划线价字段
ALTER TABLE t_mall_goods_spu DROP COLUMN min_line_price;
ALTER TABLE t_mall_goods_spu DROP COLUMN max_line_price;
ALTER TABLE t_mall_goods_sku DROP COLUMN line_price;
