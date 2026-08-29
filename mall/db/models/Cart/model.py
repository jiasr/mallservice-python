"""购物车数据模型"""
from datetime import datetime
from mall.db.models.base import BASE, DbBase
from sqlalchemy import Column, Integer, String, DateTime


class Cart(BASE, DbBase):
    """购物车表"""
    __tablename__ = 't_mall_cart'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, comment='用户ID')
    spu_id = Column(String(255), nullable=False, comment='商品SPU ID')
    sku_id = Column(String(255), nullable=False, comment='商品SKU ID')
    quantity = Column(Integer, default=1, comment='加购数量')
    is_selected = Column(Integer, default=1, comment='是否选中 1是 0否')
    cart_version = Column(Integer, default=0, comment='购物车版本号(乐观锁，用户级单调递增)')
    create_time = Column(DateTime, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
