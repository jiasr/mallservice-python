"""多渠道物流适配器 + 微信物流助手 Handler + 中通开放平台 Handler

- LogisticsAdapter：注册中心，按 provider 名路由到对应 Handler。
- WechatExpressHandler：微信物流助手实现（电子面单 + 轨迹查询），注册为 "wechat"。
- ZtoHandler：中通开放平台实现（电子面单 + 轨迹查询），注册为 "zto"。

文档参考：《微信物流配送接入设计文档》3.2 / 3.3 / 4.2
注意：本文件属于 service 层，禁止加 deco_catch_view_exception（规范一.5），异常向上抛由 router 层捕获。
"""
import logging

from mall.common.wechat_express_utils import WechatExpressClient
from mall.common.zto_express_utils import ZtoClient, SANDBOX_GATEWAY, PROD_GATEWAY
from mall.db.models.DeliveryAccount.sql import DeliveryAccountDao, _decrypt_password

LOG = logging.getLogger(__name__)


class LogisticsHandler:
    """物流执行器抽象接口"""

    def create_waybill(self, order, config):
        raise NotImplementedError

    def cancel_waybill(self, waybill_no, config):
        raise NotImplementedError

    def get_track(self, company, waybill_no):
        raise NotImplementedError

    def get_provider_name(self):
        raise NotImplementedError


class LogisticsAdapter:
    """物流适配器注册中心：根据 provider 路由到对应 Handler"""

    _handlers = {}

    @classmethod
    def register(cls, name, handler_cls):
        cls._handlers[name] = handler_cls

    @classmethod
    def get_handler(cls, name="wechat"):
        handler_cls = cls._handlers.get(name)
        if not handler_cls:
            raise ValueError("不支持的物流提供商: {}".format(name))
        return handler_cls()

    @classmethod
    def get_available_providers(cls):
        return list(cls._handlers.keys())


class WechatExpressHandler(LogisticsHandler):
    """微信物流助手 Handler（provider=wechat）"""

    def get_provider_name(self):
        return "wechat"

    def create_waybill(self, order, config):
        """调用微信 add_order 创建运单，返回 waybill_id + waybill_data"""
        client = WechatExpressClient()
        from mall.common.constant import wx_app_id
        order_data = {
            "add_source": 0,
            "wx_appid": wx_app_id,
            "order_id": str(order.get("id")),
            "sender": {
                "name": config.get("sender_name"),
                "tel": config.get("sender_tel"),
                "province": config.get("sender_province"),
                "city": config.get("sender_city"),
                "area": config.get("sender_area"),
                "address": config.get("sender_address"),
            },
            "receiver": {
                "name": order.get("consignee"),
                "tel": order.get("tel"),
                "province": order.get("province"),
                "city": order.get("city"),
                "area": order.get("area"),
                "address": order.get("address"),
            },
            "shop": {"wxa_path": "/pages/order/detail?id={}".format(order.get("id"))},
            "cargo": {
                "count": order.get("total_quantity", 1),
                "weight": order.get("weight", 500),
                "space_x": config.get("space_x", 30),
                "space_y": config.get("space_y", 30),
                "space_z": config.get("space_z", 30),
            },
            "insured": {"use_insured": 0},
            "service": {"service_type": 0},
            "delivery_id": config.get("delivery_id"),
            "biz_id": config.get("biz_id"),
            "custom_remark": order.get("remark", ""),
        }
        return client.add_order(order_data)

    def get_track(self, company, waybill_no):
        """查询物流轨迹，格式化为统一列表"""
        client = WechatExpressClient()
        result = client.get_path(company, waybill_no)
        return [
            {
                "time": item.get("action_time"),
                "status": item.get("action_msg"),
                "location": item.get("action_location", ""),
            }
            for item in result.get("path_item_list", [])
        ]

    def cancel_waybill(self, waybill_no, config):
        client = WechatExpressClient()
        result = client.cancel_order(
            config.get("order_id"), waybill_no, config.get("delivery_id")
        )
        return result.get("result_code") == "0"


class ZtoHandler(LogisticsHandler):
    """中通开放平台 Handler（provider=zto）"""

    def get_provider_name(self):
        return "zto"

    def _build_client(self, config):
        gateway = PROD_GATEWAY if config.get("env") == "prod" else SANDBOX_GATEWAY
        return ZtoClient(config.get("app_key"), config.get("app_secret"), gateway)

    def create_waybill(self, order, config):
        """调用中通 zto.open.createOrder 创建运单，返回 waybill_id(运单号) + 原始响应"""
        client = self._build_client(config)

        def _detail_address(full, prov, city, county):
            """从完整地址中剔除省/市/区, 仅保留详细地址(街道), 符合中通
            senderAddress/receiverAddress 只填详细地址的规范(官方示例地址字段仅为街道)。"""
            detail = full or ""
            for seg in (prov, city, county):
                if seg:
                    detail = detail.replace(seg, "", 1)
            return detail.strip()

        # 中通 zto.open.createOrder 真实请求体(依据官方字段定义): 顶层 partnerType(必填)/
        # orderType/partnerOrderCode + senderInfo/receiveInfo(嵌套, 省/市/区/地址均必填)
        # + orderVasList + summaryInfo + orderItems + cabinet。
        # 关键: orderItems.weight(long, 克)/quantity(integer) 必须是数值, 传字符串会导致中通后端
        # 解析异常 -> S202; 扁平结构缺少 partnerType -> S208。早前这两个坑都已踩过。
        # partnerType: 2=非集团客户(网点授权/商家自寄); 1=集团客户(需 customerId)。
        # 本系统为网点授权模式(无 customerId), 固定走 2; 若误用 1 且缺 customerId 会触发 S202。
        # 注: accountInfo 按需求当前不发送(官方标注 accountInfo 为"否"; accountId 在
        # partnerType=2/orderType=1 时虽注明必传, 但实测需对照账号后台开通情况)。
        partner_type = config.get("partner_type") or "2"
        if partner_type == "1" and not config.get("customer_id"):
            partner_type = "2"
        order_data = {
            "partnerType": partner_type,
            "orderType": "1",
            "partnerOrderCode": "MALL{}".format(order.get("id")),
            "senderInfo": {
                "senderId": "",
                "senderName": config.get("sender_name", ""),
                "senderPhone": str(config.get("sender_phone", "") or ""),
                "senderMobile": str(config.get("sender_tel", "") or ""),
                "senderProvince": config.get("sender_province", ""),
                "senderCity": config.get("sender_city", ""),
                "senderDistrict": config.get("sender_area", ""),
                "senderAddress": _detail_address(config.get("sender_address", ""), config.get("sender_province", ""), config.get("sender_city", ""), config.get("sender_area", "")),
            },
            "receiveInfo": {
                "receiverName": order.get("consignee"),
                "receiverPhone": str(order.get("receiver_phone", "") or ""),
                "receiverMobile": str(order.get("tel", "") or ""),
                "receiverProvince": order.get("province", ""),
                "receiverCity": order.get("city", ""),
                "receiverDistrict": order.get("area", ""),
                "receiverAddress": _detail_address(order.get("address", ""), order.get("province", ""), order.get("city", ""), order.get("area", "")),
            },
            "orderVasList": [],
            "summaryInfo": {
                "size": "",
                "quantity": int(order.get("total_quantity", 1) or 1),
                "price": 0,
                "freight": 0,
                "premium": 0,
                "startTime": "",
                "endTime": "",
            },
            "remark": order.get("remark", ""),
            "orderItems": [
                {
                    "name": it.get("name", "商品"),
                    "category": "",
                    "material": "",
                    "size": "",
                    "weight": int(it.get("weight", 1) or 1),
                    "unitprice": 0,
                    "quantity": int(it.get("quantity", 1) or 1),
                    "remark": "",
                }
                for it in (order.get("items") or [])
            ] or [{"name": "商品", "category": "", "material": "", "size": "", "weight": 1, "unitprice": 0, "quantity": 1, "remark": ""}],
            "cabinet": {"address": "", "specification": 0, "code": ""},
        }
        resp = client.create_order(order_data)
        bill_code = None
        if isinstance(resp, dict):
            bill_code = (
                (resp.get("result") or {}).get("billCode")
                or resp.get("billCode")
                or (resp.get("data") or {}).get("billCode")
            )
        return {"waybill_id": bill_code, "waybill_data": resp}

    def cancel_waybill(self, waybill_no, config):
        client = self._build_client(config)
        return client.cancel_order({
            "partnerCode": config.get("partner_code"),
            "waybillNo": waybill_no,
        })

    def get_track(self, company, waybill_no):
        """中通轨迹查询：取一个启用的 zto 账号配置调用（账号级，非订单级）"""
        accs = DeliveryAccountDao.list(1, 1, 1, "zto")
        acc = (accs.get("list") or [{}])[0] if accs.get("list") else {}
        if not acc.get("app_key"):
            return {"message": "未配置中通账号", "list": []}
        config = {
            "app_key": acc.get("app_key"),
            "app_secret": _decrypt_password(acc.get("app_secret", "")),
            "env": acc.get("env", "sandbox"),
            "partner_code": acc.get("partner_code"),
        }
        client = self._build_client(config)
        resp = client.track_query({
            "waybillNo": waybill_no,
            "partnerCode": acc.get("partner_code"),
        })
        track_list = []
        if isinstance(resp, dict):
            raw = resp.get("result") or resp.get("data") or resp
            items = raw.get("waybillTrack") or raw.get("list") or raw.get("traces") or []
            for it in (items or []):
                track_list.append({
                    "time": it.get("time") or it.get("action_time") or it.get("scanTime") or "",
                    "status": it.get("status") or it.get("action") or it.get("remark") or "",
                    "location": it.get("location") or it.get("city") or "",
                })
        return track_list

    def print_waybill(self, bill_code, config):
        """获取中通面单图片(URL/Base64)，用于后台预览/打印（授权模式下可用）"""
        client = self._build_client(config)
        resp = client.print_waybill({
            "partnerCode": config.get("partner_code"),
            "waybillNo": bill_code,
        })
        img = None
        if isinstance(resp, dict):
            r = resp.get("result") or resp.get("data") or resp
            if isinstance(r, dict):
                img = (r.get("printUrl") or r.get("imageUrl") or r.get("billImage")
                       or r.get("img") or resp.get("msg"))
            else:
                img = r
            if not (isinstance(img, str) and (
                img.startswith("http") or img.startswith("data:image")
                or img.startswith("/9j/") or len(img) > 200
            )):
                img = None
        return img


# 注册微信物流助手 handler（模块导入时自动注册）
LogisticsAdapter.register("wechat", WechatExpressHandler)
# 注册中通开放平台 handler
LogisticsAdapter.register("zto", ZtoHandler)
