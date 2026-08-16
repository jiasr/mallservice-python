from mall.db.models.base import BASE
from mall.db.models.base import DbBase


from sqlalchemy import Column, DateTime, Integer
from sqlalchemy import String, Text, Float
from sqlalchemy_serializer import SerializerMixin
import uuid
from datetime import datetime

class User(BASE,SerializerMixin):
    __tablename__ = 't_mall_user'
    # id
    id = Column(String(255), primary_key=True,default=uuid.UUID)
    create_time = Column(DateTime,default=datetime.now)
    name = Column(String(255))
    avatar = Column(String(500), default='', comment='头像URL')
    phone = Column(String(20), default='', comment='手机号')
    wx_openid = Column(String(255),index=True)
    wx_unionid = Column(String(255), index=True)
    wx_session_key = Column(String(255))

class UserAddress(BASE,SerializerMixin):
    __tablename__ = 't_mall_user_address'
    # id 以此为键进行
    id = Column(String(255), primary_key=True,default=uuid.UUID) # id
    create_time = Column(DateTime,default=datetime.now) #创建时间
    update_time = Column(DateTime,default=datetime.now, onupdate=datetime.now) #修改时间
    userid =  Column(String(255)) #用户id
    name = Column(String(255)) #收货人姓名
    mobile  = Column(String(20)) #收货人手机号
    province = Column(String(30)) #省
    provincecode =  Column(String(30)) #省
    city = Column(String(30)) #市
    citycode =  Column(String(30)) #市
    district = Column(String(30)) #区县
    districtcode = Column(String(30)) #区县
    detail = Column(String(255)) #详细地址（街道、楼栋、门牌号
    is_defalut = Column(Integer,default=1) #1 是 0 否
    addressTag = Column(String(30))
