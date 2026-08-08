-- 库存商品表新增 text 字段：存储从商品库(GDS)请求到的原始数据(JSON)
ALTER TABLE `t_mall_stock_goods`
    ADD COLUMN `text` TEXT COMMENT 'GDS原始数据(JSON)' AFTER `remark`;
