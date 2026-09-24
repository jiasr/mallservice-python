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
from mall.db.models.User.model import User
from mall.db.models.DeliveryAccount.sql import DeliveryAccountDao, _decrypt_password
from mall.common.wechat_express_utils import WechatExpressClient, WechatExpressError
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
    - 散单(isCash=1): 微信侧无需且【不能】绑定——散单未签约月结账号, 调 bindAccount 会报
      9300531 invalid biz_id or password。散单直接用微信下发的现付编码 cash_biz_id 下单,
      因此跳过微信绑定仅入库。
    """
    provider = data.get("provider", "wechat")
    if provider == "zto":
        return DeliveryAccountDao.create(data)
    client = WechatExpressClient()
    delivery_id = (data.get('deliveryId') or '').strip()
    biz_id = (data.get('bizId') or '').strip()
    is_cash = str(data.get('isCash', 0)) in ('1', 'true', 'True')
    if not delivery_id:
        raise Fail("INVALID_PARAM", {}, "微信渠道需填写快递公司ID")
    if is_cash:
        # 客户编码留空时自动取微信「支持的快递公司列表」里的现付编码, 不用查文档手填
        if not biz_id:
            biz_id = client.find_cash_biz_id(delivery_id)
        if not biz_id:
            raise Fail(
                "WX_CASH_NOT_SUPPORTED", {},
                "{} 不支持散单(现付)，请改选月结账号，或手动填写该公司的现付 biz_id".format(delivery_id),
            )
        data['deliveryId'] = delivery_id
        data['bizId'] = biz_id
        data['isCash'] = 1
        return DeliveryAccountDao.create(data)
    if not biz_id:
        raise Fail("INVALID_PARAM", {}, "微信渠道需填写客户编码(biz_id)")
    try:
        client.bind_account(
            delivery_id=delivery_id,
            biz_id=biz_id,
            password=(data.get('password') or '').strip(),
            remark_content=data.get('accountName', ''),
            action="bind",
        )
    except Fail:
        raise
    except WechatExpressError as e:
        # 异常已含「错误码 + 英文原文 + 中文说明」，直接透传，避免前缀重复
        raise Fail("WX_EXPRESS_BIND_FAILED", {}, e.message)
    except Exception as e:
        raise Fail("WX_EXPRESS_BIND_FAILED", {}, "微信物流绑定失败：" + str(e))
    data['deliveryId'] = delivery_id
    data['bizId'] = biz_id
    return DeliveryAccountDao.create(data)


def sync_accounts():
    """从微信同步已绑定的物流账号"""
    client = WechatExpressClient()
    accounts = client.get_all_accounts()
    return DeliveryAccountDao.upsert_from_wechat(accounts)


def list_deliveries():
    """获取微信物流助手支持的快递公司列表(用于发货/绑定账号时下拉选择)

    返回微信原结构列表, 每项含 delivery_id / delivery_name / can_use_cash /
    can_get_quota / service_type[{service_type, service_name}] / cash_biz_id
    """
    client = WechatExpressClient()
    try:
        return client.get_all_delivery()
    except Fail:
        raise
    except WechatExpressError as e:
        raise Fail("WX_EXPRESS_DELIVERY_LIST_FAILED", {}, e.message)
    except Exception as e:
        raise Fail("WX_EXPRESS_DELIVERY_LIST_FAILED", {}, "获取快递公司列表失败：" + str(e))


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
    # openid: 微信 addOrder 在 add_source=0(小程序订单) 时必填, 取下单用户的 wx_openid
    openid = ''
    if order.user_id:
        user = session.query(User).filter(User.id == order.user_id).first()
        openid = (user.wx_openid if user else '') or ''
    # 收/发件人省市区需分字段传, 全为空会导致快递侧区域匹配失败
    r_prov, r_city, r_area = _split_addr(order.consignee_address)
    sender_address = settings.get('sender_address') or settings.get('site_name', '')
    s_prov, s_city, s_area = _split_addr(sender_address)
    order_dict = {
        'id': order.id,
        'consignee': order.consignee_name,
        'tel': order.consignee_mobile,
        'province': r_prov, 'city': r_city, 'area': r_area,
        'address': order.consignee_address,
        'remark': order.remark,
        'total_quantity': total_qty,
        'openid': openid,
        'items': [{'name': it.title, 'quantity': it.quantity} for it in items],
    }
    config = {
        'delivery_id': acc['delivery_id'],
        'biz_id': acc['biz_id'],
        # 散单(现付)账号: 下单需额外传 expect_time, 否则顺丰不会有收件员上门
        'is_cash': acc.get('is_cash') == 1,
        'sender_name': settings.get('site_name', ''),
        'sender_tel': settings.get('service_phone', ''),
        'sender_province': s_prov, 'sender_city': s_city, 'sender_area': s_area,
        'sender_address': sender_address,
    }
    handler = LogisticsAdapter.get_handler('wechat')
    try:
        result = handler.create_waybill(order_dict, config)
    except Fail:
        raise
    except WechatExpressError as e:
        # 必须转成 Fail：否则被 router 兜成 result_error，前端只看到"请求失败"，
        # 看不到微信错误码与快递侧返回码（9300501 的真实原因就在 delivery_resultmsg 里）
        raise Fail('WX_CREATE_ORDER_FAILED', {}, e.message)
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
