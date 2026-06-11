"""系统配置数据模型"""
from datetime import datetime
from mall.db.models.base import BASE, DbBase
from sqlalchemy import Column, Integer, String, Text, DateTime


class SystemConfig(BASE, DbBase):
    """系统配置表 - 以 key-value 形式存储所有系统配置"""
    __tablename__ = 't_mall_system_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(128), unique=True, nullable=False, comment='配置键名')
    config_value = Column(Text, default='', comment='配置值')
    description = Column(String(255), default='', comment='配置说明')
    config_group = Column(String(64), default='general', comment='配置分组 general/upload/storage/access')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
