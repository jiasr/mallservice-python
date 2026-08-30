"""扫码备货记录数据模型

PDA 扫码备货：确认备货完成时记录一行（订单号、操作人、时间），
用于防同单重复备货、以及后续备货记录查询。
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from mall.db.models.base import BASE, DbBase


class PickRecord(BASE, DbBase):
    """备货记录表"""
    __tablename__ = 't_mall_pick_record'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    order_no = Column(String(64), nullable=False, default='', comment='订单号')
    item_count = Column(Integer, default=0, comment='商品种类数')
    total_quantity = Column(Integer, default=0, comment='备货总数量')
    operator_id = Column(Integer, default=0, comment='操作人ID')
    operator_name = Column(String(100), default='', comment='操作人姓名')
    remark = Column(String(500), default='', comment='备注')
    create_time = Column(DateTime, default=datetime.now)
