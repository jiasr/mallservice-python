"""微信支付核心服务：统一下单、签名、回调验证"""
import requests
from oslo_log import log as logging

from mall.common.wechat_pay_utils import (
    generate_nonce, dict_to_xml, xml_to_dict, build_pay_sign, sign_md5
)
from mall.db.models.SystemConfig.model import SystemConfig
from mall.db.engines.mysql import get_session

LOG = logging.getLogger(__name__)

UNIFIED_ORDER_URL = 'https://api.mch.weixin.qq.com/sandboxnew/pay/unifiedorder'
# 正式环境: 'https://api.mch.weixin.qq.com/pay/unifiedorder'


class WechatPayService:

    @staticmethod
    def _get_config(key):
        """从 DB 读取微信支付配置"""
        session = get_session()
        with session.begin():
            cfg = session.query(SystemConfig).filter(
                SystemConfig.config_key == key
            ).first()
            return cfg.config_value if cfg else ''

    @classmethod
    def get_pay_params(cls, order_id, total_fee, openid, spbill_create_ip='127.0.0.1'):
        """获取微信支付参数

        Args:
            order_id: 订单号
            total_fee: 支付金额（分）
            openid: 用户微信 OpenID
            spbill_create_ip: 终端 IP

        Returns:
            dict: { timeStamp, nonceStr, package, signType, paySign }
        """
        app_id = cls._get_config('wechat_app_id')
        mch_id = cls._get_config('wechat_mch_id')
        mch_key = cls._get_config('wechat_mch_key')
        notify_url = cls._get_config('wechat_notify_url')

        if not all([app_id, mch_id, mch_key]):
            raise Exception('微信支付未配置，请在管理后台填写微信支付参数')

        params = {
            'appid':            app_id,
            'mch_id':           mch_id,
            'nonce_str':        generate_nonce(),
            'body':             '商城-商品',
            'out_trade_no':     order_id,
            'total_fee':        str(int(total_fee)),
            'spbill_create_ip': spbill_create_ip,
            'notify_url':       notify_url or 'https://example.com/wxpay/notify',
            'trade_type':       'JSAPI',
            'openid':           openid,
        }
        # 签名
        sign = sign_md5(params, mch_key)
        params['sign'] = sign
        xml_data = dict_to_xml(params)

        LOG.info("微信统一下单请求: {}".format(xml_data))
        resp = requests.post(UNIFIED_ORDER_URL, data=xml_data.encode('utf-8'),
                             headers={'Content-Type': 'text/xml'}, timeout=10)
        resp.encoding = 'utf-8'
        result = xml_to_dict(resp.text)
        LOG.info("微信统一下单响应: {}".format(result))

        if result.get('return_code') != 'SUCCESS':
            raise Exception("微信通信失败: " + result.get('return_msg', ''))
        if result.get('result_code') != 'SUCCESS':
            raise Exception("微信下单失败: " + result.get('err_code_des', ''))

        prepay_id = result['prepay_id']
        return build_pay_sign(prepay_id, app_id, mch_key)

    @classmethod
    def verify_notify(cls, xml_str):
        """验证微信支付回调签名

        Args:
            xml_str: 微信回调 XML

        Returns:
            dict: 解析后的回调数据
        """
        mch_key = cls._get_config('wechat_mch_key')
        data = xml_to_dict(xml_str)
        sign = data.pop('sign', '')
        computed = sign_md5(data, mch_key)
        if sign != computed:
            raise Exception('签名验证失败')
        return data
