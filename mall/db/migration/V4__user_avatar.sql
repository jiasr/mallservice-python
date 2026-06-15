-- 用户表增加头像字段
ALTER TABLE t_mall_user ADD COLUMN avatar VARCHAR(500) DEFAULT '' COMMENT '头像URL';
