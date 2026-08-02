import os
from oslo_config import cfg
import json
from sqlalchemy import create_engine
from mall.db.models.base import BASE
from mall.db.engines.mysql import get_session, get_engine
from mall.db.models.User.model import User, UserAddress
from mall.db.models.GoodsCatalog.model import GoodsCatalog
from mall.db.models.Goods.model import GoodsSpu, GoodsSku, GoodsSpec
from mall.db.models.Admin.model import AdminUser, AdminRole, AdminMenu, AdminRoleMenu
from mall.db.models.SystemConfig.model import SystemConfig
from mall.db.models.StorageConfig.model import StorageConfig
from mall.db.models.Region.model import Region
from mall.db.models.Cart.model import Cart
from mall.db.models.Stock.model import InvGoods, StockInOrder, StockInItem, StockLog
from mall.db.models.Admin.adminsql import AdminUserDao
from oslo_log import log as logging
import uuid

LOG = logging.getLogger(__name__)
CONF_FILE_PATH = os.path.join('../../etc/mall', "mall.conf")
CONF = cfg.CONF


def load_config():
    print(CONF_FILE_PATH)
    CONF(['--config-file', CONF_FILE_PATH], project="mall")
    CONF.log_opt_values(LOG, logging.INFO)


def table_sync():
    tables = [
        BASE.metadata.tables["t_mall_user"],
        BASE.metadata.tables["t_mall_user_address"],
        BASE.metadata.tables["t_mall_goods_catalog"],
        BASE.metadata.tables["t_mall_goods_spu"],
        BASE.metadata.tables["t_mall_goods_sku"],
        BASE.metadata.tables["t_mall_goods_spec"],
        BASE.metadata.tables["t_mall_admin_user"],
        BASE.metadata.tables["t_mall_admin_role"],
        BASE.metadata.tables["t_mall_admin_menu"],
        BASE.metadata.tables["t_mall_admin_role_menu"],
        BASE.metadata.tables["t_mall_system_config"],
        BASE.metadata.tables["t_mall_storage_config"],
        BASE.metadata.tables["t_mall_cart"],
        BASE.metadata.tables["t_mall_order"],
        BASE.metadata.tables["t_mall_order_item"],
        BASE.metadata.tables["t_mall_wechat_pay_config"],
        BASE.metadata.tables["t_mall_freight_template"],
        BASE.metadata.tables["t_mall_freight_region"],
        BASE.metadata.tables["regions"],
        BASE.metadata.tables["t_mall_inv_goods"],
        BASE.metadata.tables["t_mall_stock_in_order"],
        BASE.metadata.tables["t_mall_stock_in_item"],
        BASE.metadata.tables["t_mall_stock_log"],
    ]
    BASE.metadata.create_all(get_engine(), tables=tables, checkfirst=True)


def init_area():
    """初始化省市区数据（如果 regions 表不存在则跳过）"""
    try:
        data = {}
        with open("./area.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
            session = get_session()
            result = session.execute("SELECT * FROM regions limit 1")
            print(result)
            if result.rowcount == 0:
                sql = "insert into regions(id,code, name, parent_code, level) VALUES('{}', '{}', '{}','{}',{}) "
                for provinces in data:
                    plabel = provinces.get("label")
                    pvalue = provinces.get("value")
                    citys = provinces.get("children")
                    psql = sql.format(uuid.uuid4().hex, pvalue, plabel, '', 1)
                    print(psql)
                    session.execute(psql)
                    for city in citys:
                        clabel = city.get("label")
                        cvalue = city.get("value")
                        districts = city.get("children")
                        csql = sql.format(uuid.uuid4().hex, cvalue, clabel, pvalue, 2)
                        print(csql)
                        session.execute(csql)
                        for district in districts:
                            dlabel = district.get("label")
                            dvalue = district.get("value")
                            dsql = sql.format(uuid.uuid4().hex, dvalue, dlabel, cvalue, 3)
                            print(dsql)
                            session.execute(dsql)
                session.commit()
                LOG.info("省市区数据初始化完成")
            else:
                LOG.info("area has been inited")
    except Exception as e:
        LOG.warning("初始化省市区数据失败（regions 表可能不存在）: {}".format(e))


def init_admin_data():
    """初始化 Admin 默认数据（菜单、角色、管理员账号）"""
    AdminUserDao.init_all_default_data()


def auto_migrate():
    """自动迁移：建表 + 加列 + 初始化默认数据（由应用启动时调用，不含 load_config）"""
    table_sync()
    _migrate_wechat_pay_config()
    init_area()
    init_admin_data()


def _migrate_wechat_pay_config():
    """迁移微信支付配置表：补充新增字段（已有表不会自动加列）"""
    engine = get_engine()
    with engine.connect() as conn:
        # mysql-connector-python 下，DDL 语句需要 autocommit
        conn.execution_options(isolation_level="AUTOCOMMIT")
        try:
            conn.execute("SELECT `apiv3_key` FROM `t_mall_wechat_pay_config` LIMIT 1")
        except Exception:
            conn.execute(
                "ALTER TABLE `t_mall_wechat_pay_config` "
                "ADD COLUMN `apiv3_key` VARCHAR(64) DEFAULT '' "
                "COMMENT 'APIv3密钥(32位,解密回调)' AFTER `mch_key`"
            )
            LOG.info("迁移: t_mall_wechat_pay_config 添加 apiv3_key 列")
        # mch_key 改大以容纳 PEM 公钥
        try:
            conn.execute("ALTER TABLE `t_mall_wechat_pay_config` MODIFY `mch_key` TEXT")
            LOG.info("迁移: t_mall_wechat_pay_config mch_key 改为 TEXT")
        except Exception:
            pass


main = auto_migrate


if __name__ == "__main__":
    load_config()
    main()
