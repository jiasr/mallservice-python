"""配送履约业务逻辑层（聚合 DAO 与多渠道物流 Handler）

- 账号管理：列表 / 绑定（按渠道区分：微信调微信绑定，中通直接入库）/ 同步
- 发货：ship 按账号 provider 选择渠道；ship_by_wechat 走微信，ship_zto 走中通
- 轨迹：query_track 按渠道查询并格式化

注意：本文件是 service 层，禁止加 deco_catch_view_exception（规范一.5），
异常统一上抛，由 router 层装饰器捕获。
"""
import base64
import datetime
import json
import logging
import re
import time

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
    "p-o003": "暂无此电子面单账号下单权限(请至开放平台申请/绑定电子面单账号)",
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
    delivery_id = (data.get("deliveryId") or "").strip()
    # 沙盒测试账号(TEST 测试运力)无需、也不能在微信侧绑定, 直接入库即可
    if provider == "zto" or delivery_id.upper() == "TEST":
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

    # 微信物流沙盒环境(官方《网络快递沙盒环境指引》):
    # 账号的快递公司ID填 TEST 即走沙盒: 测试运力 TEST / 测试商户 test_biz_id /
    # service_type=1 + service_name=test_service_name; 且 openid 必须是小程序
    # 管理员/运营者/开发者(不能用下单买家的 openid), 每天限 10 次。
    delivery_id = acc.get('delivery_id') or ''
    biz_id = acc.get('biz_id') or ''
    is_sandbox = delivery_id.upper() == 'TEST'
    if is_sandbox:
        biz_id = biz_id or 'test_biz_id'
        sandbox_openid = (acc.get('sandbox_openid') or settings.get('sandbox_openid') or '').strip()
        if sandbox_openid:
            openid = sandbox_openid
        else:
            LOG.warning("沙盒下单未配置 sandbox_openid, 回退使用买家 openid, 可能被微信拒绝")
    # shop.img_url 为微信 add_order 必填: 缺失商品缩略图会报 9300535 invalid shop args。
    # 取值优先级: 订单商品图 -> 商品SPU主图(images JSON 第一张) -> 商城Logo 兜底。
    item_thumb = ''
    item_title = ''
    for it in items:
        if not item_title and it.title:
            item_title = it.title
        if not item_thumb and it.thumb:
            item_thumb = it.thumb
    if not item_thumb and items:
        from mall.db.models.Goods.model import GoodsSpu
        spu = session.query(GoodsSpu).filter(
            GoodsSpu.spu_id == items[0].spu_id).first()
        if spu and spu.images:
            try:
                imgs = json.loads(spu.images)
                if isinstance(imgs, list) and imgs:
                    first = imgs[0]
                    item_thumb = first if isinstance(first, str) else (first.get('url') or '')
            except Exception:
                item_thumb = ''
    if not item_thumb and settings.get('logo'):
        item_thumb = settings.get('logo')
    if item_thumb:
        from mall.db.engines.s3 import get_image_display_url
        item_thumb = get_image_display_url(item_thumb) or ''

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
        'item_thumb': item_thumb,
        'goods_name': item_title or '商品',
        'items': [{'name': it.title, 'quantity': it.quantity} for it in items],
    }
    config = {
        'delivery_id': delivery_id,
        'biz_id': biz_id,
        # 沙盒环境要求 service_type=1 且 service_name=test_service_name
        'service_type': 1 if is_sandbox else 0,
        'service_name': 'test_service_name' if is_sandbox else '',
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


# 微信运单状态码 -> 中文（batchgetorder 返回的 order_status：0正常 1取消）
WX_WAYBILL_STATE = {
    0: '正常',
    1: '已取消',
}

# 微信模拟更新订单状态（仅沙盒 TEST 运力可用）的轨迹类型
WX_TEST_ACTION_TYPES = {
    100001: '揽件成功',
    100002: '揽件失败',
    100003: '分配业务员',
    200001: '更新运输轨迹',
    300002: '开始派送',
    300003: '签收成功',
    300004: '签收失败',
    400001: '订单取消',
    400002: '订单滞留',
}


def list_waybills(params):
    """后台「运单管理」列表：系统已生成运单的订单

    支持按订单号 / 运单号 / 物流公司筛选；withWxStatus=1 时批量调用
    微信 order/batchget 拉取最新运单状态。
    """
    page_num = int(params.get('pageNum', 1))
    page_size = int(params.get('pageSize', 20))
    order_no = (params.get('orderNo') or '').strip()
    waybill_no = (params.get('waybillNo') or '').strip()
    company = (params.get('company') or '').strip()

    def _fmt(t):
        return t.strftime('%Y-%m-%d %H:%M:%S') if t else ''

    session = get_session()
    with session.begin():
        q = session.query(Order).filter(Order.deleted == 0, Order.shipping_no != '')
        if order_no:
            q = q.filter(Order.order_id.like('%{}%'.format(order_no)))
        if waybill_no:
            q = q.filter(Order.shipping_no.like('%{}%'.format(waybill_no)))
        if company:
            q = q.filter(Order.shipping_company.like('%{}%'.format(company)))
        total = q.count()
        rows = (
            q.order_by(Order.shipped_at.desc())
            .limit(page_size)
            .offset((page_num - 1) * page_size)
            .all()
        )
        items = []
        for o in rows:
            is_zto = (o.shipping_company or '') == '中通快递'
            items.append({
                'orderNo': o.order_id,
                # 下单给微信的 order_id 是自增主键, 批量查询/取消必须用同一个
                'innerId': str(o.id),
                'waybillNo': o.shipping_no or '',
                'company': o.shipping_company or '',
                'channel': '中通开放平台' if is_zto else ('微信物流助手' if o.waybill_data else '手动发货'),
                'consignee': o.consignee_name or '',
                'mobile': o.consignee_mobile or '',
                'address': o.consignee_address or '',
                'orderStatus': o.order_status,
                'shippedAt': _fmt(o.shipped_at),
                'isZto': is_zto,
                'hasWaybill': bool(o.waybill_data),
                'waybillState': '',
                'waybillStateDesc': '',
            })

    if items and str(params.get('withWxStatus')) in ('1', 'true', 'True'):
        _fill_wx_waybill_status(items)
    return {'data': {'total': total, 'list': items}}


def _fill_wx_waybill_status(items):
    """批量拉取微信渠道运单状态（每批 20 条），失败不影响列表返回"""
    targets = [i for i in items if i['waybillNo'] and i['hasWaybill'] and not i['isZto']]
    if not targets:
        return
    client = WechatExpressClient()
    for start in range(0, len(targets), 20):
        chunk = targets[start:start + 20]
        try:
            resp = client.batch_get_order(
                [{'order_id': c['innerId'], 'delivery_id': c['company']} for c in chunk]
            )
        except Exception as e:
            LOG.warning("批量查询微信运单状态失败: %s", e)
            continue
        rows = (resp or {}).get('order_list') or []
        state_map = {str(r.get('order_id')): r for r in rows}
        for c in chunk:
            r = state_map.get(c['innerId'])
            if not r:
                continue
            state = r.get('order_status')
            c['waybillState'] = state
            c['waybillStateDesc'] = WX_WAYBILL_STATE.get(state) or ('状态码 {}'.format(state))
            # print_html 为面单 HTML 的 base64，可用于补打；waybill_data 为面单附加信息
            c['printHtml'] = r.get('print_html') or ''
            c['waybillExtras'] = r.get('waybill_data') or []


def get_waybill_print(order_no):
    """获取可打印的电子面单内容（优先实时向渠道取）

    - 微信渠道: batchgetorder 返回的 print_html 是面单 HTML 的 base64, 解码后可直接打印;
      同时带出 waybill_data(大头笔等面单附加信息)
    - 中通渠道: 取下单时保存的面单图片 printImage
    """
    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_no).first()
        if not order:
            raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
        waybill_no = order.shipping_no or ''
        company = order.shipping_company or ''
        inner_id = str(order.id)
        local_raw = order.waybill_data or ''
    if not waybill_no:
        raise Fail("NO_WAYBILL", {}, "该订单没有运单号")
    if not local_raw:
        raise Fail("NO_WAYBILL_DATA", {}, "该订单没有电子面单数据（可能是手动发货）")

    if company == '中通快递':
        try:
            payload = json.loads(local_raw)
        except Exception:
            payload = {}
        return {
            'success': True, 'channel': 'zto', 'waybillNo': waybill_no,
            'printImage': (payload or {}).get('printImage') or '', 'html': '',
        }

    client = WechatExpressClient()
    try:
        resp = client.batch_get_order(
            [{'order_id': inner_id, 'delivery_id': company, 'waybill_id': waybill_no}])
    except Exception as e:
        raise Fail('WX_GET_PRINT_FAILED', {}, '获取微信面单失败：' + str(e))
    rows = (resp or {}).get('order_list') or []
    if not rows:
        raise Fail('WX_GET_PRINT_FAILED', {}, '微信未返回该运单的面单数据')
    row = rows[0]
    if str(row.get('errcode') or 0) != '0':
        raise Fail('WX_GET_PRINT_FAILED', {}, '微信返回错误[{}]: {}'.format(
            row.get('errcode'), row.get('errmsg') or '未知原因'))
    html = ''
    b64 = row.get('print_html') or ''
    if b64:
        try:
            html = base64.b64decode(b64).decode('utf-8')
        except Exception:
            html = ''
    return {
        'success': True, 'channel': 'wechat', 'waybillNo': waybill_no,
        'html': html, 'waybillExtras': row.get('waybill_data') or [],
    }


def test_update_waybill(order_no, action_type):
    """模拟更新微信运单状态（沙盒专用：delivery_id=TEST / biz_id=test_biz_id）

    官方文档《模拟更新订单状态》仅用于测试，不能用于真实运单。
    """
    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_no).first()
        if not order:
            raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
        waybill_no = order.shipping_no or ''
        company = order.shipping_company or ''
        inner_id = str(order.id)
    if not waybill_no:
        raise Fail("NO_WAYBILL", {}, "该订单没有运单号")
    if (company or '').upper() != 'TEST':
        raise Fail("NOT_SANDBOX_WAYBILL", {}, "仅沙盒 TEST 运力的运单支持模拟更新")
    try:
        action_type = int(action_type)
    except (TypeError, ValueError):
        raise Fail("INVALID_PARAM", {}, "轨迹类型不合法")
    if action_type not in WX_TEST_ACTION_TYPES:
        raise Fail("INVALID_PARAM", {}, "轨迹类型不合法：{}".format(action_type))

    client = WechatExpressClient()
    resp = client.test_update_order({
        'biz_id': 'test_biz_id',
        'order_id': inner_id,
        'delivery_id': 'TEST',
        'waybill_id': waybill_no,
        'action_time': int(time.time()),
        'action_type': action_type,
        'action_msg': WX_TEST_ACTION_TYPES[action_type],
    })
    if isinstance(resp, dict) and str(resp.get('errcode') or 0) != '0':
        raise Fail('WX_TEST_UPDATE_FAILED', {}, '模拟更新失败[{}]: {}'.format(
            resp.get('errcode'), resp.get('errmsg') or '未知原因'))
    return {'success': True, 'message': '已模拟：{}'.format(WX_TEST_ACTION_TYPES[action_type])}


def cancel_waybill(order_no, force=False):
    """撤销已发货订单的运单：先向渠道侧撤销，再本地回退为待发货

    force=True 时渠道撤销失败也不阻断，仅本地回滚（快递侧运单可能仍在，
    适用于测试单或快递侧已无法撤销的场景）。

    说明:
    - 仅处理已发货(order_status=2)且已有运单号的订单;
    - 系统下单生成的运单(waybill_data 非空)会先调渠道接口撤销; 手动发货(无面单数据)
      只做本地回退, 因为该运单并非由本系统向渠道下单;
    - 渠道明确返回失败时抛错, 不改写本地数据, 避免"本地已撤、快递侧仍在"。
    """
    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_no).first()
        if not order:
            raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
        if order.order_status != 2:
            raise Fail("ORDER_CANNOT_CANCEL_SHIP", {}, "仅已发货的订单可取消运单")
        waybill_no = order.shipping_no or ''
        company = order.shipping_company or ''
        waybill_data = order.waybill_data or ''
        # 下单给微信的 order_id 是自增主键(见 express_service), 取消必须用同一个,
        # 传订单号会找不到运单
        inner_id = str(order.id)
    if not waybill_no:
        raise Fail("NO_WAYBILL", {}, "该订单没有运单号，无需取消")

    if waybill_data and company == '中通快递':
        try:
            _cancel_zto_waybill(waybill_no)
            channel_msg = '中通运单已向开放平台撤销'
        except Fail as e:
            if not force:
                raise
            channel_msg = '中通撤销失败，已强制本地撤销：' + str(e)
    elif waybill_data and company:
        try:
            _cancel_wechat_waybill(inner_id, waybill_no, company)
            channel_msg = '运单已向微信物流助手撤销'
        except Fail as e:
            if not force:
                raise
            channel_msg = '微信撤销失败，已强制本地撤销：' + str(e)
    else:
        channel_msg = '手动发货订单，仅本地撤销'

    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_no).first()
        order.shipping_company = ''
        order.shipping_no = ''
        order.waybill_data = ''
        order.order_status = 1  # 回到待发货
        order.shipped_at = None
    LOG.info("订单 {} 运单 {} 已撤销, 恢复待发货".format(order_no, waybill_no))
    return {'success': True, 'message': '{}，订单已恢复为待发货'.format(channel_msg)}


def _cancel_wechat_waybill(order_no, waybill_no, delivery_id):
    """向微信物流助手撤销运单，失败时透出微信侧真实错误"""
    handler = LogisticsAdapter.get_handler('wechat')
    try:
        resp = handler.cancel_waybill(
            waybill_no, {'order_id': order_no, 'delivery_id': delivery_id})
    except WechatExpressError as e:
        raise Fail('WX_CANCEL_FAILED', {}, '微信取消运单失败：' + str(getattr(e, 'message', e)))
    except Fail:
        raise
    except Exception as e:
        raise Fail('WX_CANCEL_FAILED', {}, '微信取消运单失败：' + str(e))

    if isinstance(resp, dict):
        code = str(resp.get('result_code') or resp.get('errcode') or '')
        if code and code != '0':
            msg = resp.get('result_msg') or resp.get('errmsg') or '微信侧未给出原因'
            extra = []
            for k in ('delivery_resultcode', 'delivery_resultmsg'):
                if resp.get(k):
                    extra.append('{}={}'.format(k, resp[k]))
            raise Fail('WX_CANCEL_FAILED', {}, '微信取消运单失败[{}] {}{}'.format(
                code, msg, ('；' + '，'.join(extra)) if extra else ''))
        return True
    if resp is False:
        raise Fail('WX_CANCEL_FAILED', {}, '微信取消运单失败（运单可能已被揽收）')
    return True


def _cancel_zto_waybill(waybill_no):
    """向中通开放平台撤销运单"""
    accs = DeliveryAccountDao.list(1, 1, 1, 'zto')
    acc = (accs.get('list') or [{}])[0] if accs.get('list') else {}
    if not acc.get('app_key'):
        raise Fail('ZTO_ACCOUNT_NOT_FOUND', {}, '未配置可用的中通账号，无法向中通撤销运单')
    handler = LogisticsAdapter.get_handler('zto')
    resp = handler.cancel_waybill(waybill_no, {
        'app_key': acc.get('app_key'),
        'app_secret': _decrypt_password(acc.get('app_secret', '')),
        'env': acc.get('env', 'sandbox'),
        'partner_code': acc.get('partner_code'),
    })
    if isinstance(resp, dict) and resp.get('status') is False:
        status_code = resp.get('statusCode') or ''
        msg = resp.get('message') or '中通未返回撤销结果'
        raise Fail('ZTO_CANCEL_FAILED', {}, '中通取消运单失败({}): {}'.format(status_code, msg))
    return True


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
