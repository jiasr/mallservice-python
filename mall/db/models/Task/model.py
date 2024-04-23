from mall.db.models.base import BASE
from mall.db.models.base import DbBase


from sqlalchemy import Column, DateTime, Integer
from sqlalchemy import String, Text, Float
from sqlalchemy_serializer import SerializerMixin
import uuid
import time

class Task(BASE,SerializerMixin):
    __tablename__ = 't_mall_task'
    # id 以此为键进行name翻译
    id = Column(String(255), primary_key=True)
    create_time = Column(DateTime,default=time.localtime(time.time()) )
    name = Column(String(255))