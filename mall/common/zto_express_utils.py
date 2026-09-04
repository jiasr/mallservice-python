"""中通开放平台(ZOP) API 客户端封装

接口文档: 中通开放平台 -> 寄件服务 -> zto.open.createOrder
特点(与微信物流助手不同):
- 每个接口是独立 HTTPS 地址: {gateway}/{method}
- 签名: x-dataDigest = base64( md5( 请求体JSON字符串 + appSecret ) )
- Headers: x-appKey(应用Key), x-datadigest(签名, 全小写)
- body 为业务参数 JSON 字符串(不是包在 data 字段里)
- 授权模式下, 电子面单账号(partnerCode)需提前在控制台绑定到 appKey,
  下单时传 partnerCode 即可, 通常不需要 partnerKey 密码。

注意: 本文件属于 service 层工具, 禁止加 deco_catch_view_exception(规范一.5),
异常向上抛由 router 层捕获。
"""
import json
import logging
import hashlib
import base64

import requests

LOG = logging.getLogger(__name__)

# 沙箱(测试)网关 / 生产网关(生产地址以你控制台"接口调试"页为准)
SANDBOX_GATEWAY = "https://japi-test.zto.com"
PROD_GATEWAY = "https://japi.zto.com"  # TODO: 上线前由控制台确认


class ZtoClient:
    """中通开放平台客户端"""

    def __init__(self, app_key, app_secret, gateway=SANDBOX_GATEWAY):
        self.app_key = app_key
        self.app_secret = app_secret
        self.gateway = gateway

    def _sign(self, body_str):
        """x-dataDigest = base64( md5( body + appSecret ) )"""
        raw = body_str + self.app_secret
        md5_digest = hashlib.md5(raw.encode("utf-8")).digest()
        return base64.b64encode(md5_digest).decode("utf-8")

    def _call(self, method, data):
        """统一请求: 返回解析后的 dict(解析失败返回 {raw: 原文})"""
        url = "{}/{}".format(self.gateway, method)
        # 与官方签名文档一致: 用无空格分隔符序列化(示例 body 为 {"pageNo1":33,...} 无空格),
        # 否则网关验签通过但下游下单服务以无空格规范串二次验签会失败 -> S202
        body_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        headers = {
            "x-appKey": self.app_key,
            "x-datadigest": self._sign(body_str),
            "Content-Type": "application/json;charset=utf-8",
        }
        LOG.info("ZTO req method=%s headers=%s body=%s", method, headers, body_str)
        resp = requests.post(
            url, data=body_str.encode("utf-8"), headers=headers, timeout=15
        )
        text = resp.text
        LOG.info("ZTO resp status=%s text=%s", resp.status_code, text)
        try:
            return resp.json()
        except Exception:
            return {"raw": text, "status_code": resp.status_code}

    # ---------- 寄件服务 ----------
    def create_order(self, order_data):
        """创建订单(电子面单) zto.open.createOrder

        order_data 业务参数示例:
        {
          "partnerCode": "D36_360320735712101",  # 电子面单账号(已绑定appKey)
          "type": 1,
          "tradeId": "商户唯一订单号",
          "sender": {"name","mobile","prov","city","county","address"},
          "receiver": {"name","mobile","prov","city","county","address"},
          "items": [{"name","quantity","weight"}],
          "weight": 1
        }
        """
        return self._call("zto.open.createOrder", order_data)

    def cancel_order(self, order_data):
        """取消订单 zto.open.cancelPreOrder"""
        return self._call("zto.open.cancelPreOrder", order_data)

    def track_query(self, order_data):
        """物流轨迹查询 zto.merchant.waybill.track.query"""
        return self._call("zto.merchant.waybill.track.query", order_data)

    def print_waybill(self, order_data):
        """请求生成面单图片/PDF zto.open.order.print

        常用业务参数: {partnerCode, waybillNo} 或 {partnerCode, tradeId}
        返回含面单图片(URL 或 Base64)的报文。
        """
        return self._call("zto.open.order.print", order_data)
