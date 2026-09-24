-- 快递账号表支持散单(现付)账号
-- 2026-09-24
-- 说明: 微信物流助手里 can_use_cash=1 的快递公司(如顺丰 SF)可直接用现付编码 cash_biz_id
--       下单, 无需也【不能】调 bindAccount 绑定(未签约月结账号, 绑定会报 9300531)。
--       is_cash=1 标记该账号为散单: 入库时跳过微信绑定, 下单时按官方要求传 expect_time。

ALTER TABLE t_mall_delivery_account
    ADD COLUMN is_cash TINYINT NOT NULL DEFAULT 0 COMMENT '散单(现付)账号 1=是 0=否(月结,需微信绑定)' AFTER env;
