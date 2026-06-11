"""商品相关数据模型：SPU、SKU、规格、分类、评价、搜索历史"""
from datetime import datetime
from mall.db.models.base import BASE, DbBase
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime,
    ForeignKey, Boolean, Integer
)
from sqlalchemy.orm import relationship
from sqlalchemy_serializer import SerializerMixin
import uuid



class GoodsSpu(BASE, SerializerMixin):
    """商品SPU表"""
    __tablename__ = 't_mall_goods_spu'

    id = Column(String(255), primary_key=True,index=True,) # id
    spu_id = Column(String(255), nullable=False, default='', comment='SPU唯一标识')
    title = Column(String(500), nullable=False, comment='商品标题')
    etitle = Column(String(500), default='', comment='英文标题')

    category_id = Column(String(255), comment='分类ID')
    is_put_on_sale = Column(Integer, default=1, comment='是否上架 1是 0否')
    is_available = Column(Integer, default=1, comment='是否可用 1是 0否')


    primary_image = Column(String(500), comment='主图')
    images = Column(Text, comment='轮播图(JSON数组)')
    desc = Column(Text, comment='详情图(JSON数组)')
    video = Column(String(500), comment='视频地址')


    sold_num = Column(Integer, default=0, comment='已售数量')
    is_sold_out = Column(Boolean, default=False, comment='是否售罄')
    tags = Column(String(500), comment='标签(JSON数组)')

    store_id = Column(String(64), default='1000', comment='店铺ID')

    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    min_sale_price = Column(Integer, default=0, comment='最低售价(分)')
    max_sale_price = Column(Integer, default=0, comment='最高售价(分)')
    min_line_price = Column(Integer, default=0, comment='最低划线价(分)')
    max_line_price = Column(Integer, default=0, comment='最高划线价(分)')
    stock_quantity = Column(Integer, default=0, comment='总库存')


class GoodsSku(BASE, SerializerMixin):
    """商品SKU表"""
    __tablename__ = 't_mall_goods_sku'

    id =Column(String(255), primary_key=True) # id
    sku_id = Column(String(255), nullable=False, default='', comment='SKU唯一标识')
    spu_id = Column(String(255), ForeignKey('t_mall_goods_spu.id'), comment='关联SPU')
    sku_image = Column(String(500), comment='SKU图片')
    price = Column(Integer, default=0, comment='销售价格(分)')
    line_price = Column(Integer, default=0, comment='划线价格(分)')
    stock_quantity = Column(Integer, default=0, comment='库存数量')
    sold_quantity = Column(Integer, default=0, comment='已售数量')
    spec_info = Column(Text, comment='规格信息(JSON数组)')
    weight_value = Column(Float, comment='重量')
    weight_unit = Column(String(10), default='KG', comment='重量单位')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class GoodsSpec(BASE, SerializerMixin):
    """商品规格定义表"""
    __tablename__ = 't_mall_goods_spec'

    id = Column(String(255), primary_key=True) # id
    spec_id = Column(String(255), nullable=False, default='', comment='规格唯一标识')
    spu_id = Column(String(255), comment='关联SPU')
    title = Column(String(100), nullable=False, comment='规格名称(如颜色、尺码)')
    spec_values = Column(Text, comment='规格值列表(JSON数组)')
    create_time = Column(DateTime, default=datetime.now)