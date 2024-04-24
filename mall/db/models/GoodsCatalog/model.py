from mall.db.models.base import BASE
from mall.db.models.base import DbBase

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy import String, Text, Float
from sqlalchemy_serializer import SerializerMixin
import uuid
import time

class GoodsCatalog(BASE,SerializerMixin):
    __tablename__ = 't_mall_goodscatalog'

    id = Column(String(255), primary_key=True)
    create_time = Column(DateTime,default=time.localtime(time.time()) )
    name = Column(String(255))
    parentid = Column(String(255),default="0")