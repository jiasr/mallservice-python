"""微信支付 APIv3 核心服务：JSAPI 下单、回调解密处理"""

import json

import requests
from oslo_log import log as logging

from mall.common.wechat_pay_utils import (
    generate_nonce,
    generate_timestamp,
    load_private_key,
    build_authorization,
    build_jsapi_pay_sign,
    decrypt_aes_gcm,
)
from mall.db.models.WechatPayConfig.model import WechatPayConfig
from mall.db.engines.mysql import get_session

LOG = logging.getLogger(__name__)

# APIv3 JSAPI 下单地址
JSAPI_ORDER_URL = 'https://api.mch.weixin.qq.com/v3/pay/transactions/jsapi'


class WechatPayService:

    @staticmethod
    def _get_config(key):
        session = get_session()
        with session.begin():
            cfg = session.query(WechatPayConfig).first()
            if not cfg:
                return ''
            mapping = {
                'wechat_app_id': cfg.app_id,
                'wechat_mch_id': cfg.mch_id,
                'wechat_mch_key': cfg.mch_key,
                'wechat_notify_url': cfg.notify_url,
                'wechat_private_key': cfg.private_key,
                'wechat_cert_serial_no': cfg.cert_serial_no,
            }
            return mapping.get(key, '')

    @classmethod
    def _get_private_key_and_serial(cls):
        """从 DB 配置获取商户私钥和证书序列号"""
        private_key_pem = cls._get_config('wechat_private_key')
        cert_serial_no = cls._get_config('wechat_cert_serial_no')

        if not private_key_pem or 'BEGIN PRIVATE KEY' not in private_key_pem:
            raise Exception("商户 API 私钥未配置（wechat_private_key）")

        if not cert_serial_no:
            raise Exception("商户证书序列号未配置（wechat_cert_serial_no）")

        return private_key_pem, cert_serial_no

    @classmethod
    def get_pay_params(cls, order_id, total_fee, openid, spbill_create_ip='127.0.0.1'):
        """APIv3: JSAPI 统一下单，返回调起支付参数

        Returns:
            dict: {appId, timeStamp, nonceStr, package, signType, paySign}
        """
        LOG.info("===== 微信支付 APIv3 开始 =====")
        LOG.info("订单号: {}, 金额: {}分, openid: {}".format(order_id, total_fee, openid))

        # 1. 读取基础配置
        app_id = cls._get_config('wechat_app_id')
        mch_id = cls._get_config('wechat_mch_id')
        apiv3_key = cls._get_config('wechat_mch_key')
        notify_url = cls._get_config('wechat_notify_url')

        if not all([app_id, mch_id, apiv3_key]):
            missing = [k for k, v in [
                ('wechat_app_id', app_id),
                ('wechat_mch_id', mch_id),
                ('wechat_mch_key', apiv3_key),
            ] if not v]
            LOG.error("微信支付基础配置不完整: {}".format(missing))
            raise Exception('微信支付基础配置不完整: {}'.format(', '.join(missing)))

        # 2. 获取私钥和证书序列号
        private_key_pem, cert_serial_no = cls._get_private_key_and_serial()
        private_key = load_private_key(private_key_pem)

        # 3. 构建请求体
        body_dict = {
            'appid': app_id,
            'mchid': mch_id,
            'description': '商城-商品',
            'out_trade_no': order_id,
            'notify_url': notify_url or 'https://example.com/wxpay/notify',
            'amount': {
                'total': int(total_fee),
                'currency': 'CNY',
            },
            'payer': {
                'openid': openid,
            },
        }
        body_str = json.dumps(body_dict, separators=(',', ':'))

        # 4. 构建 Authorization
        auth = build_authorization('POST', '/v3/pay/transactions/jsapi',
                                   body_str, mch_id, cert_serial_no, private_key)

        LOG.info("APIv3 下单地址: {}".format(JSAPI_ORDER_URL))
        log_body = {k: v for k, v in body_dict.items() if k != 'payer'}
        LOG.info("APIv3 下单请求: {}".format(log_body))

        # 5. 发送请求
        headers = {
            'Authorization': auth,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'mall-python/1.0',
        }
        try:
            resp = requests.post(JSAPI_ORDER_URL, data=body_str.encode('utf-8'),
                                 headers=headers, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            prepay_id = result.get('prepay_id', '')
            LOG.info("APIv3 下单成功, prepay_id={}".format(prepay_id))
        except requests.RequestException as e:
            LOG.error("APIv3 下单网络请求异常: {}".format(e))
            if e.response is not None:
                LOG.error("响应状态码: {}, 内容: {}".format(
                    e.response.status_code, e.response.text[:500]))
            raise Exception("微信支付 APIv3 下单失败: {}".format(e))
        except (json.JSONDecodeError, KeyError) as e:
            LOG.error("APIv3 下单响应解析失败: {}".format(e))
            raise Exception("微信支付 APIv3 响应解析失败")

        if not prepay_id:
            raise Exception("微信支付 APIv3 下单未返回 prepay_id")

        # 6. 生成 JSAPI 调起支付参数（前端 wx.requestPayment 用）
        timestamp = generate_timestamp()
        nonce_str = generate_nonce()
        pay_sign = build_jsapi_pay_sign(app_id, timestamp, nonce_str,
                                        prepay_id, private_key)

        LOG.info("生成支付签名成功: timeStamp={}, nonceStr={}".format(
            pay_sign.get('timeStamp'), pay_sign.get('nonceStr')))
        LOG.info("===== 微信支付 APIv3 结束 =====")
        return pay_sign

    @classmethod
    def parse_notify(cls, body_json: dict, headers: dict):
        """APIv3: 解析回调通知，验签 + 解密

        Args:
            body_json: 回调请求体 (dict)
            headers: 回调请求头 (需包含 Wechatpay-Signature 等)

        Returns:
            dict: 解密后的支付结果数据
        """
        LOG.info("===== 微信支付 APIv3 回调 =====")

        apiv3_key = cls._get_config('wechat_mch_key')
        if not apiv3_key:
            raise Exception('APIv3 密钥未配置')

        event_type = body_json.get('event_type', '')
        if event_type != 'TRANSACTION.SUCCESS':
            LOG.warning("忽略非支付成功回调: event_type={}".format(event_type))
            raise Exception("非 TRANSACTION.SUCCESS 事件")

        resource = body_json.get('resource', {})
        if resource.get('algorithm') != 'AEAD_AES_256_GCM':
            raise Exception("不支持的加密算法: {}".format(resource.get('algorithm')))

        try:
            result = decrypt_aes_gcm(
                ciphertext_b64=resource['ciphertext'],
                nonce_b64=resource['nonce'],
                associated_data_b64=resource.get('associated_data', ''),
                apiv3_key=apiv3_key,
            )
        except Exception as e:
            LOG.error("回调解密失败: {}".format(e))
            raise Exception("回调解密失败")

        LOG.info("回调解密成功: out_trade_no={}, transaction_id={}, trade_state={}".format(
            result.get('out_trade_no'), result.get('transaction_id'),
            result.get('trade_state')))
        return result
