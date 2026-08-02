"""库存相关数据模型：入库单、入库明细、库存流水"""
from datetime import datetime

from sqlalchemy import Column, Integer, SmallInteger, String, DateTime

from mall.db.models.base import BASE, DbBase


class StockInOrder(BASE, DbBase):
    """入库单主表"""
    __tablename__ = 't_mall_stock_in_order'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    order_no = Column(String(64), nullable=False, default='', comment='入库单号')
    type = Column(SmallInteger, default=1, comment='入库类型: 1=采购入库 2=退货入库 3=调拨入库 4=盘盈入库')
    total_quantity = Column(Integer, default=0, comment='入库总数量')
    status = Column(SmallInteger, default=0, comment='状态: 0=草稿 1=已提交 2=已取消')
    operator_id = Column(Integer, default=0, comment='操作人ID')
    operator_name = Column(String(100), default='', comment='操作人姓名')
    remark = Column(String(500), default='', comment='备注')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class StockInItem(BASE, DbBase):
    """入库明细表"""
    __tablename__ = 't_mall_stock_in_item'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    order_id = Column(Integer, nullable=False, comment='关联入库单ID')
    sku_id = Column(String(255), nullable=False, comment='SKU ID')
    spu_id = Column(String(255), nullable=False, comment='SPU ID')
    quantity = Column(Integer, default=0, comment='入库数量')
    batch_no = Column(String(64), default='', comment='批次号')
    remark = Column(String(500), default='', comment='备注')
    create_time = Column(DateTime, default=datetime.now)


class StockLog(BASE, DbBase):
    """库存流水表"""
    __tablename__ = 't_mall_stock_log'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    sku_id = Column(String(255), nullable=False, comment='SKU ID')
    spu_id = Column(String(255), nullable=False, comment='SPU ID')
    change_qty = Column(Integer, nullable=False, comment='变动数量')
    balance_after = Column(Integer, default=0, comment='变动后结存数量')
    biz_type = Column(String(32), nullable=False, comment='业务类型: stock_in/stock_out/stock_check')
    biz_no = Column(String(64), default='', comment='业务单号')
    operator_id = Column(Integer, default=0, comment='操作人ID')
    operator_name = Column(String(100), default='', comment='操作人姓名')
    remark = Column(String(500), default='', comment='备注')
    create_time = Column(DateTime, default=datetime.now)
