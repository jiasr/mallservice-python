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


def main():
    load_config()
    table_sync()
    init_area()
    init_admin_data()


if __name__ == "__main__":
    main()
