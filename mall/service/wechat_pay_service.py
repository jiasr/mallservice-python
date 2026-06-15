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
        session = get_session()
        with session.begin():
            cfg = session.query(SystemConfig).filter(
                SystemConfig.config_key == key
            ).first()
            val = cfg.config_value if cfg else ''
            if val:
                masked = val[:4] + '****' + val[-4:] if len(val) > 8 else '****'
            else:
                masked = '(空)'
            LOG.info("微信配置 [{}] = {}".format(key, masked))
            return val

    @classmethod
    def get_pay_params(cls, order_id, total_fee, openid, spbill_create_ip='127.0.0.1'):
        """获取微信支付参数"""
        LOG.info("===== 微信支付开始 =====")
        LOG.info("订单号: {}, 金额: {}分, openid: {}".format(order_id, total_fee, openid))

        app_id = cls._get_config('wechat_app_id')
        mch_id = cls._get_config('wechat_mch_id')
        mch_key = cls._get_config('wechat_mch_key')
        notify_url = cls._get_config('wechat_notify_url')

        if not all([app_id, mch_id, mch_key]):
            LOG.error("微信支付配置不完整: app_id={}, mch_id={}, mch_key={}".format(
                bool(app_id), bool(mch_id), bool(mch_key)))
            raise Exception('微信支付未配置，请在管理后台填写微信支付参数')

        LOG.info("统一下单地址: {}".format(UNIFIED_ORDER_URL))
        LOG.info("通知回调URL: {}".format(notify_url or '(未设置)'))

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

        # 打印请求参数（隐藏敏感字段）
        log_params = {k: v for k, v in params.items() if k not in ('openid',)}
        LOG.info("统一下单请求参数: {}".format(log_params))

        sign = sign_md5(params, mch_key)
        params['sign'] = sign
        xml_data = dict_to_xml(params)

        try:
            resp = requests.post(UNIFIED_ORDER_URL, data=xml_data.encode('utf-8'),
                                 headers={'Content-Type': 'text/xml'}, timeout=10)
            resp.encoding = 'utf-8'
            result = xml_to_dict(resp.text)
            LOG.info("统一下单响应: return_code={}, result_code={}, prepay_id={}".format(
                result.get('return_code'), result.get('result_code'),
                result.get('prepay_id', '(无)')))
            if result.get('return_code') != 'SUCCESS' or result.get('result_code') != 'SUCCESS':
                LOG.error("统一下单失败: return_msg={}, err_code={}, err_code_des={}".format(
                    result.get('return_msg', ''), result.get('err_code', ''),
                    result.get('err_code_des', '')))
        except requests.RequestException as e:
            LOG.error("统一下单网络请求异常: {}".format(e))
            raise
        except Exception as e:
            LOG.error("统一下单解析响应异常: {}".format(e))
            raise

        if result.get('return_code') != 'SUCCESS':
            raise Exception("微信通信失败: " + result.get('return_msg', ''))
        if result.get('result_code') != 'SUCCESS':
            raise Exception("微信下单失败: " + result.get('err_code_des', ''))

        prepay_id = result['prepay_id']
        LOG.info("获取到 prepay_id: {}".format(prepay_id))

        pay_sign = build_pay_sign(prepay_id, app_id, mch_key)
        LOG.info("生成支付签名成功: timeStamp={}, nonceStr={}".format(
            pay_sign.get('timeStamp'), pay_sign.get('nonceStr')))
        LOG.info("===== 微信支付结束 =====")
        return pay_sign

    @classmethod
    def verify_notify(cls, xml_str):
        """验证微信支付回调签名"""
        LOG.info("===== 微信支付回调 =====")
        LOG.info("原始XML: {}".format(xml_str[:200]))

        mch_key = cls._get_config('wechat_mch_key')
        data = xml_to_dict(xml_str)
        sign = data.pop('sign', '')
        LOG.info("回调数据: out_trade_no={}, transaction_id={}, total_fee={}".format(
            data.get('out_trade_no'), data.get('transaction_id'), data.get('total_fee')))

        computed = sign_md5(data, mch_key)
        if sign != computed:
            LOG.error("签名验证失败: received={}, computed={}".format(sign, computed))
            raise Exception('签名验证失败')

        LOG.info("签名验证通过, 回调处理完成")
        return data
