"""腾讯出行服务·跑腿(同城即时配送) 2B 上游渠道 API 客户端封装

文档: 腾讯出行服务·开放平台《跑腿上游渠道接入文档(2B)》 + 子文档 04.2.1(普通询价下单)
接口前缀:
- 测试: https://test.tai.qq.com/api/open/express/intracity/2b
- 正式: https://weixin.go.qq.com/api/open/express/intracity/2b
全部 POST + JSON, 通用字段 seq_id/timestamp(毫秒)/nonce/api_key/sign,

签名算法(附录 3.9.1):
  取除 sign 外所有参数, 按 key 字典升序拼成 k=v&k=v... 的原始串 src1;
  将 src1 尾部拼接分配给调用方的 api_secret 形成 src2;
  对 src2 做 md5 并转大写即为 sign。
  注意: 对象类型 value 需 json 序列化(ensure_ascii=False, 顺序与传输一致)后拼接;
  标量字符串原样(不加引号), 布尔用小写 true/false, 与传输 JSON 保持一致。

注意: 本文件属于 service 层工具, 禁止加 deco_catch_view_exception(规范一.5),
异常统一上抛(Fail), 由 router 层装饰器捕获。
"""
import hashlib
import json
import logging
import time
import uuid

import requests

from mall.common.common import Fail

LOG = logging.getLogger(__name__)

TEST_GATEWAY = "https://test.tai.qq.com/api/open/express/intracity/2b"
PROD_GATEWAY = "https://weixin.go.qq.com/api/open/express/intracity/2b"

# 腾讯跑腿通用响应错误码 code -> (英文原文, 中文说明)（附录 3.8）
ERRAND_ERROR_DESC = {
    0: ("success", "成功"),
    400000: ("请求参数错误，备注超长", "请求参数错误，备注超长"),
    400001: ("请求 URL 错误", "请求 URL 错误"),
    400002: ("请求方法错误", "请求方法错误"),
    400003: ("appId 错误", "app_key 错误"),
    400004: ("时间戳过期或者 nonce 重复", "时间戳过期或 nonce 重复（核对服务器时间/重试）"),
    400005: ("签名验证失败", "签名验证失败（核对 api_secret 与签名拼接顺序）"),
    400101: ("请求频繁，请稍后重试", "请求频繁，请稍后重试"),
    400102: ("询价价格已失效，请重新询价", "询价价格已失效，请重新询价"),
    400103: ("询价地址不支持", "询价地址不支持（该城市/区域暂无可调度运力）"),
    400100: ("通用非影响主流程错误码", "通用非影响主流程错误码，无需关注"),
    400201: ("渠道方订单状态不匹配", "渠道方订单状态不匹配"),
    500000: ("其他系统错误", "其他系统错误，建议指数递增重试(1s,2s,4s,8s,16s,32s,64s)"),
}

# 订单状态(附录 3.2) code -> 中文
ERRAND_ORDER_STATUS = {
    10205: "派单失败",
    30050: "派单中",
    30100: "取件中",
    30200: "到达取件点",
    30300: "送件中",
    30400: "送回中",
    30700: "取消中",
    30710: "已取消",
    30900: "已送达",
}

# 事件类型(附录 3.2) event -> 中文
ERRAND_EVENT = {
    101: "创单失败",
    150: "派单/改派",
    200: "骑手接单",
    250: "骑手转单",
    300: "到达取件点",
    400: "开始送件",
    450: "已送达",
    500: "骑手送回",
    670: "运力骑手改派",
    850: "订单异常",
    950: "取消",
    960: "退款通知",
}

# 物品类别(附录 3.3) goods_type
ERRAND_GOODS_TYPE = {
    1: "文件证照", 2: "服饰", 3: "食品饮料", 4: "蛋糕", 5: "鲜花",
    6: "数码", 7: "水果生鲜", 8: "药品", 9: "汽配", 10: "个护美妆",
    11: "家居家纺", 12: "其他",
}

# 跑腿类型(附录 3.4) express_type
ERRAND_EXPRESS_TYPE = {1: "特惠拼送", 2: "极速直送"}

# 取消失败原因(附录 3.6.1)
ERRAND_CANCEL_FAIL_REASON = {
    "当前订单状态不支持": "当前订单状态不支持取消",
    "服务商侧取消失败": "服务商侧取消失败",
    "其它": "其它原因",
}


def _val_str(v):
    """签名时标量/对象的字符串化（与传输 JSON 保持一致）

    - 对象(dict/list): json 序列化(ensure_ascii=False, 紧凑分隔符)
    - 布尔: 小写 true/false（与 json.dumps 一致）
    - 字符串: 原样（不加引号，与附录 3.9.1 示例 name=test 一致）
    - 其它标量: str()
    """
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v
    return str(v)


class TencentErrandClient:
    """腾讯跑腿(同城即时配送)上游渠道客户端"""

    def __init__(self, api_key, api_secret, env="sandbox", gateway=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.gateway = gateway or (PROD_GATEWAY if env == "prod" else TEST_GATEWAY)

    # ---------------- 签名 ----------------
    def _sign(self, params):
        """附录 3.9.1: 除 sign 外按 key 升序拼 k=v&..., 尾部拼 api_secret, md5 大写"""
        parts = []
        for k in sorted(params.keys()):
            if k == "sign":
                continue
            parts.append("{}={}".format(k, _val_str(params[k])))
        raw = "&".join(parts) + self.api_secret
        return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    def _common(self):
        return {
            "seq_id": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "nonce": uuid.uuid4().hex[:32],
            "api_key": self.api_key,
        }

    def _call(self, path, biz):
        """统一请求: 合并通用字段 + 业务字段, 计算 sign, POST JSON, 校验响应 code

        biz 中的 None 值会被丢弃(避免透传 null), 但保留空字符串(必填项缺失由服务端报错)。
        """
        params = self._common()
        params.update({k: v for k, v in biz.items() if v is not None})
        params["sign"] = self._sign(params)
        # 传输 JSON 必须与签名一致: 嵌套对象 value 用紧凑分隔符(无空格)序列化,
        # 与 _val_str 签名时的 json.dumps(..., separators=(",",":")) 字节级一致
        # (文档 3.9.1 注: 验签时"原样提取"传输 JSON 中的对象 value)。
        body = json.dumps(params, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        url = "{}{}".format(self.gateway, path)
        LOG.info("ERRAND req %s seq_id=%s", url, params.get("seq_id"))
        resp = requests.post(
            url, data=body, headers={"Content-Type": "application/json;charset=utf-8"}, timeout=15
        )
        try:
            data = resp.json()
        except Exception:
            raise Fail("ERRAND_RESP_INVALID", {}, "腾讯跑腿返回非 JSON: {}".format(resp.text[:500]))
        code = data.get("code", -1)
        if code != 0:
            desc = ERRAND_ERROR_DESC.get(code, ("", "未知错误"))
            msg = "腾讯跑腿接口失败[{}] {}".format(code, data.get("message") or desc[0])
            if desc[1] and desc[1] != desc[0]:
                msg += "（{}）".format(desc[1])
            raise Fail("ERRAND_API_FAILED", {"code": code}, msg)
        return data.get("data", {}) or {}

    # ---------------- 业务接口 ----------------
    def estimate_price(self, biz):
        """询价 /estimatePrice（普通询价下单模式）"""
        return self._call("/estimatePrice", biz)

    def create_order(self, biz):
        """下单 /createOrder（与询价使用同一 third_order_id 直接创单）"""
        return self._call("/createOrder", biz)

    def cancel_order(self, order_id, order_type=2, cancel_type=None, cancel_reason=None):
        """取消订单 /cancelOrder

        order_type: 1=腾讯业务订单号(order_code) 2=接入方业务订单号(third_order_id)
        """
        biz = {"order_id": str(order_id), "order_type": int(order_type)}
        if cancel_type is not None:
            biz["cancel_type"] = int(cancel_type)
        if cancel_reason:
            biz["cancel_reason"] = cancel_reason
        return self._call("/cancelOrder", biz)

    def pre_cancel_order(self, order_id, order_type=2):
        """取消前预检 /preCancelOrder（返回是否可取消 + 取消费）"""
        return self._call("/preCancelOrder", {"order_id": str(order_id), "order_type": int(order_type)})

    def order_detail(self, order_id, order_type=2):
        """订单详情 /orderDetail（含状态/费用/骑手/取送件照片）"""
        return self._call("/orderDetail", {"order_id": str(order_id), "order_type": int(order_type)})

    def rider_location(self, order_id, order_type=2):
        """骑手实时位置 /riderLocation"""
        return self._call("/riderLocation", {"order_id": str(order_id), "order_type": int(order_type)})

    def order_status_change_node(self, order_id, order_type=2):
        """订单状态变更节点 /orderStatusChangeNode"""
        return self._call("/orderStatusChangeNode", {"order_id": str(order_id), "order_type": int(order_type)})

    def driver_trajectory(self, order_id, order_type=2, start_time=None, end_time=None):
        """骑手轨迹 /driverTrajectory（start_time/end_time 为秒级时间戳）"""
        biz = {"order_id": str(order_id), "order_type": int(order_type)}
        if start_time is not None:
            biz["start_time"] = int(start_time)
        if end_time is not None:
            biz["end_time"] = int(end_time)
        return self._call("/driverTrajectory", biz)

    def add_tips(self, third_order_id, fee=None, total_fee=None):
        """加小费 /addTips（fee 单次累加 / total_fee 覆盖总额，二者不可同传或同空）"""
        biz = {"third_order_id": str(third_order_id)}
        if fee is not None:
            biz["fee"] = int(fee)
        if total_fee is not None:
            biz["total_fee"] = int(total_fee)
        return self._call("/addTips", biz)

    # ---------------- 地理编码(腾讯位置服务) ----------------
    def geocode(self, address, region=None, lbs_key=None):
        """调用腾讯位置服务地理编码, 补全收寄件经纬度与城市编码(adcode)

        跑腿 AddressInfo 必须传 poi_lng/poi_lat, city_code 必须传标准行政区划编码,
        二者均通过地理编码一次性获得。文档: https://apis.map.qq.com/ws/geocoder/v1/
        前置: 需在系统设置配置 tencent_lbs_key(腾讯位置服务 key)。
        """
        if not lbs_key:
            raise Fail(
                "ERRAND_NO_LBS_KEY", {},
                "跑腿下单需收寄件经纬度与城市编码，请先在系统设置配置腾讯位置服务 key（tencent_lbs_key）",
            )
        url = "https://apis.map.qq.com/ws/geocoder/v1/"
        params = {"address": address, "key": lbs_key}
        if region:
            params["region"] = region
        LOG.info("ERRAND geocode address=%s region=%s", address, region)
        resp = requests.get(url, params=params, timeout=15)
        try:
            data = resp.json()
        except Exception:
            raise Fail("ERRAND_GEOCODE_FAILED", {}, "地理编码返回非 JSON")
        if data.get("status") != 0:
            raise Fail(
                "ERRAND_GEOCODE_FAILED", {"code": data.get("status")},
                "地理编码失败: {}".format(data.get("message")),
            )
        r = data.get("result", {})
        loc = r.get("location", {}) or {}
        adcode = (r.get("ad_info") or {}).get("adcode", "")
        if not loc.get("lat") or not loc.get("lng"):
            raise Fail("ERRAND_GEOCODE_FAILED", {}, "地理编码未返回经纬度: {}".format(address))
        return {
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "adcode": adcode,
            "title": address,
        }
