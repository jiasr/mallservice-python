"""微信支付 APIv3 核心服务：JSAPI 下单、回调解密处理"""

import json

import requests
from oslo_log import log as logging

from mall.common.wechat_pay_utils import (
    generate_nonce,
    generate_timestamp,
    load_private_key,
    load_public_key,
    sign_rsa,
    verify_signature,
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
                'wechat_apiv3_key': cfg.apiv3_key,
                'wechat_notify_url': cfg.notify_url,
                'wechat_private_key': cfg.private_key,
                'wechat_certificate': cfg.certificate,
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
        apiv3_key = cls._get_config('wechat_apiv3_key')
        notify_url = cls._get_config('wechat_notify_url')

        if not all([app_id, mch_id, apiv3_key]):
            missing = [k for k, v in [
                ('wechat_app_id', app_id),
                ('wechat_mch_id', mch_id),
                ('wechat_apiv3_key', apiv3_key),
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
        LOG.info(body_dict)
        body_str = json.dumps(body_dict, separators=(',', ':'))

        # 4. 构建 Authorization
        auth = build_authorization('POST', '/v3/pay/transactions/jsapi',
                                   body_str, mch_id, cert_serial_no, private_key)

        LOG.info(auth)
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
        LOG.info(headers)
        try:
            resp = requests.post(JSAPI_ORDER_URL, data=body_str.encode('utf-8'),
                                 headers=headers, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            prepay_id = result.get('prepay_id', '')
            LOG.info("APIv3 下单成功, prepay_id={}".format(result))
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
    def refund(cls, order_id, transaction_id, refund_amount, total_amount, reason=''):
        """APIv3: 申请退款

        Args:
            order_id: 商户订单号
            transaction_id: 微信支付交易号
            refund_amount: 退款金额(分)
            total_amount: 原订单金额(分)
            reason: 退款原因

        Returns:
            dict: 退款结果
        """
        LOG.info("===== 微信支付 APIv3 退款开始 =====")
        LOG.info("订单号: {}, 交易号: {}, 退款金额: {}分".format(order_id, transaction_id, refund_amount))

        # 1. 读取配置
        mch_id = cls._get_config('wechat_mch_id')
        apiv3_key = cls._get_config('wechat_apiv3_key')
        if not all([mch_id, apiv3_key]):
            raise Exception('微信支付基础配置不完整')

        private_key_pem, cert_serial_no = cls._get_private_key_and_serial()
        private_key = load_private_key(private_key_pem)

        # 2. 构建退款请求
        refund_no = 'RF' + order_id[2:]  # 退款单号: RF + 原订单号去掉前缀
        body_dict = {
            'transaction_id': transaction_id,
            'out_refund_no': refund_no,
            'amount': {
                'refund': int(refund_amount),
                'total': int(total_amount),
                'currency': 'CNY',
            },
        }
        if reason:
            body_dict['reason'] = reason

        body_str = json.dumps(body_dict, separators=(',', ':'))

        # 3. 构建签名
        auth = build_authorization('POST', '/v3/refund/domestic/refunds',
                                   body_str, mch_id, cert_serial_no, private_key)

        REFUND_URL = 'https://api.mch.weixin.qq.com/v3/refund/domestic/refunds'
        headers = {
            'Authorization': auth,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'mall-python/1.0',
        }

        LOG.info("退款请求: order_id={}, refund_no={}, amount={}".format(
            order_id, refund_no, refund_amount))

        try:
            resp = requests.post(REFUND_URL, data=body_str.encode('utf-8'),
                                 headers=headers, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            LOG.info("退款成功: refund_id={}, status={}".format(
                result.get('refund_id'), result.get('status')))
            return result
        except requests.RequestException as e:
            LOG.error("退款请求异常: {}".format(e))
            if e.response is not None:
                LOG.error("响应状态码: {}, 内容: {}".format(
                    e.response.status_code, e.response.text[:500]))
            raise Exception("退款失败: {}".format(e))

    @classmethod
    def query_order(cls, order_id):
        """APIv3: 查询订单支付状态"""
        LOG.info("===== 微信支付查询订单 =====")
        app_id = cls._get_config('wechat_app_id')
        mch_id = cls._get_config('wechat_mch_id')
        if not all([app_id, mch_id]):
            raise Exception('微信支付配置不完整')

        private_key_pem, cert_serial_no = cls._get_private_key_and_serial()
        private_key = load_private_key(private_key_pem)

        url_path = '/v3/pay/transactions/out-trade-no/{}?mchid={}'.format(order_id, mch_id)
        message = 'GET\n{}\n{}\n'.format(url_path, generate_timestamp()) + generate_nonce() + '\n\n'
        # 简化：直接用 build_authorization 模式
        url = 'https://api.mch.weixin.qq.com{}'.format(url_path)
        nonce_str = generate_nonce()
        timestamp = generate_timestamp()
        message = 'GET\n{}\n{}\n{}\n\n'.format(url_path, timestamp, nonce_str)
        signature = sign_rsa(message, private_key)
        auth = 'WECHATPAY2-SHA256-RSA2048 mchid="{}",nonce_str="{}",signature="{}",timestamp="{}",serial_no="{}"'.format(
            mch_id, nonce_str, signature, timestamp, cert_serial_no)

        headers = {
            'Authorization': auth,
            'Accept': 'application/json',
            'User-Agent': 'mall-python/1.0',
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            LOG.info("查询订单 {}: trade_state={}".format(order_id, result.get('trade_state')))
            return result
        except requests.RequestException as e:
            LOG.error("查询订单异常: {}".format(e))
            if e.response is not None:
                LOG.error("响应: {} {}".format(e.response.status_code, e.response.text[:500]))
            raise Exception("查询订单失败")

    @classmethod
    def parse_notify(cls, body_json: dict, headers: dict, raw_body: str = ''):
        """APIv3: 解析回调通知，验签 + 解密

        Args:
            body_json: 回调请求体 (dict)
            headers: 回调请求头
            raw_body: 原始请求体字符串（用于验签）

        Returns:
            dict: 解密后的支付结果数据
        """
        LOG.info("===== 微信支付 APIv3 回调 =====")
        LOG.info(body_json)

        # 1. 验签（用 mch_key 验证 Wechatpay-Signature）
        mch_key = cls._get_config('wechat_mch_key')
        if mch_key and raw_body:
            signature_b64 = headers.get('Wechatpay-Signature', '')
            timestamp = headers.get('Wechatpay-Timestamp', '')
            nonce = headers.get('Wechatpay-Nonce', '')
            if all([signature_b64, timestamp, nonce]):
                try:
                    public_key = load_public_key(mch_key)
                    message = "{}\n{}\n{}\n".format(timestamp, nonce, raw_body)
                    if verify_signature(message, signature_b64, public_key):
                        LOG.info("回调验签通过")
                    else:
                        raise Exception("签名验证失败")
                except Exception as e:
                    LOG.error("回调验签失败: {}".format(e))
                    raise Exception("回调验签失败")
            else:
                LOG.warning("回调缺少验签头，跳过验签")
        else:
            LOG.warning("mch_key 未配置或缺少原始请求体，跳过验签")

        # 2. 解密
        apiv3_key = cls._get_config('wechat_apiv3_key')
        if not apiv3_key:
            raise Exception('APIv3 密钥未配置')

        event_type = body_json.get('event_type', '')
        LOG.info("收到微信回调: event_type={}".format(event_type))

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
