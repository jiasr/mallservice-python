"""快递公司账号绑定数据模型"""
from datetime import datetime
from mall.db.models.base import BASE, DbBase
from sqlalchemy import Column, String, DateTime, Integer


class DeliveryAccount(BASE, DbBase):
    """快递公司账号绑定表

    支持多渠道:
    - wechat(微信物流助手): 使用 delivery_id + biz_id + password
    - zto(中通开放平台): 使用 app_key + app_secret(加密) + partner_code + env

    新建表，主键遵循《开发规范汇总》一.1 使用 UUID（VARCHAR(32)，uuid4().hex）。
    """
    __tablename__ = 't_mall_delivery_account'

    id = Column(String(32), primary_key=True, comment='主键 UUID（uuid4().hex，符合规范一.1）')
    delivery_id = Column(String(32), nullable=False, default='', comment='快递公司ID（微信物流助手，如 YTO, STO）')
    biz_id = Column(String(32), nullable=False, default='', comment='快递公司客户编码（微信）')
    account_name = Column(String(64), default='', comment='账号名称(别名)')
    password = Column(String(255), default='', comment='密码(微信,加密存储，AES后Base64)')
    status = Column(Integer, default=1, comment='状态 1启用 0禁用')
    # ---- 多渠道扩展 ----
    provider = Column(String(16), nullable=False, default='wechat',
                     comment='渠道 wechat=微信物流助手 zto=中通开放平台')
    app_key = Column(String(128), default='', comment='中通开放平台 appKey')
    app_secret = Column(String(512), default='', comment='中通开放平台 appSecret(AES-GCM 加密存储)')
    partner_code = Column(String(64), default='', comment='中通电子面单账号(如 D36_360320735712101)')
    customer_id = Column(String(64), default='', comment='中通客户编码(对应 accountInfo.customerId)')
    partner_key = Column(String(512), default='', comment='中通电子面单密码(对应 accountInfo.accountPassword, AES-GCM 加密存储)')
    partner_type = Column(String(16), default='1', comment='中通电子面单类型(partnerType, 默认 1)')
    env = Column(String(16), default='sandbox', comment='中通环境 sandbox/prod')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
