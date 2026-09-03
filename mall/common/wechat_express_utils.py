"""微信物流助手 API 客户端封装

封装微信物流助手全部服务端接口，所有请求需携带 access_token（复用 mall.common.wechat_utils）。
接口路径遵循微信官方 cgi-bin/express/business/* 。
文档参考：《微信物流配送接入设计文档》4.1
"""
import requests
import logging

from mall.common.wechat_utils import get_access_token

LOG = logging.getLogger(__name__)

WX_API = "https://api.weixin.qq.com/cgi-bin/express/business"


class WechatExpressClient:
    """微信物流助手客户端"""

    def _call(self, path, payload):
        """统一请求：GET/POST 统一拼 access_token，返回解析后的 dict（含错误检查）"""
        url = "{}?access_token={}".format(path, get_access_token())
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("errcode", 0) != 0:
            LOG.error("微信物流接口异常 path=%s errcode=%s errmsg=%s", path, data.get("errcode"), data.get("errmsg"))
            raise Exception("微信物流接口异常: {} {}".format(data.get("errcode"), data.get("errmsg")))
        return data

    # ---------- 账号管理 ----------
    def bind_account(self, delivery_id, biz_id, password="", remark="", account_type=1):
        """绑定/更新物流账号（快递公司账号）

        account_type: 微信账号类型 1=月结账号 2=网点账号 3=手机号
        """
        return self._call("{}/account/bind".format(WX_API), {
            "type": account_type,
            "delivery_id": delivery_id,
            "biz_id": biz_id,
            "password": password,
            "remark": remark,
        })

    def get_all_accounts(self):
        """获取所有已绑定的物流账号"""
        data = self._call("{}/account/getall".format(WX_API), {})
        return data.get("list", [])

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
