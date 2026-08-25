"""云打印机配置数据模型

每品牌一行：账号参数(config_json)与设备列表(devices_json)以 JSON 存储，
不同品牌的字段差异由 JSON 承载，品牌字段定义见 printer_service 品牌注册表。
"""
from datetime import datetime

from sqlalchemy import Column, String, Text, SmallInteger, DateTime

from mall.db.models.base import BASE, DbBase


class PrinterConfig(BASE, DbBase):
    """云打印机品牌配置表"""
    __tablename__ = 't_mall_printer_config'

    id = Column(String(32), primary_key=True, comment='UUID主键')
    brand = Column(String(32), unique=True, nullable=False, comment='品牌标识: feie/xprinter')
    name = Column(String(32), default='', comment='品牌显示名')
    config_json = Column(Text, default='{}', comment='账号参数JSON: {"user":"","ukey":""}')
    devices_json = Column(Text, default='[]', comment='设备列表JSON: [{"sn":"","key":"","name":"","status":1}]')
    enabled = Column(SmallInteger, default=0, comment='是否启用 1=启用 0=停用')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
