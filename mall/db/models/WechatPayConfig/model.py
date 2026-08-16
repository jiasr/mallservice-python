"""微信支付配置数据模型 — 独立表"""
from datetime import datetime
from mall.db.models.base import BASE, DbBase
from sqlalchemy import Column, Integer, String, Text, DateTime


class WechatPayConfig(BASE, DbBase):
    """微信支付配置表"""
    __tablename__ = 't_mall_config_wechatpay'

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(String(128), default='', comment='微信小程序AppID')
    mch_id = Column(String(128), default='', comment='微信商户号')
    mch_key = Column(Text, default='', comment='APIv2密钥/微信支付公钥(PEM)')
    apiv3_key = Column(String(64), default='', comment='APIv3密钥(32位,解密回调)')
    notify_url = Column(String(512), default='', comment='支付回调URL')
    private_key = Column(String(4096), default='', comment='商户API V3私钥(PEM)')
    certificate = Column(String(4096), default='', comment='商户证书(PEM)')
    cert_serial_no = Column(String(128), default='', comment='商户证书序列号(自动提取)')
    wechatpay_public_key = Column(String(4096), default='', comment='微信支付公钥(PEM)')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
