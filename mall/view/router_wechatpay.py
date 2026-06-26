"""微信支付配置 API 路由"""
import json
from io import StringIO
from flask import Blueprint, request
from flask_restx import Namespace, Resource
from oslo_log import log as logging
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from mall.common.common import admin_required, deco_catch_view_exception
from mall.db.engines.mysql import get_session
from mall.db.models.WechatPayConfig.model import WechatPayConfig

LOG = logging.getLogger(__name__)

app_wechatpay = Blueprint('wechatpay', __name__)
ns_wechatpay = Namespace("wechatpay", description="微信支付配置", path="/v1/admin")


def _extract_serial_from_pem(pem_str):
    """从 PEM 格式证书内容中提取序列号"""
    try:
        cert = x509.load_pem_x509_certificate(pem_str.encode('utf-8'), default_backend())
        serial = format(cert.serial_number, 'X')
        return serial
    except Exception as e:
        LOG.warning("提取证书序列号失败: {}".format(e))
        return None


@ns_wechatpay.route('/wechatpay/get', methods=['POST', 'GET'])
class WechatPayGet(Resource):
    """获取微信支付配置"""

    @admin_required
    @deco_catch_view_exception("获取微信支付配置")
    def post(self):
        session = get_session()
        with session.begin():
            cfg = session.query(WechatPayConfig).first()
            if not cfg:
                return {
                    'app_id': '', 'mch_id': '',
                    'mch_key': '', 'notify_url': '',
                    'wechat_private_key': '',
                    'wechat_certificate': '',
                    'wechat_cert_serial_no': '',
                }
            return {
                'app_id': cfg.app_id or '',
                'mch_id': cfg.mch_id or '',
                'mch_key': cfg.mch_key or '',
                'notify_url': cfg.notify_url or '',
                'wechat_private_key': cfg.private_key or '',
                'wechat_certificate': cfg.certificate or '',
                'wechat_cert_serial_no': cfg.cert_serial_no or '',
            }

    def get(self):
        return self.post()


@ns_wechatpay.route('/wechatpay/save', methods=['POST'])
class WechatPaySave(Resource):
    """保存微信支付配置"""

    @admin_required
    @deco_catch_view_exception("保存微信支付配置")
    def post(self):
        data = json.loads(request.data)
        session = get_session()
        with session.begin():
            cfg = session.query(WechatPayConfig).first()
            if not cfg:
                cfg = WechatPayConfig()
                session.add(cfg)

            if 'app_id' in data:
                cfg.app_id = data['app_id']
            if 'mch_id' in data:
                cfg.mch_id = data['mch_id']
            if 'mch_key' in data:
                cfg.mch_key = data['mch_key']
            if 'notify_url' in data:
                cfg.notify_url = data['notify_url']
            if 'wechat_private_key' in data:
                cfg.private_key = data['wechat_private_key']

            # 如果上传了证书，自动提取序列号
            if 'wechat_certificate' in data:
                cfg.certificate = data['wechat_certificate']
                serial = _extract_serial_from_pem(data['wechat_certificate'])
                if serial:
                    cfg.cert_serial_no = serial
                    LOG.info("从证书自动提取序列号: {}".format(serial))

        return {'success': True}
