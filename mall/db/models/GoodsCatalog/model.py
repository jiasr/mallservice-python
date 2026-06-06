from mall.db.models.base import BASE
from mall.db.models.base import DbBase

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy import String, Text, Float
from sqlalchemy_serializer import SerializerMixin
import uuid
import time
from datetime import datetime


class GoodsCatalog(BASE,DbBase):
    __tablename__ = 't_mall_goodscatalog'

    id = Column(String(255), primary_key=True)
    create_time = Column(DateTime,default=time.localtime(time.time()) )
    name = Column(String(255))
    parentid = Column(String(255),default="0")
    level = Column(Integer, default=0, comment='层级：1一级 2二级 3三级')
    thumbnail = Column(String(500), comment='分类缩略图')
    sort_order = Column(Integer, default=0, comment='排序')
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)