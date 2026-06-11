"""管理员数据访问层"""
import hashlib
from sqlalchemy import func

from mall.db.engines.mysql import get_session, get_engine
from mall.db.models.Admin.model import (
    AdminUser, AdminRole, AdminMenu, AdminRoleMenu
)
from mall.db.models.base import BASE
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

# 密码加盐
PASSWORD_SALT = "mall_admin_salt"


def _hash_password(password):
    """密码哈希"""
    return hashlib.sha256((password + PASSWORD_SALT).encode()).hexdigest()


class AdminUserDao:
    """管理员用户数据访问"""

    @classmethod
    def verify_login(cls, username, password):
        """验证登录

        Returns:
            dict or None: 成功返回用户信息字典，失败返回 None
        """
        session = get_session()
        with session.begin():
            user = session.query(AdminUser).filter(
                AdminUser.username == username,
                AdminUser.status == 1,
            ).first()
            if not user:
                return None
            if user.password_hash != _hash_password(password):
                return None
            return {
                "id": user.id,
                "username": user.username,
                "avatar": user.avatar or "",
                "role_id": user.role_id,
            }

    @classmethod
    def get_by_id(cls, user_id):
        """根据ID获取用户"""
        session = get_session()
        with session.begin():
            user = session.query(AdminUser).filter(AdminUser.id == user_id).first()
            if not user:
                return None
            return {
                "id": user.id,
                "username": user.username,
                "avatar": user.avatar or "",
                "role_id": user.role_id,
            }

    @classmethod
    def update_password(cls, user_id, old_password, new_password):
        """修改密码"""
        session = get_session()
        with session.begin():
            user = session.query(AdminUser).filter(AdminUser.id == user_id).first()
            if not user:
                return False, "用户不存在"
            if user.password_hash != _hash_password(old_password):
                return False, "原密码错误"
            user.password_hash = _hash_password(new_password)
            return True, "密码修改成功"

    @classmethod
    def get_menus_by_role(cls, role_id):
        """根据角色ID获取菜单列表（扁平列表）"""
        session = get_session()
        with session.begin():
            menus = session.query(AdminMenu).join(
                AdminRoleMenu, AdminMenu.id == AdminRoleMenu.menu_id
            ).filter(
                AdminRoleMenu.role_id == role_id,
                AdminMenu.visible == 1,
            ).order_by(AdminMenu.sort_order).all()

            result = []
            for m in menus:
                result.append({
                    "id": m.id,
                    "name": m.name,
                    "frontpath": m.frontpath or "",
                    "icon": m.icon or "",
                    "parent_id": m.parent_id,
                    "sort_order": m.sort_order,
                    "permission": m.permission or "",
                })
            return result

    @classmethod
    def build_menu_tree(cls, flat_menus):
        """将扁平菜单列表构建为树形结构（前端需要的格式），按 sort_order 排序
        父菜单隐藏时，子菜单也一并过滤
        """
        # 收集所有可见菜单的 ID，以及它们的父级 ID
        visible_ids = {m["id"] for m in flat_menus}

        # 多轮过滤：如果父菜单不在可见集合中，子菜单也应移除
        def _filter_by_parent(items):
            result = []
            for m in items:
                pid = m["parent_id"]
                # parent_id=0 的顶级菜单直接保留；否则检查父菜单是否在列表中
                if pid == 0 or pid in visible_ids:
                    result.append(m)
            return result

        flat_menus = _filter_by_parent(flat_menus)
        visible_ids = {m["id"] for m in flat_menus}

        menu_map = {}
        for m in flat_menus:
            menu_map[m["id"]] = {
                "name": m["name"],
                "frontpath": m["frontpath"],
                "icon": m["icon"],
                "sort_order": m["sort_order"],
                "child": [],
            }

        roots = []
        for m in flat_menus:
            pid = m["parent_id"]
            if pid == 0 or pid not in menu_map:
                roots.append(menu_map[m["id"]])
            else:
                menu_map[pid]["child"].append(menu_map[m["id"]])

        # 按 sort_order 排序
        roots.sort(key=lambda x: x["sort_order"])
        for node in menu_map.values():
            if node["child"]:
                node["child"].sort(key=lambda x: x["sort_order"])

        return roots

    @classmethod
    def get_rule_names_by_role(cls, role_id):
        """根据角色ID获取权限标识列表"""
        session = get_session()
        with session.begin():
            menus = session.query(AdminMenu.permission).join(
                AdminRoleMenu, AdminMenu.id == AdminRoleMenu.menu_id
            ).filter(
                AdminRoleMenu.role_id == role_id,
                AdminMenu.permission != "",
            ).all()
            return [m.permission for m in menus if m.permission]

    # ==================== 默认数据初始化 ====================

    @classmethod
    def _table_is_empty(cls, table_class):
        """检查表是否为空"""
        session = get_session()
        with session.begin():
            count = session.query(func.count(table_class.id)).scalar()
            return count == 0

    @classmethod
    def create_default_menus(cls):
        """创建默认菜单数据"""
        if not cls._table_is_empty(AdminMenu):
            LOG.info("AdminMenu 表已有数据，跳过初始化")
            return

        session = get_session()
        with session.begin():
            default_menus = [
                # 顶级菜单
                (1, "仪表盘", "/", "Odometer", 0, 1, ""),
                (2, "商品管理", "/goods/list", "Goods", 0, 2, ""),
                (3, "订单管理", "/order/list", "Tickets", 0, 3, ""),
                (4, "团购管理", "/groupon/list", "ShoppingCartFull", 0, 4, ""),
                (5, "用户管理", "/user/list", "User", 0, 5, ""),
                (6, "分销管理", "/agent/list", "Share", 0, 6, ""),
                (7, "优惠券管理", "/coupon/list", "Discount", 0, 7, ""),
                (8, "系统设置", "/setting/base", "Setting", 0, 8, ""),

                # 商品管理子菜单
                (9, "商品列表", "/goods/list", "List", 2, 1, ""),
                (10, "分类管理", "/category/list", "Menu", 2, 2, ""),
                (11, "规格管理", "/goods/spec", "SetUp", 2, 3, ""),

                # 订单管理子菜单
                (13, "订单列表", "/order/list", "List", 3, 1, ""),
                (14, "退款管理", "/order/refund", "Warning", 3, 2, ""),

                # 团购管理子菜单
                (15, "团购列表", "/groupon/list", "List", 4, 1, ""),
                (16, "添加团购", "/groupon/add", "Plus", 4, 2, "groupon:add"),

                # 用户管理子菜单
                (17, "用户列表", "/user/list", "List", 5, 1, ""),

                # 分销管理子菜单
                (18, "分销员列表", "/agent/list", "List", 6, 1, ""),
                (19, "佣金管理", "/agent/commission", "Money", 6, 2, ""),

                # 优惠券管理子菜单
                (20, "优惠券列表", "/coupon/list", "List", 7, 1, ""),
                (21, "添加优惠券", "/coupon/add", "Plus", 7, 2, "coupon:add"),

                # 系统设置子菜单
                (22, "基本设置", "/setting/base", "Tools", 8, 1, ""),
                (23, "角色与权限", "/setting/role", "Key", 8, 2, "admin:manage"),
                (24, "存储配置", "/setting/objectsto", "Folder", 8, 3, ""),
            ]

            for (mid, name, frontpath, icon, parent_id, sort_order, permission) in default_menus:
                menu = AdminMenu(
                    id=mid,
                    name=name,
                    frontpath=frontpath,
                    icon=icon,
                    parent_id=parent_id,
                    sort_order=sort_order,
                    permission=permission,
                    visible=1,
                )
                session.add(menu)

            LOG.info("已初始化 {} 条默认菜单数据".format(len(default_menus)))

    @classmethod
    def create_default_role(cls):
        """创建默认超级管理员角色"""
        if not cls._table_is_empty(AdminRole):
            LOG.info("AdminRole 表已有数据，跳过初始化")
            return

        session = get_session()
        with session.begin():
            role = AdminRole(
                id=1,
                name="超级管理员",
                description="拥有所有权限",
                status=1,
            )
            session.add(role)
            LOG.info("已初始化默认角色：超级管理员")

    @classmethod
    def create_default_role_menus(cls):
        """为超级管理员角色分配所有菜单"""
        if not cls._table_is_empty(AdminRoleMenu):
            LOG.info("AdminRoleMenu 表已有数据，跳过初始化")
            return

        session = get_session()
        with session.begin():
            menus = session.query(AdminMenu.id).all()
            for (menu_id,) in menus:
                rm = AdminRoleMenu(role_id=1, menu_id=menu_id)
                session.add(rm)
            LOG.info("已为超级管理员角色分配 {} 个菜单权限".format(len(menus)))

    @classmethod
    def create_default_admin(cls):
        """创建默认管理员账号 admin/admin123"""
        if not cls._table_is_empty(AdminUser):
            LOG.info("AdminUser 表已有数据，跳过初始化")
            return

        session = get_session()
        with session.begin():
            user = AdminUser(
                id=1,
                username="admin",
                password_hash=_hash_password("admin123"),
                avatar="https://example.com/avatar.png",
                role_id=1,
                status=1,
            )
            session.add(user)
            LOG.info("已初始化默认管理员账号：admin / admin123")

    @classmethod
    def init_all_default_data(cls):
        """初始化所有默认数据（按依赖顺序）"""
        try:
            cls.create_default_menus()
            cls.create_default_role()
            cls.create_default_role_menus()
            cls.create_default_admin()
            cls._init_system_config()
            cls._init_storage_config()
            LOG.info("Admin 默认数据初始化完成")
        except Exception as e:
            LOG.error("Admin 默认数据初始化失败: {}".format(e))

    @classmethod
    def _init_system_config(cls):
        """初始化系统配置表及默认配置"""
        from mall.db.models.SystemConfig.model import SystemConfig

        if not cls._table_is_empty(SystemConfig):
            LOG.info("SystemConfig 表已有数据，跳过初始化")
            return

        session = get_session()
        with session.begin():
            default_configs = [
                # 基础设置
                ("site_name", "我的商城", "商城名称", "general"),
                ("logo", "", "商城 Logo URL", "general"),
                ("service_phone", "400-123-4567", "客服电话", "general"),
                ("service_email", "service@example.com", "客服邮箱", "general"),
                # 注册与访问
                ("allow_register", "true", "是否允许注册", "access"),
                ("register_need_audit", "false", "注册是否需要审核", "access"),
                ("enable_distribution", "true", "是否启用分销", "access"),
            ]

            for key, value, description, group in default_configs:
                config = SystemConfig(
                    config_key=key,
                    config_value=value,
                    description=description,
                    config_group=group,
                )
                session.add(config)

            LOG.info("已初始化 {} 条系统默认配置".format(len(default_configs)))

    @classmethod
    def _init_storage_config(cls):
        """初始化对象存储配置（独立表）"""
        from mall.db.models.StorageConfig.model import StorageConfig

        if not cls._table_is_empty(StorageConfig):
            LOG.info("StorageConfig 表已有数据，跳过初始化")
            return

        session = get_session()
        with session.begin():
            config = StorageConfig(
                endpoint="http://82.156.225.136:9000",
                access_key="admin",
                secret_key="password123",
                bucket_name="mall-images1",
                region="us-east-1",
                public_endpoint="http://82.156.225.136:9000",
                upload_max_size=10,
                upload_allowed_types="jpg,jpeg,png,gif,webp,bmp",
            )
            session.add(config)
            LOG.info("已初始化对象存储默认配置")
