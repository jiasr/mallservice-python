"""数据库初始化模块
在 API 启动时自动执行：
1. 删除所有表（保留 regions 数据不受影响）
2. 创建所有表
3. 初始化省市区数据（如果 regions 为空）
4. 初始化管理员/菜单/角色默认数据
"""
import os
import json
import uuid

from oslo_log import log as logging
from mall.db.models.base import BASE
from mall.db.engines.mysql import get_engine, get_session
from mall.db.models.Admin.adminsql import AdminUserDao

# 导入所有模型，确保它们注册到 BASE.metadata
from mall.db.models.User import model as _m_user  # noqa
from mall.db.models.GoodsCatalog import model as _m_catalog  # noqa
from mall.db.models.Goods import model as _m_goods  # noqa
from mall.db.models.Admin import model as _m_admin  # noqa
from mall.db.models.SystemConfig import model as _m_syscfg  # noqa
from mall.db.models.StorageConfig import model as _m_storage  # noqa
from mall.db.models.Region import model as _m_region  # noqa
from mall.db.models.Task import model as _m_task  # noqa

LOG = logging.getLogger(__name__)

# 需要保留的表名（不清空）
_KEEP_TABLES = {'regions','t_mall_goods_catalog'}

# 需要按顺序创建的表（按依赖关系排序，被依赖的在前）
_TABLE_CREATE_ORDER = [
    'regions',
    't_mall_admin_menu',
    't_mall_admin_role',
    't_mall_admin_role_menu',
    't_mall_admin_user',
    't_mall_user',
    't_mall_user_address',
    't_mall_goods_catalog',
    't_mall_goods_spu',
    't_mall_goods_sku',
    't_mall_goods_spec',
    't_mall_system_config',
    't_mall_storage_config',
    't_mall_task',
]


def drop_and_create_tables():
    """删除所有表（保留 regions）并重新创建"""
    engine = get_engine()

    all_tables = set(BASE.metadata.tables.keys())
    tables_to_drop = all_tables - _KEEP_TABLES

    LOG.info("准备删除以下表: {}".format(sorted(tables_to_drop)))
    LOG.info("保留表: {}".format(sorted(_KEEP_TABLES & all_tables)))

    if tables_to_drop:
        drop_list = [BASE.metadata.tables[t] for t in tables_to_drop]
        BASE.metadata.drop_all(engine, tables=drop_list)
        LOG.info("已删除 {} 个表".format(len(tables_to_drop)))

    for table_name in _TABLE_CREATE_ORDER:
        if table_name in BASE.metadata.tables:
            table = BASE.metadata.tables[table_name]
            if table.exists(engine):
                LOG.info("表 {} 已存在，跳过创建".format(table_name))
            else:
                table.create(engine)
                LOG.info("已创建表: {}".format(table_name))

    LOG.info("数据库表初始化完成")


def init_area():
    """初始化省市区数据"""
    session = get_session()
    try:
        with session.begin():
            result = session.execute("SELECT count(*) FROM regions")
            count = result.scalar()
            if count > 0:
                LOG.info("regions 表已有 {} 条数据，跳过初始化".format(count))
                return

            area_file = os.path.join(
                os.path.dirname(__file__), '..', 'cmd', 'area.json'
            )
            area_file = os.path.abspath(area_file)

            if not os.path.exists(area_file):
                LOG.warning("area.json 文件不存在: {}".format(area_file))
                return

            with open(area_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            sql = (
                "INSERT INTO regions(id, code, name, parent_code, level) "
                "VALUES(:id, :code, :name, :parent_code, :level)"
            )
            row_count = 0
            for province in data:
                province_code = province.get("value")
                province_name = province.get("label")

                session.execute(sql, {
                    "id": uuid.uuid4().hex,
                    "code": province_code,
                    "name": province_name,
                    "parent_code": "",
                    "level": 1,
                })
                row_count += 1

                for city in province.get("children", []):
                    city_code = city.get("value")
                    city_name = city.get("label")

                    session.execute(sql, {
                        "id": uuid.uuid4().hex,
                        "code": city_code,
                        "name": city_name,
                        "parent_code": province_code,
                        "level": 2,
                    })
                    row_count += 1

                    for district in city.get("children", []):
                        session.execute(sql, {
                            "id": uuid.uuid4().hex,
                            "code": district.get("value"),
                            "name": district.get("label"),
                            "parent_code": city_code,
                            "level": 3,
                        })
                        row_count += 1

            LOG.info("省市区数据初始化完成，共 {} 条".format(row_count))
    except Exception as e:
        LOG.warning("初始化省市区数据失败: {}".format(e))


def init_admin_data():
    """初始化 Admin 默认数据（菜单、角色、管理员账号）"""
    AdminUserDao.create_default_menus()
    AdminUserDao.create_default_role()
    AdminUserDao.create_default_role_menus()
    AdminUserDao.create_default_admin()
    AdminUserDao._init_system_config()
    AdminUserDao._init_storage_config()
    LOG.info("Admin 默认数据初始化完成")


def init_all():
    """执行所有初始化步骤"""
    LOG.info("========== 开始数据库初始化 ==========")
    drop_and_create_tables()
    init_area()
    init_admin_data()
    LOG.info("========== 数据库初始化完成 ==========")
