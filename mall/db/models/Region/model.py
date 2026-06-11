from mall.db.models.base import BASE
from sqlalchemy import Column, String, TIMESTAMP, text
from sqlalchemy_serializer import SerializerMixin


class Region(BASE, SerializerMixin):
    """行政区划表：省/市/区县"""
    __tablename__ = 'regions'

    id = Column(String(100), primary_key=True, comment='主键ID')
    code = Column(String(20), nullable=False, comment='行政区划代码')
    name = Column(String(100), nullable=False, comment='名称')
    parent_code = Column(String(20), comment='父级代码')
    level = Column(String(1), nullable=False, comment='层级：1-省/直辖市，2-市，3-区/县')
    full_name = Column(String(255), comment='完整名称')
    created_at = Column(TIMESTAMP, server_default=text('NOW()'), comment='创建时间')
    updated_at = Column(TIMESTAMP, server_default=text('NOW() ON UPDATE NOW()'), comment='更新时间')
