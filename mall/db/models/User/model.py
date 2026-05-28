from mall.db.models.base import BASE
from mall.db.models.base import DbBase


from sqlalchemy import Column, DateTime, Integer
from sqlalchemy import String, Text, Float
from sqlalchemy_serializer import SerializerMixin
import uuid
import time

class User(BASE,SerializerMixin):
    __tablename__ = 't_mall_user'
    # id 以此为键进行name翻译
    id = Column(String(255), primary_key=True,default=uuid.UUID)
    create_time = Column(DateTime,default=time.localtime(time.time()))
    name = Column(String(255))
    wx_openid = Column(String(255),index=True)
    wx_unionid = Column(String(255), index=True)  # 添加 unionid
    wx_session_key = Column(String(255))  # 添加 session_key