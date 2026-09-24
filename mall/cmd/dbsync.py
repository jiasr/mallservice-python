import os
from oslo_config import cfg
from sqlalchemy import inspect

from mall.db.models.base import BASE
from mall.db.engines.mysql import get_engine
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
CONF_FILE_PATH = os.path.join('../../etc/mall', "mall.conf")
CONF = cfg.CONF

# 核心表清单：用于启动时校验数据库是否已初始化
_CORE_TABLES = [
    "t_mall_user",
    "t_mall_user_address",
    "t_mall_goods_catalog",
    "t_mall_goods_spu",
    "t_mall_goods_sku",
    "t_mall_goods_spec",
    "t_mall_admin_user",
    "t_mall_admin_role",
    "t_mall_admin_menu",
    "t_mall_admin_role_menu",
    "t_mall_config_system",
    "t_mall_storage_config",
    "t_mall_cart",
    "t_mall_order",
    "t_mall_order_item",
    "t_mall_config_wechatpay",
    "t_mall_freight_template",
    "t_mall_freight_region",
    "t_mall_delivery_account",
    "regions",
    "t_mall_stock_goods",
    "t_mall_stock_barcode_seq",
    "t_mall_stock_in_order",
    "t_mall_stock_in_item",
    "t_mall_stock_log",
    "t_mall_agreement",
    "t_mall_task",
    "t_mall_printer_config",
    "t_mall_print_log",
]


def load_config():
    """从配置文件加载配置（手动执行 dbsync.py 时使用）"""
    CONF(['--config-file', CONF_FILE_PATH], project="mall")
    CONF.log_opt_values(LOG, logging.INFO)


def _ensure_new_tables(engine):
    """幂等创建新增表（老库增量，不依赖 init.sql）。

    注意：必须放在 check_schema 的核心表检查之前执行，
    否则新表缺失会被误判为"数据库未初始化"而中断。
    """
    from mall.db.models.PickRecord.model import PickRecord
    existing = set(inspect(engine).get_table_names())
    if "t_mall_pick_record" not in existing:
        PickRecord.__table__.create(engine)
        LOG.info("t_mall_pick_record 已创建")
    else:
        LOG.info("t_mall_pick_record 已存在，跳过")

    from mall.db.models.DeliveryAccount.model import DeliveryAccount
    if "t_mall_delivery_account" not in existing:
        DeliveryAccount.__table__.create(engine)
        LOG.info("t_mall_delivery_account 已创建")
    else:
        LOG.info("t_mall_delivery_account 已存在，跳过")


def _migrate_missing_columns(engine, inspector):
    """幂等补齐新增字段（老库启动时自动 ALTER TABLE）"""
    with engine.connect() as conn:
        # t_mall_cart.cart_version：购物车版本号（乐观锁，2026-08-29 新增）
        cart_columns = {c["name"] for c in inspector.get_columns("t_mall_cart")}
        if "cart_version" not in cart_columns:
            conn.execute(
                "ALTER TABLE t_mall_cart ADD COLUMN cart_version INTEGER "
                "COMMENT '购物车版本号(乐观锁，用户级单调递增)' DEFAULT 0"
            )
            LOG.info("t_mall_cart 已新增列 cart_version")
        else:
            LOG.info("t_mall_cart.cart_version 已存在，跳过")

        # t_mall_order 状态时间 + 软删除回收站：发货/完成/取消/已删除/删除时间（2026-08-30 新增）
        order_columns = {c["name"] for c in inspector.get_columns("t_mall_order")}
        for _col, _ddl in [
            ("shipped_at", "DATETIME COMMENT '发货时间'"),
            ("completed_at", "DATETIME COMMENT '完成时间'"),
            ("canceled_at", "DATETIME COMMENT '取消时间'"),
            ("deleted", "INTEGER DEFAULT 0 COMMENT '软删除 0正常 1已删除(回收站)'"),
            ("deleted_at", "DATETIME COMMENT '删除时间'"),
            ("waybill_data", "TEXT COMMENT '电子面单数据(JSON)'"),
        ]:
            if _col not in order_columns:
                conn.execute(
                    "ALTER TABLE t_mall_order ADD COLUMN {} {}".format(_col, _ddl)
                )
                LOG.info("t_mall_order 已新增列 {}".format(_col))
            else:
                LOG.info("t_mall_order.{} 已存在，跳过".format(_col))

        # t_mall_delivery_account 中通开放平台渠道字段（2026-09-04 新增）
        da_columns = {c["name"] for c in inspector.get_columns("t_mall_delivery_account")}
        for _col, _ddl in [
            ("provider", "VARCHAR(16) NOT NULL DEFAULT 'wechat' COMMENT '渠道 wechat=微信物流助手 zto=中通开放平台'"),
            ("app_key", "VARCHAR(128) NOT NULL DEFAULT '' COMMENT '中通开放平台 appKey'"),
            ("app_secret", "VARCHAR(512) NOT NULL DEFAULT '' COMMENT '中通开放平台 appSecret(AES-GCM 加密存储)'"),
            ("partner_code", "VARCHAR(64) NOT NULL DEFAULT '' COMMENT '中通电子面单账号'"),
            ("customer_id", "VARCHAR(64) NOT NULL DEFAULT '' COMMENT '中通客户编码(对应 customerId)'"),
            ("partner_key", "VARCHAR(512) NOT NULL DEFAULT '' COMMENT '中通电子面单密码(AES-GCM 加密存储)'"),
            ("partner_type", "VARCHAR(16) NOT NULL DEFAULT '1' COMMENT '中通电子面单类型(对应 partnerType)'"),
            ("env", "VARCHAR(16) NOT NULL DEFAULT 'sandbox' COMMENT '中通环境 sandbox/prod'"),
            ("sandbox_openid", "VARCHAR(64) NOT NULL DEFAULT '' COMMENT '微信物流沙盒测试 openid(仅 delivery_id=TEST 时使用)'"),
        ]:
            if _col not in da_columns:
                conn.execute(
                    "ALTER TABLE t_mall_delivery_account ADD COLUMN {} {}".format(_col, _ddl)
                )
                LOG.info("t_mall_delivery_account 已新增列 {}".format(_col))
            else:
                LOG.info("t_mall_delivery_account.{} 已存在，跳过".format(_col))


# 运单管理菜单（启动时幂等初始化，避免每次升级都要手动补菜单）
_WAYBILL_MENU_FRONTPATH = "/express/waybill/list"


def _ensure_waybill_menu(engine, inspector):
    """幂等补齐「运单管理」菜单并授权给所有角色

    作为「订单管理」的子菜单；若已存在但挂错父级会自动纠正到订单管理下。
    找不到订单管理菜单时才降级为顶级菜单。
    """
    tables = set(inspector.get_table_names())
    if "t_mall_admin_menu" not in tables:
        return
    with engine.connect() as conn:
        # 父菜单 = 订单管理
        order_menu = conn.execute(
            "SELECT id FROM t_mall_admin_menu WHERE frontpath = '/order/list' LIMIT 1"
        ).fetchone()
        parent_id = int(order_menu[0]) if order_menu else 0

        row = conn.execute(
            "SELECT id, parent_id FROM t_mall_admin_menu "
            "WHERE frontpath = '{}' LIMIT 1".format(_WAYBILL_MENU_FRONTPATH)
        ).fetchone()
        if row:
            menu_id = int(row[0])
            current_parent = int(row[1]) if row[1] is not None else 0
            if parent_id and current_parent != parent_id:
                conn.execute(
                    "UPDATE t_mall_admin_menu SET parent_id = {} WHERE id = {}".format(
                        parent_id, menu_id)
                )
                LOG.info("菜单「运单管理」已移动到「订单管理」下(id=%s)", menu_id)
            else:
                LOG.info("菜单「运单管理」已存在（id=%s），跳过新增", menu_id)
        else:
            conn.execute(
                "INSERT INTO t_mall_admin_menu "
                "(name, frontpath, icon, parent_id, sort_order, permission, visible) "
                "VALUES ('运单管理', '{}', 'Van', {}, 100, '', 1)".format(
                    _WAYBILL_MENU_FRONTPATH, parent_id)
            )
            menu_id = int(conn.execute("SELECT LAST_INSERT_ID()").fetchone()[0])
            LOG.info("已新增菜单「运单管理」(id=%s, parent_id=%s)", menu_id, parent_id)

        if "t_mall_admin_role_menu" in tables:
            roles = conn.execute("SELECT id FROM t_mall_admin_role").fetchall()
            for (role_id,) in roles:
                role_id = int(role_id)
                exists = conn.execute(
                    "SELECT id FROM t_mall_admin_role_menu "
                    "WHERE role_id = {} AND menu_id = {} LIMIT 1".format(role_id, menu_id)
                ).fetchone()
                if exists:
                    continue
                conn.execute(
                    "INSERT INTO t_mall_admin_role_menu (role_id, menu_id) "
                    "VALUES ({}, {})".format(role_id, menu_id)
                )
                LOG.info("菜单「运单管理」已授权给角色 %s", role_id)
        conn.commit()


def check_schema():
    """仅检查核心表是否存在，不建表、不初始化数据。

    建表和初始数据统一由 mall/db/migration/init.sql 负责（全新库一键执行）。
    若核心表缺失，说明未初始化或使用的库有误，给出明确提示。
    """
    engine = get_engine()
    # 新增表幂等创建（必须在核心表检查前，避免误判未初始化）
    _ensure_new_tables(engine)

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    missing = [t for t in _CORE_TABLES if t not in existing]
    if missing:
        LOG.warning(
            "检测到数据库未完成初始化，缺失表: {}。"
            "全新部署请先执行: mysql -u root -p mall < mall/db/migration/init.sql".format(missing)
        )
        return False

    # 老库增量迁移：补齐新增列（幂等）
    _migrate_missing_columns(engine, inspector)

    # 新增菜单：运单管理（幂等，自动授权给所有角色）
    _ensure_waybill_menu(engine, inspector)

    LOG.info("数据库表结构校验通过（{} 张核心表均存在）".format(len(_CORE_TABLES)))
    return True


def auto_migrate():
    """启动时校验数据库结构（不含 load_config，由 mall/__init__.py 调用）"""
    return check_schema()


main = auto_migrate


if __name__ == "__main__":
    load_config()
    main()
