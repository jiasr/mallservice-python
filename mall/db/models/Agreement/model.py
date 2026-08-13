"""用户协议与隐私政策模型"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, SmallInteger, DateTime

from mall.db.models.base import BASE, DbBase


class Agreement(BASE, DbBase):
    """用户协议与隐私政策表"""
    __tablename__ = 't_mall_agreement'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    type = Column(String(32), nullable=False, default='agreement', comment='类型: agreement=用户协议 privacy=隐私政策')
    title = Column(String(255), nullable=False, default='', comment='标题')
    content = Column(Text, default='', comment='内容')
    version = Column(String(32), nullable=False, default='1.0', comment='版本号')
    status = Column(SmallInteger, nullable=False, default=1, comment='状态: 1=启用 0=停用')
    create_time = Column(DateTime, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
