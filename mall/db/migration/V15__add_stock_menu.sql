-- V15: 新增进销存菜单（库存商品等），解决管理端左侧菜单缺少进销存入口的问题
-- 说明：此前迁移从未定义过进销存菜单，前端 /stock/goods/list 路由存在但未被菜单引用，导致侧边栏不显示。

-- 1. 添加进销存菜单（不存在才插入）
INSERT IGNORE INTO `t_mall_admin_menu` (`id`, `name`, `frontpath`, `icon`, `parent_id`, `sort_order`, `permission`, `visible`) VALUES
(30, '进销存', '/stock/goods/list', 'Box', 0, 10, '', 1),
(31, '库存商品', '/stock/goods/list', 'List', 30, 1, 'stock:list', 1);

-- 2. 为超级管理员角色（role_id=1）分配进销存菜单权限
INSERT IGNORE INTO `t_mall_admin_role_menu` (`role_id`, `menu_id`)
SELECT 1, id FROM `t_mall_admin_menu` WHERE `id` IN (30, 31);
