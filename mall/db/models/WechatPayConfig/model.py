"""微信支付配置数据模型 — 独立表"""
from datetime import datetime
from mall.db.models.base import BASE, DbBase
from sqlalchemy import Column, Integer, String, DateTime


class WechatPayConfig(BASE, DbBase):
    """微信支付配置表"""
    __tablename__ = 't_mall_wechat_pay_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(String(128), default='', comment='微信小程序AppID')
    mch_id = Column(String(128), default='', comment='微信商户号')
    mch_key = Column(String(256), default='', comment='API密钥')
    notify_url = Column(String(512), default='', comment='支付回调URL')
    private_key = Column(String(4096), default='', comment='商户API V3私钥(PEM)')
    certificate = Column(String(4096), default='', comment='商户证书(PEM)')
    cert_serial_no = Column(String(128), default='', comment='商户证书序列号(自动提取)')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
