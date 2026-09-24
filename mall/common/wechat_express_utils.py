"""微信物流助手 API 客户端封装

封装微信物流助手全部服务端接口，所有请求需携带 access_token（复用 mall.common.wechat_utils）。
接口路径遵循微信官方 cgi-bin/express/business/* 。
文档参考：《微信物流配送接入设计文档》4.1
"""
import json

import requests
import logging

from mall.common.wechat_utils import get_access_token

LOG = logging.getLogger(__name__)

WX_API = "https://api.weixin.qq.com/cgi-bin/express/business"


def _parse_json(resp):
    """解析微信响应 JSON

    微信部分接口(如 delivery/getall)响应头未声明 charset, requests 会按 ISO-8859-1
    解码, 导致 delivery_name / service_name 等中文字段变成 "å®\\x89..." 乱码。
    这里统一按 UTF-8 解码, 异常时回退到 requests 默认解析。
    """
    try:
        return json.loads(resp.content.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return resp.json()


# 微信物流接口错误码 -> (errmsg 英文原文, 中文说明与处理建议)
# 依据: 官方文档《生成运单》第6节错误码表 + 《绑定/解绑物流账号》错误码表；
# 40097 为通用错误码(官方文档未单列), 是 bindAccount 实测遇到的。
WX_ERROR_DESC = {
    "-1": ("system error", "系统繁忙，请稍后重试"),
    "40001": ("invalid credential, access_token is invalid or not latest",
              "access_token 无效或不是最新的：核对 AppSecret 配置，确认调用的是正确的小程序"),
    "40003": ("invalid openid", "openid 不合法：确认该 openid 属于当前小程序"),
    "40097": ("invalid args", "参数不合法：检查字段名与取值，如 bindAccount 的 type 必须是字符串 bind/unbind"),
    # 40199 为 path/get(轨迹查询) 实测遇到的运单不存在
    "40199": ("waybill_id not found", "运单号不存在：确认运单号是否正确、是否由本账号下单（手动填的单号查不到轨迹）"),
    "47001": ("data format error", "数据格式错误或缺少参数：检查请求体 JSON"),
    "930559": ("invalid openid", "沙盒环境 openid 无效"),
    "930561": ("args error", "参数错误"),
    "930564": ("quota run out", "沙盒环境调用配额已用完"),
    "9300501": ("delivery side error",
                "快递侧逻辑错误：需结合快递侧返回码定位，如地址/电话不合规、客户密码不正确"),
    "9300502": ("delivery side sys error", "快递公司系统错误，请稍后重试"),
    "9300503": ("specified delivery id is not registered",
                "delivery_id 不存在：请使用支持的快递公司列表中的 ID"),
    "9300510": ("invalid service type", "service_type 不存在：核对快递公司支持的服务类型"),
    "9300525": ("biz id not bind", "biz_id 未绑定：请先绑定该快递账号"),
    "9300526": ("arg size exceed limit", "参数字段长度超限"),
    "9300531": ("invalid biz_id or password",
                "客户编码(biz_id)无效或密码错误：确认快递公司账号已签约且编码/密码无误；发散单请填 cash_biz_id 并留空密码"),
    "9300534": ("invalid shop args", "access_token 与 openid 参数不匹配"),
    "9300535": ("invalid shop args", "shop 字段商品信息不合法：缩略图 url/商品名称为空或商品数量为 0"),
    "9300536": ("invalid wxa_appid", "add_source=2 时 wxa_appid 无效"),
}


class WechatExpressError(Exception):
    """微信物流接口业务错误

    携带 errcode / errmsg 与快递侧返回码，message 为可直接展示的中英文提示。
    """

    def __init__(self, errcode, errmsg="", delivery_resultcode=None, delivery_resultmsg=""):
        self.errcode = errcode
        self.errmsg = errmsg or WX_ERROR_DESC.get(str(errcode), ("", ""))[0]
        self.delivery_resultcode = delivery_resultcode
        self.delivery_resultmsg = delivery_resultmsg or ""
        super().__init__(self.message)

    @property
    def message(self):
        """中英文完整提示：[微信]错误码 英文原文（中文说明）；[快递侧]返回码 信息"""
        code = str(self.errcode)
        en_msg, cn_desc = WX_ERROR_DESC.get(code, ("", ""))
        parts = ["微信物流接口报错 {} {}".format(code, self.errmsg or en_msg)]
        if cn_desc:
            parts.append("（{}）".format(cn_desc))
        if self.delivery_resultcode is not None or self.delivery_resultmsg:
            parts.append("；快递侧返回[{}] {}".format(self.delivery_resultcode, self.delivery_resultmsg))
        return "".join(parts)


class WechatExpressClient:
    """微信物流助手客户端"""

    def _call(self, path, payload):
        """统一请求：GET/POST 统一拼 access_token，返回解析后的 dict（含错误检查）"""
        url = "{}?access_token={}".format(path, get_access_token())
        # 官方错误码 9300501 明确建议: python 用 json.dumps(..., ensure_ascii=False),
        # 否则中文被转义成 \uXXXX, 快递侧会报"客户密码不正确"等逻辑错误
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        resp = requests.post(
            url, data=body, headers={"Content-Type": "application/json"}, timeout=15
        )
        return self._check_error(path, _parse_json(resp))

    def _get(self, path):
        """GET 请求：部分接口(如 delivery/getall)为 GET 且无请求体"""
        url = "{}?access_token={}".format(path, get_access_token())
        resp = requests.get(url, timeout=15)
        return self._check_error(path, _parse_json(resp))

    def _check_error(self, path, data):
        """统一错误检查，抛出携带中英文说明的 WechatExpressError

        官方对 9300501 的说明是"详细原因需要看 delivery_resultcode"，快递侧返回码
        与错误信息必须一并保留，否则只能看到一句 delivery logic fail 无从排查。
        """
        errcode = data.get("errcode", 0)
        if not errcode:
            return data
        LOG.error(
            "微信物流接口异常 path=%s errcode=%s errmsg=%s delivery_resultcode=%s delivery_resultmsg=%s",
            path, errcode, data.get("errmsg"),
            data.get("delivery_resultcode"), data.get("delivery_resultmsg"),
        )
        raise WechatExpressError(
            errcode,
            data.get("errmsg", ""),
            data.get("delivery_resultcode"),
            data.get("delivery_resultmsg", ""),
        )

    # ---------- 账号管理 ----------
    def bind_account(self, delivery_id, biz_id, password="", remark_content="", action="bind"):
        """绑定/解绑物流账号（快递公司账号）

        注意: 官方 type 是字符串 bind=绑定 / unbind=解绑, 表示操作类型而非账号类型。
        历史文档里的 1=月结账号 2=网点账号 3=手机号 已废弃(getallaccount 也不再返回 type),
        传整型会导致 errcode=40097 invalid args。
        备注字段名为 remark_content（提交 EMS 审核时需要）, 不是 remark。
        """
        payload = {
            "type": action,
            "delivery_id": delivery_id,
            "biz_id": biz_id,
        }
        if password:
            payload["password"] = password
        if remark_content:
            payload["remark_content"] = remark_content
        LOG.info("微信%s物流账号 delivery_id=%s biz_id=%s", action, delivery_id, biz_id)
        return self._call("{}/account/bind".format(WX_API), payload)

    def get_all_accounts(self):
        """获取所有已绑定的物流账号"""
        data = self._call("{}/account/getall".format(WX_API), {})
        return data.get("list", [])

    # ---------- 快递公司 ----------
    def get_all_delivery(self):
        """获取支持的快递公司列表 GET /cgi-bin/express/business/delivery/getall

        每项含: delivery_id, delivery_name, can_use_cash(1=支持散单),
        can_get_quota, service_type[{service_type, service_name}], cash_biz_id
        """
        data = self._get("{}/delivery/getall".format(WX_API))
        return data.get("data", [])

    def find_cash_biz_id(self, delivery_id):
        """取该快递公司的散单(现付)编码 cash_biz_id

        getAllDelivery 里 can_use_cash=1 的公司才返回可用现付编码；
        不支持散单或未取到时返回空串。
        """
        for item in self.get_all_delivery():
            if item.get("delivery_id") == delivery_id:
                if item.get("can_use_cash") == 1:
                    return item.get("cash_biz_id") or ""
                return ""
        return ""

    # ---------- 运单 ----------
    def add_order(self, order_data):
        """生成运单（电子面单），返回 waybill_id / waybill_data"""
        return self._call("{}/order/add".format(WX_API), order_data)

    def cancel_order(self, order_id, waybill_id, delivery_id):
        """取消运单"""
        return self._call("{}/order/cancel".format(WX_API), {
            "order_id": str(order_id),
            "waybill_id": waybill_id,
            "delivery_id": delivery_id,
        })

    def get_order(self, order_id):
        """获取运单信息"""
        return self._call("{}/order/get".format(WX_API), {"order_id": str(order_id)})

    def batch_get_order(self, order_list):
        """批量获取运单信息"""
        return self._call("{}/order/batchget".format(WX_API), {"order_list": order_list})

    def test_update_order(self, data):
        """模拟更新订单状态（仅沙盒：delivery_id=TEST / biz_id=test_biz_id）"""
        return self._call("{}/test_update_order".format(WX_API), data)

    def get_path(self, delivery_id, waybill_id):
        """查询运单轨迹"""
        return self._call("{}/path/get".format(WX_API), {
            "delivery_id": delivery_id,
            "waybill_id": waybill_id,
        })

    def get_quota(self, delivery_id, biz_id):
        """查询电子面单余额"""
        return self._call("{}/quota/get".format(WX_API), {
            "delivery_id": delivery_id,
            "biz_id": biz_id,
        })
