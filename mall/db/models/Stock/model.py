"""进销存库存数据模型：独立库存商品、入库单、入库明细、库存流水"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, SmallInteger, Numeric, Text

from mall.db.models.base import BASE, DbBase


class InvGoods(BASE, DbBase):
    """进销存独立库存商品表（完全独立于商城SKU）"""
    __tablename__ = 't_mall_stock_goods'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    barcode = Column(String(64), nullable=False, default='', comment='商品条码')
    name = Column(String(200), nullable=False, default='', comment='商品名称')
    brand = Column(String(100), default='', comment='品牌')
    spec = Column(String(100), default='', comment='规格')
    unit = Column(String(20), default='', comment='单位')
    category = Column(String(100), default='', comment='分类')
    cost_price = Column(Numeric(10, 2), default=0, comment='成本价')
    sale_price = Column(Numeric(10, 2), default=0, comment='参考售价')
    stock_quantity = Column(Integer, default=0, comment='当前库存')
    warn_threshold = Column(Integer, default=0, comment='库存预警阈值')
    supplier = Column(String(200), default='', comment='供应商')
    shelf_life_days = Column(Integer, default=0, comment='保质期天数')
    image_url = Column(String(500), default='', comment='商品图片')
    remark = Column(String(500), default='', comment='备注')
    text = Column(Text, default='', comment='从商品库请求到的原始数据(JSON)')
    status = Column(SmallInteger, default=1, comment='状态: 1=启用 0=停用')
    is_auto_barcode = Column(SmallInteger, default=0, comment='条码来源: 0=手动/已有条码 1=无码商品自动生成')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class BarcodeSeq(BASE, DbBase):
    """无码商品条码流水号表（单行计数器）：记录当前条码流水号，从1开始"""
    __tablename__ = 't_mall_stock_barcode_seq'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键，固定为1（单行计数器）')
    barcode = Column(String(64), nullable=False, default='', comment='最近生成的条码')
    seq = Column(Integer, nullable=False, default=0, comment='当前条码流水号（从1开始）')
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class StockInOrder(BASE, DbBase):
    """入库单主表"""
    __tablename__ = 't_mall_stock_in_order'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    order_no = Column(String(64), nullable=False, default='', comment='入库单号')
    type = Column(SmallInteger, default=1, comment='入库类型: 1=采购入库 2=退货入库 3=调拨入库 4=盘盈入库')
    total_quantity = Column(Integer, default=0, comment='入库总数量')
    total_amount = Column(Numeric(10, 2), default=0, comment='入库总金额')
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
    goods_id = Column(Integer, nullable=False, default=0, comment='关联t_mall_stock_goods.id')
    quantity = Column(Integer, default=0, comment='入库数量')
    cost_price = Column(Numeric(10, 2), default=0, comment='入库成本价')
    batch_no = Column(String(64), default='', comment='批次号')
    remark = Column(String(500), default='', comment='备注')
    create_time = Column(DateTime, default=datetime.now)


class StockLog(BASE, DbBase):
    """库存流水表"""
    __tablename__ = 't_mall_stock_log'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    goods_id = Column(Integer, nullable=False, default=0, comment='关联t_mall_stock_goods.id')
    change_qty = Column(Integer, nullable=False, comment='变动数量')
    balance_after = Column(Integer, default=0, comment='变动后结存数量')
    biz_type = Column(String(32), nullable=False, comment='业务类型: stock_in/stock_out/stock_check')
    biz_no = Column(String(64), default='', comment='业务单号')
    operator_id = Column(Integer, default=0, comment='操作人ID')
    operator_name = Column(String(100), default='', comment='操作人姓名')
    remark = Column(String(500), default='', comment='备注')
    create_time = Column(DateTime, default=datetime.now)
