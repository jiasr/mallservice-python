"""对象存储配置数据模型 — 独立表，与通用系统配置分离"""
from datetime import datetime
from mall.db.models.base import BASE, DbBase
from sqlalchemy import Column, Integer, String, DateTime


class StorageConfig(BASE, DbBase):
    """对象存储配置表"""
    __tablename__ = 't_mall_storage_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint = Column(String(512), default='http://127.0.0.1:9000', comment='S3 端点地址')
    access_key = Column(String(256), default='', comment='AccessKey ID')
    secret_key = Column(String(256), default='', comment='AccessKey Secret')
    bucket_name = Column(String(128), default='mall-images', comment='Bucket 名称')
    region = Column(String(64), default='us-east-1', comment='地域')
    public_endpoint = Column(String(512), default='http://127.0.0.1:9000', comment='公网访问地址')
    upload_max_size = Column(Integer, default=10, comment='上传文件最大大小（MB）')
    upload_allowed_types = Column(String(512), default='jpg,jpeg,png,gif,webp,bmp', comment='允许上传的文件类型')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
