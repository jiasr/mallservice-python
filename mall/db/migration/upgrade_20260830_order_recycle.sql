-- ============================================
-- 订单回收站（软删除）升级脚本  2026-08-30
-- 适用：已有 t_mall_order 表的存量库
-- 执行：mysql -u<user> -p<pass> <dbname> < upgrade_20260830_order_recycle.sql
-- ============================================
ALTER TABLE t_mall_order
	ADD COLUMN deleted INTEGER DEFAULT 0 COMMENT '软删除 0正常 1已删除(回收站)' AFTER local_delivery_time,
	ADD COLUMN deleted_at DATETIME COMMENT '删除时间' AFTER deleted;
