"""中通沙箱联调脚本 (签名已验证通过)

已验证正确的部分:
- 沙箱 appKey = 7fbd04c8cee40fbf8c539
- 沙箱 appSecret = c3395f9e4f6d7f718f1d5   (注意: 之前把 key/secret 顺序搞反了)
- 签名: x-datadigest = base64( md5( body + appSecret ) ), body 用紧凑 JSON
- 网关: https://japi-test.zto.com/{method}
- partnerCode = D36_360320735712101 已在控制台"商家授权网点授权"绑定, 授权模式无需 partnerKey

当前卡点: 接口返回 "无权限访问(S210)" —— 应用未授权寄件服务。
解决: 开放平台控制台 -> 应用(app, appKey 7fbd04...) -> 服务管理 -> 添加/授权
      "寄件服务": zto.open.createOrder / zto.open.cancelPreOrder / zto.merchant.waybill.track.query
      授权后直接重跑本脚本即可看到下单成功返回(含 billCode 运单号)。

运行: cd e:/aicode/mallservice-python; python test_zto_sandbox.py
"""
import json
import hashlib
import base64

import requests

APP_KEY = "7fbd04c8cee40fbf8c539"
APP_SECRET = "c3395f9e4f6d7f718f1d5"
PARTNER = "D36_360320735712101"
GW = "https://japi-test.zto.com"


def sign(body, secret):
    return base64.b64encode(
        hashlib.md5((body + secret).encode("utf-8")).digest()).decode()


def call(method, data):
    body = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    headers = {
        "x-appKey": APP_KEY,
        "x-datadigest": sign(body, APP_SECRET),
        "Content-Type": "application/json;charset=utf-8",
    }
    r = requests.post("{}/{}".format(GW, method),
                      data=body.encode("utf-8"), headers=headers, timeout=15)
    return r.json()


def main():
    order = {
        "partnerCode": PARTNER, "type": 1, "tradeId": "TEST20260903001",
        "sender": {"name": "测试发件人", "mobile": "13900000000", "prov": "山东省",
                   "city": "济南市", "county": "历城区", "address": "宏昌路1号"},
        "receiver": {"name": "测试收件人", "mobile": "13800000000", "prov": "北京市",
                     "city": "北京市", "county": "朝阳区", "address": "测试路2号"},
        "items": [{"name": "测试商品", "quantity": "1", "weight": "1"}], "weight": 1,
    }
    print(">>> createOrder 返回:")
    print(json.dumps(call("zto.open.createOrder", order), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
