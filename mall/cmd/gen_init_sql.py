# -*- encoding: utf-8 -*-
"""生成全新库初始化 SQL（init.sql）

本脚本从 ORM metadata 生成建表语句，并写入省市区数据及所有默认初始数据，
产出一个可用于全新部署的一键初始化 SQL 文件。

用法:
    python -m mall.cmd.gen_init_sql

说明:
    这是"一次性初始化"工具，仅用于全新数据库部署。
    已有数据的数据库不应重复执行 init.sql，避免覆盖现有数据。
"""
import hashlib
import io
import json
import os
import uuid

from sqlalchemy.dialects.mysql import dialect as mysql_dialect
from sqlalchemy.schema import CreateTable

# 导入所有模型，确保注册到 BASE.metadata
import mall.db.models.base as _base  # noqa
from mall.db.models.User import model as _m_user  # noqa
from mall.db.models.GoodsCatalog import model as _m_catalog  # noqa
from mall.db.models.Goods import model as _m_goods  # noqa
from mall.db.models.Admin import model as _m_admin  # noqa
from mall.db.models.SystemConfig import model as _m_syscfg  # noqa
from mall.db.models.StorageConfig import model as _m_storage  # noqa
from mall.db.models.Region import model as _m_region  # noqa
from mall.db.models.Task import model as _m_task  # noqa
from mall.db.models.Cart import model as _m_cart  # noqa
from mall.db.models.Order import model as _m_order  # noqa
from mall.db.models.Freight import model as _m_freight  # noqa
from mall.db.models.WechatPayConfig import model as _m_wxpay  # noqa
from mall.db.models.Stock import model as _m_stock  # noqa
from mall.db.models.Agreement import model as _m_agreement  # noqa
from mall.db.models.PrinterConfig import model as _m_printer  # noqa

from mall.db.models.base import BASE

MYSQL_DIALECT = mysql_dialect()
_PASSWORD_SALT = "mall_admin_salt"
_OUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'db', 'migration', 'init.sql'
)
_AREA_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'area.json'
)


def _hash_password(password):
    return hashlib.sha256((password + _PASSWORD_SALT).encode()).hexdigest()


def _gen_create_tables():
    """生成所有表的 CREATE TABLE 语句（含 InnoDB/utf8mb4，时间字段补默认值）"""
    lines = []
    for table_name, table in BASE.metadata.tables.items():
        ddl = str(CreateTable(table).compile(dialect=MYSQL_DIALECT)).strip()
        if ddl.endswith(';'):
            ddl = ddl[:-1].rstrip()

        # 时间字段（create_time/update_time）补默认值：与旧 V1~V15 行为保持一致
        # 避免纯 SQL 插入时该字段为 NULL
        ddl = ddl.replace(
            "\tcreate_time DATETIME,",
            "\tcreate_time DATETIME DEFAULT CURRENT_TIMESTAMP,",
        )
        ddl = ddl.replace(
            "\tupdate_time DATETIME,",
            "\tupdate_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,",
        )
        # 去除 MySQL 5.7 不支持的 CHECK 约束（Boolean 字段自动生成），避免兼容性问题
        # 注意 CHECK 前一行是 PRIMARY KEY (id), 结尾带逗号，需一并删除，否则残留尾逗号
        ddl = ddl.replace(",\n\tCHECK (is_sold_out IN (0, 1))", "")

        # 在末尾加入 ENGINE/CHARSET（去掉空的 COMMENT=''）
        ddl = ddl.rstrip() + " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
        lines.append("-- ==================== {} ====================".format(table_name))
        lines.append(ddl)
        lines.append("")
    return lines


def _gen_area_inserts():
    """生成省市区数据 INSERT 语句（与原 init_area 逻辑一致）"""
    with open(_AREA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rows = []
    for province in data:
        province_code = str(province.get("value"))
        province_name = province.get("label")
        rows.append((uuid.uuid4().hex, province_code, province_name, "", 1))
        for city in province.get("children", []):
            city_code = str(city.get("value"))
            city_name = city.get("label")
            rows.append((uuid.uuid4().hex, city_code, city_name, province_code, 2))
            for district in city.get("children", []):
                district_code = str(district.get("value"))
                district_name = district.get("label")
                rows.append((uuid.uuid4().hex, district_code, district_name, city_code, 3))

    lines = []
    lines.append("-- ==================== 省市区数据 ({} 条) ====================".format(len(rows)))
    lines.append("INSERT INTO `regions` (`id`, `code`, `name`, `parent_code`, `level`) VALUES")
    values = []
    for rid, code, name, pcode, level in rows:
        # 转义单引号
        name_esc = name.replace("'", "''")
        values.append("('{}','{}','{}','{}',{})".format(rid, code, name_esc, pcode, level))
    lines.append(",\n".join(values))
    lines.append(";")
    lines.append("")
    return lines


def _gen_default_data():
    """生成菜单、角色、角色权限、admin账号、系统配置、存储配置、协议、运费模板初始数据"""
    lines = []
    lines.append("-- ==================== 默认初始数据 ====================")

    # 超级管理员角色
    lines.append("-- 默认超级管理员角色")
    lines.append(
        "INSERT INTO `t_mall_admin_role` (`id`,`name`,`description`,`status`) VALUES "
        "(1,'超级管理员','拥有所有权限',1);"
    )
    lines.append("")

    # 默认菜单（与 AdminUserDao.create_default_menus 保持一致）
    lines.append("-- 默认菜单")
    menus = [
        (1, "仪表盘", "/", "Odometer", 0, 1, ""),
        (2, "商品管理", "/goods/list", "Goods", 0, 2, ""),
        (3, "订单管理", "/order/list", "Tickets", 0, 3, ""),
        (4, "团购管理", "/groupon/list", "ShoppingCartFull", 0, 4, ""),
        (5, "用户管理", "/user/list", "User", 0, 5, ""),
        (6, "分销管理", "/agent/list", "Share", 0, 6, ""),
        (7, "优惠券管理", "/coupon/list", "Discount", 0, 7, ""),
        (8, "系统设置", "/setting/base", "Setting", 0, 8, ""),
        (9, "商品列表", "/goods/list", "List", 2, 1, ""),
        (10, "分类管理", "/category/list", "Menu", 2, 2, ""),
        (11, "规格管理", "/goods/spec", "SetUp", 2, 3, ""),
        (12, "配送管理", "/freight/list", "Van", 0, 9, ""),
        (13, "订单列表", "/order/list", "List", 3, 1, ""),
        (14, "退款管理", "/order/refund", "Warning", 3, 2, ""),
        (15, "团购列表", "/groupon/list", "List", 4, 1, ""),
        (16, "添加团购", "/groupon/add", "Plus", 4, 2, "groupon:add"),
        (17, "用户列表", "/user/list", "List", 5, 1, ""),
        (18, "分销员列表", "/agent/list", "List", 6, 1, ""),
        (19, "佣金管理", "/agent/commission", "Money", 6, 2, ""),
        (20, "优惠券列表", "/coupon/list", "List", 7, 1, ""),
        (21, "添加优惠券", "/coupon/add", "Plus", 7, 2, "coupon:add"),
        (22, "基本设置", "/setting/base", "Tools", 8, 1, ""),
        (23, "角色与权限", "/setting/role", "Key", 8, 2, "admin:manage"),
        (24, "存储配置", "/setting/objectsto", "Folder", 8, 3, ""),
        (25, "微信支付", "/setting/wechatpay", "Money", 8, 4, ""),
        (26, "运费模板", "/freight/list", "List", 12, 1, ""),
        (27, "添加模板", "/freight/add", "Plus", 12, 2, "freight:add"),
        (28, "用户协议与隐私", "/setting/agreement", "Document", 8, 5, ""),
        (32, "小票机", "/setting/printer", "Printer", 8, 6, ""),
        (30, "进销存", "/stock/goods/list", "Box", 0, 10, ""),
        (31, "库存商品", "/stock/goods/list", "List", 30, 1, ""),
    ]
    menu_rows = []
    for mid, name, frontpath, icon, parent_id, sort_order, permission in menus:
        menu_rows.append(
            "({},'{}','{}','{}',{},{},'{}',1)".format(
                mid, name, frontpath, icon, parent_id, sort_order, permission
            )
        )
    lines.append(
        "INSERT INTO `t_mall_admin_menu` "
        "(`id`,`name`,`frontpath`,`icon`,`parent_id`,`sort_order`,`permission`,`visible`) VALUES\n"
        + ",\n".join(menu_rows) + ";"
    )
    lines.append("")

    # 角色-菜单关联（超级管理员拥有全部菜单）
    lines.append("-- 超级管理员分配全部菜单权限")
    all_menu_ids = sorted(set(m[0] for m in menus))
    rm_rows = ["(1,{})".format(mid) for mid in all_menu_ids]
    lines.append(
        "INSERT INTO `t_mall_admin_role_menu` (`role_id`,`menu_id`) VALUES\n"
        + ",\n".join(rm_rows) + ";"
    )
    lines.append("")

    # 默认管理员账号 admin/password123（预哈希）
    lines.append("-- 默认管理员账号 admin / password123")
    pwd_hash = _hash_password("password123")
    lines.append(
        "INSERT INTO `t_mall_admin_user` "
        "(`id`,`username`,`password_hash`,`avatar`,`role_id`,`status`) VALUES "
        "(1,'admin','{}','',1,1);".format(pwd_hash)
    )
    lines.append("")

    # 默认系统配置（与 AdminUserDao._init_system_config 一致）
    lines.append("-- 默认系统配置")
    sys_configs = [
        ("site_name", "我的商城", "商城名称", "general"),
        ("logo", "", "商城 Logo URL", "general"),
        ("service_phone", "400-123-4567", "客服电话", "general"),
        ("service_email", "service@example.com", "客服邮箱", "general"),
        ("allow_register", "true", "是否允许注册", "access"),
        ("register_need_audit", "false", "注册是否需要审核", "access"),
        ("enable_distribution", "true", "是否启用分销", "access"),
        # 微信支付配置统一存于 t_mall_config_wechatpay 表，此处不再冗余定义
    ]
    sys_rows = []
    for key, value, desc, group in sys_configs:
        sys_rows.append("('{}','{}','{}','{}')".format(key, value, desc, group))
    lines.append(
        "INSERT INTO `t_mall_config_system` (`config_key`,`config_value`,`description`,`config_group`) VALUES\n"
        + ",\n".join(sys_rows) + ";"
    )
    lines.append("")

    # 默认存储配置
    lines.append("-- 默认对象存储配置")
    lines.append(
        "INSERT INTO `t_mall_storage_config` "
        "(`id`,`endpoint`,`access_key`,`secret_key`,`bucket_name`,`region`,`public_endpoint`) VALUES "
        "(1,'http://82.156.225.136:9000','admin','password123','mall-images1','us-east-1','http://82.156.225.136:9000');"
    )
    lines.append("")

    # 默认运费模板（与 V5 一致）
    lines.append("-- 默认运费模板")
    lines.append(
        "INSERT INTO `t_mall_freight_template` "
        "(`name`,`pricing_type`,`fixed_fee`,`first_unit`,`first_fee`,`continue_unit`,`continue_fee`,`free_threshold`,`is_default`) VALUES "
        "('默认运费模板',1,0,1,1000,1,500,0,1);"
    )
    lines.append("")

    # 用户协议/隐私政策/关于我们（与 V14 一致）
    lines.append("-- 默认用户协议、隐私政策、关于我们")
    lines.append(
        "INSERT INTO `t_mall_agreement` (`type`,`title`,`content`,`version`,`status`) VALUES\n"
        "('agreement','用户协议','欢迎使用本商城，请在使用前仔细阅读本用户协议。','1.0',1),\n"
        "('privacy','隐私政策','我们重视您的隐私保护，会依法收集、使用和保护您的个人信息。','1.0',1),\n"
        "('about','关于我们','关于我们的介绍内容','1.0',1);"
    )
    lines.append("")

    # 无码商品条码流水号（单行计数器，与 V13 一致）
    lines.append("-- 无码商品条码流水号计数器")
    lines.append(
        "INSERT INTO `t_mall_stock_barcode_seq` (`id`,`barcode`,`seq`) VALUES (1,'',0);"
    )
    lines.append("")

    return lines


def main():
    import sys
    database = "MALL"
    for i, arg in enumerate(sys.argv):
        if arg == "--database" and i + 1 < len(sys.argv):
            database = sys.argv[i + 1]

    if database == "MALL":
        out_path = os.path.abspath(_OUT_FILE)
    else:
        out_path = os.path.abspath(
            os.path.join(os.path.dirname(_OUT_FILE), 'init_{}.sql'.format(database))
        )
    buf = io.StringIO()
    buf.write("-- ============================================\n")
    buf.write("-- 商城系统全量初始化 SQL（全新库部署用）\n")
    buf.write("-- 由 mall/cmd/gen_init_sql.py 自动生成，请勿手动修改\n")
    buf.write("-- 仅用于全新数据库，已有数据的库请勿执行\n")
    buf.write("-- 用法: mysql -u root -p < init.sql\n")
    buf.write("-- ============================================\n\n")

    buf.write("CREATE DATABASE IF NOT EXISTS `{}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n".format(database))
    buf.write("USE `{}`;\n".format(database))
    buf.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS = 0;\n\n")

    buf.write("\n".join(_gen_create_tables()))
    buf.write("\n\n")
    buf.write("\n".join(_gen_area_inserts()))
    buf.write("\n")
    buf.write("\n".join(_gen_default_data()))

    buf.write("\nSET FOREIGN_KEY_CHECKS = 1;\n")
    buf.write("-- ============================================\n")
    buf.write("-- 初始化完成\n")
    buf.write("-- ============================================\n")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(buf.getvalue())

    print("已生成 init.sql: {}".format(out_path))


if __name__ == "__main__":
    main()
