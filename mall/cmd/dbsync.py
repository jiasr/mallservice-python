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
    "regions",
    "t_mall_stock_goods",
    "t_mall_stock_barcode_seq",
    "t_mall_stock_in_order",
    "t_mall_stock_in_item",
    "t_mall_stock_log",
    "t_mall_agreement",
    "t_mall_task",
    "t_mall_printer_config",
]


def load_config():
    """从配置文件加载配置（手动执行 dbsync.py 时使用）"""
    CONF(['--config-file', CONF_FILE_PATH], project="mall")
    CONF.log_opt_values(LOG, logging.INFO)


def check_schema():
    """仅检查核心表是否存在，不建表、不初始化数据。

    建表和初始数据统一由 mall/db/migration/init.sql 负责（全新库一键执行）。
    若核心表缺失，说明未初始化或使用的库有误，给出明确提示。
    """
    engine = get_engine()
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    missing = [t for t in _CORE_TABLES if t not in existing]
    if missing:
        LOG.warning(
            "检测到数据库未完成初始化，缺失表: {}。"
            "全新部署请先执行: mysql -u root -p mall < mall/db/migration/init.sql".format(missing)
        )
        return False

    LOG.info("数据库表结构校验通过（{} 张核心表均存在）".format(len(_CORE_TABLES)))
    return True


def auto_migrate():
    """启动时校验数据库结构（不含 load_config，由 mall/__init__.py 调用）"""
    return check_schema()


main = auto_migrate


if __name__ == "__main__":
    load_config()
    main()
