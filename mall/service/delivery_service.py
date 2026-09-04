"""配送履约业务逻辑层（聚合 DAO 与多渠道物流 Handler）

- 账号管理：列表 / 绑定（按渠道区分：微信调微信绑定，中通直接入库）/ 同步
- 发货：ship 按账号 provider 选择渠道；ship_by_wechat 走微信，ship_zto 走中通
- 轨迹：query_track 按渠道查询并格式化

注意：本文件是 service 层，禁止加 deco_catch_view_exception（规范一.5），
异常统一上抛，由 router 层装饰器捕获。
"""
import datetime
import json
import logging
import re

LOG = logging.getLogger(__name__)
from mall.db.engines.mysql import get_session
from mall.db.models.Order.model import Order, OrderItem
from mall.db.models.DeliveryAccount.sql import DeliveryAccountDao, _decrypt_password
from mall.common.wechat_express_utils import WechatExpressClient
from mall.service.express_service import LogisticsAdapter
from mall.common.common import Fail

# 中通开放平台错误码 -> 中文描述（覆盖公共/鉴权错误码，便于排查）
ZTO_ERROR_DESC = {
    "S200": "请求超时(后端服务调用超时)",
    "S202": "发生错误(后端服务调用抛出异常)",
    "S203": "服务暂不可用",
    "S206": "API调用次数达到限制",
    "S207": "API不存在",
    "S208": "必填参数不能为空",
    "S210": "无权限访问(未绑定服务关系, 需在开放平台订阅该API)",
    "S211": "签名错误",
    "S212": "IP黑白名单限制",
    "S214": "时间戳非法",
    "S221": "API流控限制",
    "E404": "鉴权失败: 未绑定电子面单账号",
    "E409": "鉴权失败: 收寄人电话号码校验不一致",
    "E413": "鉴权失败: 请输入收寄人任一方电话号码后4位",
    "E416": "不符合中通运单号规则校验",
    "E418": "鉴权失败: 不存在对应的网点授权",
}


def list_accounts(params):
    return DeliveryAccountDao.list(
        int(params.get('pageNum', 1)),
        int(params.get('pageSize', 20)),
        int(params['status']) if params.get('status') not in (None, '', 'null') else None,
        params.get('provider'),
    )


def bind_account(data):
    """绑定快递账号

    - wechat: 先调微信绑定，成功后再加密入库
    - zto:    直接入库（中通开放平台授权模式下不需要微信绑定）
    """
    provider = data.get("provider", "wechat")
    if provider == "zto":
        return DeliveryAccountDao.create(data)
    client = WechatExpressClient()
    try:
        client.bind_account(
            delivery_id=data.get('deliveryId', ''),
            biz_id=data.get('bizId', ''),
            password=data.get('password', ''),
            remark=data.get('accountName', ''),
            account_type=int(data.get('accountType', 1) or 1),
        )
    except Fail:
        raise
    except Exception as e:
        raise Fail("WX_EXPRESS_BIND_FAILED", {}, "微信物流绑定失败：" + str(e))
    return DeliveryAccountDao.create(data)


def sync_accounts():
    """从微信同步已绑定的物流账号"""
    client = WechatExpressClient()
    accounts = client.get_all_accounts()
    return DeliveryAccountDao.upsert_from_wechat(accounts)


def ship(order_no, account_id):
    """通用发货：按账号 provider 选择渠道(wechat / zto)"""
    acc = DeliveryAccountDao.get_by_id(account_id)
    provider = (acc or {}).get("provider", "wechat")
    if provider == "zto":
        return ship_zto(order_no, account_id)
    return ship_by_wechat(order_no, account_id)


def ship_by_wechat(order_no, account_id):
    """微信物流助手发货：生成电子面单并写回订单物流字段

    Args:
        order_no: 订单号
        account_id: t_mall_delivery_account 主键
    Returns:
        dict: {success, waybillId, waybillData}
    """
    # 1. 读取订单与账号（只读，网络调用不放在事务内）
    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_no).first()
        if not order:
            raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
        if order.order_status != 1:
            raise Fail("ORDER_CANNOT_SHIP", {}, "当前订单状态不可发货")
        items = session.query(OrderItem).filter(OrderItem.order_id == order_no).all()
        acc = DeliveryAccountDao.get_by_id(account_id)
        if not acc:
            raise Fail("DELIVERY_ACCOUNT_NOT_FOUND", {}, "快递账号不存在")
        from mall.service.setting_service import get_all_settings
        settings = get_all_settings()
        total_qty = sum((it.quantity or 0) for it in items)

    # 2. 调用微信生成运单
    order_dict = {
        'id': order.id,
        'consignee': order.consignee_name,
        'tel': order.consignee_mobile,
        'province': '', 'city': '', 'area': '',
        'address': order.consignee_address,
        'remark': order.remark,
        'total_quantity': total_qty,
    }
    config = {
        'delivery_id': acc['delivery_id'],
        'biz_id': acc['biz_id'],
        'sender_name': settings.get('site_name', ''),
        'sender_tel': settings.get('service_phone', ''),
        'sender_province': '', 'sender_city': '', 'sender_area': '',
        'sender_address': settings.get('site_name', ''),
    }
    handler = LogisticsAdapter.get_handler('wechat')
    result = handler.create_waybill(order_dict, config)
    waybill_id = result.get('waybill_id')

    # 微信下单失败：禁止改写订单状态
    if not waybill_id:
        raise Fail('WX_CREATE_ORDER_FAILED', {}, '微信物流下单失败，未返回运单号')

    # 3. 写回订单物流字段与状态
    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_no).first()
        order.shipping_company = acc['delivery_id']
        order.shipping_no = waybill_id or ''
        order.waybill_data = json.dumps(result.get('waybill_data') or [], ensure_ascii=False)
        order.order_status = 2  # 已发货
        order.shipped_at = datetime.datetime.now()
    return {'success': True, 'waybillId': waybill_id, 'waybillData': result.get('waybill_data')}


def _split_addr(addr):
    """从完整收货地址粗略拆出省/市/区(中通下单需分开字段)
    兼容带空格(省 市 区 ...)与无空格(省市区连写)两种写法,
    并去除 city/district 里冗余的省/市前缀(如 '山东省济南市' -> '济南市'),
    否则中通按区域名匹配失败会报 S202。"""
    prov = city = county = ''
    if not addr:
        return prov, city, county
    m = re.search(r'([^\s,，]+?(?:省|自治区))', addr)
    if m:
        prov = m.group(1)
    m = re.search(r'(北京|上海|天津|重庆)市', addr)
    if m:
        prov = m.group(1) + '市'
    m = re.search(r'([^\s,，]+?市)', addr)
    if m and m.group(1) != prov:
        city = m.group(1)
    m = re.search(r'([^\s,，]+?(?:区|县|旗))', addr)
    if m:
        county = m.group(1)
    # 去掉 city/district 中冗余的省/市前缀, 避免中通按区域名匹配失败(S202)
    if prov and city.startswith(prov):
        city = city[len(prov):]
    if prov and county.startswith(prov):
        county = county[len(prov):]
    if city and county.startswith(city):
        county = county[len(city):]
    return prov, city, county


def ship_zto(order_no, account_id):
    """中通开放平台发货：生成电子面单并写回订单物流字段

    Returns:
        dict: {success, waybillId, waybillData}
    """
    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_no).first()
        if not order:
            raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
        if order.order_status != 1:
            raise Fail("ORDER_CANNOT_SHIP", {}, "当前订单状态不可发货")
        items = session.query(OrderItem).filter(OrderItem.order_id == order_no).all()
        acc = DeliveryAccountDao.get_by_id(account_id)
        if not acc:
            raise Fail("DELIVERY_ACCOUNT_NOT_FOUND", {}, "快递账号不存在")
        if acc.get("provider") != "zto":
            raise Fail("DELIVERY_ACCOUNT_INVALID", {}, "该账号不是中通渠道")
        from mall.service.setting_service import get_all_settings
        settings = get_all_settings()
        total_qty = sum((it.quantity or 0) for it in items)

    prov, city, county = _split_addr(order.consignee_address)
    order_dict = {
        'id': order_no,
        'consignee': order.consignee_name,
        'tel': order.consignee_mobile,
        'province': prov, 'city': city, 'area': county,
        'address': order.consignee_address,
        'remark': order.remark,
        'total_quantity': total_qty,
        'items': [
            {'name': it.title or '商品', 'quantity': it.quantity or 1, 'weight': 1}
            for it in items
        ],
        'total_weight': 1,
    }
    config = {
        'app_key': acc.get('app_key'),
        'app_secret': _decrypt_password(acc.get('app_secret', '')),
        'env': acc.get('env', 'sandbox'),
        'partner_code': acc.get('partner_code'),
        'customer_id': acc.get('customer_id', ''),
        'partner_key': _decrypt_password(acc.get('partner_key', '')),
        'partner_type': acc.get('partner_type', '1'),
        'sender_name': settings.get('site_name', ''),
        'sender_tel': settings.get('service_phone', ''),
        # 发货地址优先取系统设置 sender_address, 未配置时回退到商城名称
        'sender_address': settings.get('sender_address') or settings.get('site_name', ''),
    }
    # 发件人省/市/区从完整发货地址中解析(与收件人一致的处理方式), 避免中通因发件地址为空报 S202
    _s_prov, _s_city, _s_county = _split_addr(config['sender_address'])
    config['sender_province'] = _s_prov
    config['sender_city'] = _s_city
    config['sender_area'] = _s_county
    handler = LogisticsAdapter.get_handler('zto')
    result = handler.create_waybill(order_dict, config)
    waybill_id = result.get('waybill_id')

    # 下单失败：禁止改写订单状态，直接抛出物流侧错误（订单保持待发货）
    if not waybill_id:
        raw = result.get('waybill_data') or {}
        if not isinstance(raw, dict):
            raw = {}
        status_code = raw.get('statusCode') or ''
        desc = ZTO_ERROR_DESC.get(status_code, '')
        msg = raw.get('message') or ''
        if desc:
            err_msg = '中通下单失败[{}] {}'.format(status_code, desc)
            if msg and msg not in desc:
                err_msg += '（{}）'.format(msg)
        else:
            err_msg = '中通下单失败({}): {}'.format(status_code, msg or '未返回运单号')
        raise Fail('ZTO_CREATE_ORDER_FAILED', {}, err_msg)

    # 尽力获取面单图片(需开放平台授权面单打印能力, 失败不影响发货)
    print_image = None
    try:
        print_image = handler.print_waybill(waybill_id, config)
    except Exception as e:
        LOG.warning("中通面单图片获取失败(可忽略): %s", e)

    waybill_payload = {
        "billCode": waybill_id,
        "raw": result.get('waybill_data'),
        "printImage": print_image,
    }

    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_no).first()
        order.shipping_company = '中通快递'
        order.shipping_no = waybill_id or ''
        order.waybill_data = json.dumps(waybill_payload, ensure_ascii=False)
        order.order_status = 2  # 已发货
        order.shipped_at = datetime.datetime.now()
    return {'success': True, 'waybillId': waybill_id, 'waybillData': waybill_payload}


def get_waybill(order_no):
    """获取订单已生成的电子面单数据（用于预览/补打）

    Returns:
        dict: {success, waybillData}
    """
    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_no).first()
        if not order:
            raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
        raw = order.waybill_data or ''
    if not raw:
        return {'success': False, 'message': '该订单未生成电子面单'}
    try:
        data = json.loads(raw)
    except Exception:
        data = []
    return {'success': True, 'waybillData': data or []}


def query_track(delivery_id, waybill_id):
    """查询物流轨迹（按渠道）"""
    handler = LogisticsAdapter.get_handler(delivery_id if delivery_id in ("zto",) else 'wechat')
    return handler.get_track(delivery_id, waybill_id)


def update_account(data):
    """更新快递账号（名称/状态/渠道字段）"""
    account_id = data.get('id')
    if not account_id:
        raise Fail("INVALID_PARAM", {}, "缺少账号ID")
    return DeliveryAccountDao.update(account_id, data)


def delete_account(account_id):
    """删除快递账号"""
    return DeliveryAccountDao.delete(account_id)
