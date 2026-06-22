"""订单数据模型"""
from datetime import datetime
from mall.db.models.base import BASE, DbBase
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index


class Order(BASE, DbBase):
    """订单主表"""
    __tablename__ = 't_mall_order'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), nullable=False, unique=True, comment='订单号')
    user_id = Column(String(255), nullable=False, comment='用户ID')
    total_amount = Column(Integer, default=0, comment='商品总金额(分)')
    discount_amount = Column(Integer, default=0, comment='优惠金额(分)')
    freight_amount = Column(Integer, default=0, comment='运费(分)')
    pay_amount = Column(Integer, default=0, comment='实付金额(分)')
    pay_status = Column(Integer, default=0, comment='支付状态 0未支付 1已支付 2已退款')
    order_status = Column(Integer, default=0, comment='订单状态 0待付款 1已付款 2已发货 3已完成 4已取消')
    consignee_name = Column(String(100), nullable=False, comment='收货人姓名')
    consignee_mobile = Column(String(20), nullable=False, comment='收货人手机号')
    consignee_address = Column(String(500), nullable=False, comment='收货地址')
    remark = Column(String(500), default='', comment='买家留言')
    payment_method = Column(String(32), default='', comment='支付方式')
    paid_at = Column(DateTime, comment='支付时间')
    shipping_company = Column(String(100), default='', comment='物流公司')
    shipping_no = Column(String(100), default='', comment='物流单号')
    delivery_type = Column(Integer, default=0, comment='配送方式 0=快递 1=同城配送 2=自提')
    pickup_store_id = Column(Integer, default=0, comment='自提门店ID')
    pickup_store_name = Column(String(100), default='', comment='自提门店名称')
    pickup_code = Column(String(10), default='', comment='自提核销码')
    pickup_expire_time = Column(DateTime, comment='自提截止时间')
    local_delivery_time = Column(String(50), default='', comment='同城配送时段')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class OrderItem(BASE, DbBase):
    """订单商品明细表"""
    __tablename__ = 't_mall_order_item'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), ForeignKey('t_mall_order.order_id'), nullable=False, comment='订单号')
    spu_id = Column(String(255), nullable=False, comment='商品SPU ID')
    sku_id = Column(String(255), nullable=False, comment='商品SKU ID')
    title = Column(String(500), nullable=False, comment='商品标题')
    thumb = Column(String(500), default='', comment='商品图片')
    spec_label = Column(String(200), default='', comment='规格描述')
    price = Column(Integer, default=0, comment='成交价(分)')
    quantity = Column(Integer, default=1, comment='购买数量')
    subtotal = Column(Integer, default=0, comment='小计(分)')
    create_time = Column(DateTime, default=datetime.now)
