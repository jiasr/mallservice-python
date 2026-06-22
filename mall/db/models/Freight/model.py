"""运费数据模型"""
from datetime import datetime
from mall.db.models.base import BASE, DbBase
from sqlalchemy import Column, Integer, String, DateTime, Index


class FreightTemplate(BASE, DbBase):
    """运费模板表"""
    __tablename__ = 't_mall_freight_template'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment='模板名称')
    pricing_type = Column(Integer, default=1, comment='计费方式 0=固定运费 1=按件')
    fixed_fee = Column(Integer, default=0, comment='固定运费金额(分)')
    first_unit = Column(Integer, default=1, comment='首件数量')
    first_fee = Column(Integer, default=0, comment='首件费用(分)')
    continue_unit = Column(Integer, default=1, comment='续件数量')
    continue_fee = Column(Integer, default=0, comment='续件费用(分)')
    free_threshold = Column(Integer, default=0, comment='满额包邮门槛(分)，0=不启用')
    is_default = Column(Integer, default=0, comment='是否默认模板 1=是 0=否')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class FreightRegion(BASE, DbBase):
    """运费地区规则表"""
    __tablename__ = 't_mall_freight_region'

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, nullable=False, comment='关联模板ID')
    region_code = Column(String(20), nullable=False, comment='省份编码')
    region_name = Column(String(50), nullable=False, comment='省份名称')
    is_free = Column(Integer, default=0, comment='是否包邮 1=是 0=按规则')
    fixed_fee = Column(Integer, nullable=True, comment='该地区固定运费(分)，覆盖模板值')
    first_fee = Column(Integer, nullable=True, comment='该地区首费(分)，覆盖模板值')
    continue_fee = Column(Integer, nullable=True, comment='该地区续费(分)，覆盖模板值')
    free_threshold = Column(Integer, nullable=True, comment='该地区包邮门槛(分)，覆盖模板值')

    __table_args__ = (
        Index('idx_fr_template', 'template_id'),
        Index('idx_fr_region', 'region_code'),
    )
