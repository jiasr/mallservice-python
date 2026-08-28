"""云打印机服务

- 品牌注册表：每种品牌的字段定义（账号参数/设备字段）与打印实现
- 配置存储：t_mall_printer_config 每品牌一行，JSON 承载品牌差异字段
- 打印流水：t_mall_print_log 记录每次打印状态（异步回调更新）
- 打印策略：默认设备 / 轮询（设备列表内轮流）
- 当前已实现品牌：feie（飞鹅），其他品牌仅注册占位

飞鹅 API: https://help.feieyun.com/home/doc/zh
"""
import hashlib
import json
import os
import time
import uuid

import requests
from oslo_log import log as logging

from mall.db.engines.mysql import get_session
from mall.db.models.PrinterConfig.model import PrinterConfig
from mall.db.models.PrintLog.model import PrintLog

LOG = logging.getLogger(__name__)

# 飞鹅云 API 地址（表单方式 POST）
FEIE_API_URL = "https://api.feieyun.cn/Api/Open/"
APINAME_PRINT_MSG = "Open_printMsg"

# 密钥脱敏占位：前端保存时传该值表示"不修改原密钥"
MASKED_SECRET = "******"

# 飞鹅回调验签公钥（从飞鹅平台下载，放置于 etc/mall/ 或容器 /app/etc/mall/）
FEIE_PUBLIC_KEY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', 'etc', 'mall', 'feie_public_key.pem')

# 轮询策略计数器（进程内，重启后从头轮）
_round_robin_index = 0

# ==================== 品牌注册表 ====================
# config_fields: 账号参数表单定义; device_fields: 设备字段定义
BRANDS = [
    {
        "brand": "feie",
        "name": "飞鹅",
        "available": True,
        "configFields": [
            {"key": "user", "label": "开发者账号", "type": "text", "required": True},
            {"key": "ukey", "label": "开发者密钥", "type": "text", "required": True},
        ],
        "deviceFields": [
            {"key": "sn", "label": "设备编号", "type": "text", "required": True},
            {"key": "key", "label": "设备KEY", "type": "text", "required": True},
            {"key": "name", "label": "备注名", "type": "text", "required": False},
        ],
    },
    {
        "brand": "xprinter",
        "name": "芯烨",
        "available": False,
        "configFields": [
            {"key": "user", "label": "开发者账号", "type": "text", "required": True},
            {"key": "ukey", "label": "开发者密钥", "type": "password", "required": True},
        ],
        "deviceFields": [
            {"key": "sn", "label": "设备编号", "type": "text", "required": True},
            {"key": "name", "label": "备注名", "type": "text", "required": False},
        ],
    },
]


def get_brands():
    """品牌列表（前端 Tab 页与动态表单的数据源）"""
    return [{"brand": b["brand"], "name": b["name"], "available": b["available"],
             "configFields": b["configFields"], "deviceFields": b["deviceFields"]}
            for b in BRANDS]


def _brand_info(brand):
    for b in BRANDS:
        if b["brand"] == brand:
            return b
    return None


def _mask_config(config, fields):
    """密钥类字段脱敏（返回掩码，避免明文回显）"""
    result = dict(config)
    for f in fields:
        if f["type"] == "password" and result.get(f["key"]):
            result[f["key"]] = MASKED_SECRET
    return result


def get_config(brand):
    """读取品牌配置（密钥脱敏）"""
    info = _brand_info(brand)
    if not info:
        return {"success": False, "message": "不支持的品牌: {}".format(brand)}

    session = get_session()
    with session.begin():
        row = session.query(PrinterConfig).filter(PrinterConfig.brand == brand).first()
        if not row:
            return {"success": True, "data": {
                "brand": brand, "name": info["name"], "enabled": False,
                "config": {}, "devices": [],
            }}
        try:
            config = json.loads(row.config_json) if row.config_json else {}
        except Exception:
            config = {}
        try:
            devices = json.loads(row.devices_json) if row.devices_json else []
        except Exception:
            devices = []
        return {"success": True, "data": {
            "brand": row.brand, "name": row.name or info["name"],
            "enabled": bool(row.enabled),
            "config": _mask_config(config, info["configFields"]),
            "devices": devices,
        }}


def save_config(brand, data):
    """保存品牌配置（config + devices + enabled 整体提交）

    密钥字段传 MASKED_SECRET 或空时保留原值（防止脱敏后保存把密钥清掉）。
    """
    info = _brand_info(brand)
    if not info:
        return {"success": False, "message": "不支持的品牌: {}".format(brand)}

    config = data.get("config") or {}
    devices = data.get("devices") or []
    enabled = bool(data.get("enabled", False))

    # 校验必填字段
    for f in info["configFields"]:
        if f["required"] and not config.get(f["key"]):
            return {"success": False, "message": "请填写{}".format(f["label"])}
    for dev in devices:
        for f in info["deviceFields"]:
            if f["required"] and not dev.get(f["key"]):
                return {"success": False, "message": "设备缺少{}: {}".format(f["label"], dev.get("sn", ""))}

    session = get_session()
    with session.begin():
        row = session.query(PrinterConfig).filter(PrinterConfig.brand == brand).first()
        if not row:
            row = PrinterConfig(
                id=uuid.uuid4().hex,
                brand=brand,
                name=info["name"],
                config_json=json.dumps(config, ensure_ascii=False),
                devices_json=json.dumps(devices, ensure_ascii=False),
                enabled=1 if enabled else 0,
            )
            session.add(row)
        else:
            # 密钥保留逻辑
            try:
                old_config = json.loads(row.config_json) if row.config_json else {}
            except Exception:
                old_config = {}
            for f in info["configFields"]:
                if f["type"] == "password":
                    val = config.get(f["key"])
                    if not val or val == MASKED_SECRET:
                        config[f["key"]] = old_config.get(f["key"], "")
            row.config_json = json.dumps(config, ensure_ascii=False)
            row.devices_json = json.dumps(devices, ensure_ascii=False)
            row.enabled = 1 if enabled else 0
    LOG.info("保存打印机配置成功: {}".format(brand))
    return {"success": True, "message": "保存成功"}


# ==================== 飞鹅实现 ====================

def _feie_sign(user, ukey, stime):
    """飞鹅签名: SHA1(user + UKEY + stime)，40 位小写"""
    raw = "{}{}{}".format(user, ukey, stime)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _feie_request(config, sn, content, backurl=''):
    """调用飞鹅 Open_printMsg，返回解析后的 JSON

    backurl 非空时飞鹅打印完成后会向该地址推送打印结果回调。
    """
    user = config.get("user", "")
    ukey = config.get("ukey", "")
    stime = str(int(time.time()))
    params = {
        "user": user,
        "stime": stime,
        "sig": _feie_sign(user, ukey, stime),
        "apiname": APINAME_PRINT_MSG,
        "sn": sn,
        "content": content,
        "times": 1,
    }
    if backurl:
        params["backurl"] = backurl
    try:
        resp = requests.post(FEIE_API_URL, data=params, timeout=10)
        return resp.json()
    except Exception as e:
        LOG.error("飞鹅API请求失败: {}".format(e))
        return {"ret": -1, "msg": "请求飞鹅服务失败: {}".format(e)}


def test_print(brand, sn):
    """发送测试打印内容到指定设备"""
    info = _brand_info(brand)
    if not info:
        return {"success": False, "message": "不支持的品牌: {}".format(brand)}
    if not info["available"]:
        return {"success": False, "message": "{} 品牌尚未接入".format(info["name"])}

    session = get_session()
    with session.begin():
        row = session.query(PrinterConfig).filter(PrinterConfig.brand == brand).first()
        if not row:
            return {"success": False, "message": "请先保存{}配置".format(info["name"])}
        try:
            config = json.loads(row.config_json) if row.config_json else {}
        except Exception:
            config = {}

    if not config.get("user") or not config.get("ukey"):
        return {"success": False, "message": "请先配置{}账号和密钥".format(info["name"])}

    if brand == "feie":
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        content = "<CB>飞鹅打印测试</CB><BR>"
        content += "<L>打印机连接正常</L><BR>"
        content += "<L>测试时间：{}</L><BR>".format(now)
        content += "<BR><L>商城订单小票打印对接成功</L><BR>"
        result = _feie_request(config, sn, content, backurl=config.get("backurl", ""))
        if result.get("ret") == 0:
            _write_log(order_no='', biz_type=2, sn=sn,
                       feie_order_id=result.get("data", ""), status=0)
            return {"success": True, "message": "打印指令已发送（订单号: {}）".format(result.get("data", ""))}
        return {"success": False, "message": "打印失败: {}".format(result.get("msg", "未知错误"))}

    return {"success": False, "message": "{} 品牌尚未接入".format(info["name"])}


# ==================== 打印流水 ====================

def _write_log(order_no, biz_type, sn, feie_order_id, status, message=''):
    """写入打印流水"""
    session = get_session()
    with session.begin():
        session.add(PrintLog(
            id=uuid.uuid4().hex,
            order_no=order_no or '',
            biz_type=biz_type,
            printer_sn=sn or '',
            feie_order_id=feie_order_id or '',
            status=status,
            message=message or '',
        ))


def get_last_ticket_log(order_no):
    """订单最近一次小票打印流水（无则返回 None）"""
    session = get_session()
    with session.begin():
        return session.query(PrintLog).filter(
            PrintLog.order_no == order_no, PrintLog.biz_type == 1
        ).order_by(PrintLog.create_time.desc()).first()


def has_ticket_printed(order_no):
    """订单是否已有受理/成功的小票打印（自动打印防重用）"""
    log = get_last_ticket_log(order_no)
    return log is not None and log.status in (0, 1)


def get_orders_ticket_status(order_nos):
    """批量查询订单最近一次小票打印状态

    返回 {orderNo: {'status': 状态, 'createTime': 最近打印时间}}，无记录的不在结果中。
    用于订单列表合并展示（避免每个订单单独查一次）。
    """
    order_nos = [n for n in (order_nos or []) if n]
    if not order_nos:
        return {}
    session = get_session()
    with session.begin():
        rows = session.query(PrintLog).filter(
            PrintLog.order_no.in_(order_nos), PrintLog.biz_type == 1
        ).order_by(PrintLog.create_time.desc()).all()
    result = {}
    for r in rows:
        if r.order_no not in result:
            result[r.order_no] = {
                'status': r.status,
                'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else '',
            }
    return result


def is_feie_printable():
    """飞鹅小票打印是否已启用且可出票

    判断逻辑与 _auto_print_after_pay / print_ticket 保持一致：
    配置存在 + enabled 开启 + 至少一台可用设备。
    返回 True 表示订单小票可以打印；False 表示小票机未配置/未启用。
    """
    session = get_session()
    with session.begin():
        row = session.query(PrinterConfig).filter(PrinterConfig.brand == 'feie').first()
        if not row or not row.enabled:
            return False
        try:
            devices = json.loads(row.devices_json) if row.devices_json else []
        except Exception:
            devices = []
    if not devices:
        return False
    # 至少一台状态启用(status!=0)的设备
    return any(d.get('status', 1) for d in devices)


def list_logs(order_no='', status='', page_num=1, page_size=10):
    """打印流水分页查询（订单打印记录/设置页共用）

    支持订单号模糊筛选、状态筛选（-1=未打印 0=已提交 1=打印成功 2=打印失败）。
    """
    session = get_session()
    with session.begin():
        q = session.query(PrintLog)
        if order_no:
            q = q.filter(PrintLog.order_no.like('%' + order_no + '%'))
        if status != '' and status is not None and str(status).isdigit():
            q = q.filter(PrintLog.status == int(status))
        total = q.count()
        q = q.order_by(PrintLog.create_time.desc()).limit(page_size).offset((page_num - 1) * page_size)
        rows = q.all()
        items = [{
            'id': r.id,
            'orderNo': r.order_no,
            'bizType': r.biz_type,
            'printerSn': r.printer_sn,
            'feieOrderId': r.feie_order_id,
            'status': r.status,
            'message': r.message,
            'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else '',
        } for r in rows]
    return {'success': True, 'data': {'total': total, 'list': items}}


# ==================== 打印策略 ====================

def _pick_device(config, devices, sn=''):
    """按策略选择打印设备，返回设备 dict（无可用设备返回 None）

    - 指定 sn：直接用该设备（手动指定/补打）
    - printStrategy=round_robin：设备列表轮流
    - 其他（default/空）：默认设备 defaultSn，未设置则取第一台
    """
    global _round_robin_index
    enabled = [d for d in devices if d.get('status', 1)]
    if not enabled:
        return None
    if sn:
        for d in enabled:
            if d.get('sn') == sn:
                return d
        return None
    strategy = config.get('printStrategy', 'default')
    if strategy == 'round_robin':
        d = enabled[_round_robin_index % len(enabled)]
        _round_robin_index += 1
        return d
    default_sn = config.get('defaultSn', '')
    for d in enabled:
        if d.get('sn') == default_sn:
            return d
    return enabled[0]


# ==================== 小票排版 ====================

LINE = "--------------------------------"  # 57mm: 32 字符分隔线


def _fen_to_yuan(fen):
    """分 → 元，保留两位小数（订单金额字段单位均为分）"""
    return (fen or 0) / 100.0


# 订单状态中文映射（与前端 print.vue 保持一致）
_ORDER_STATUS_NAMES = {0: '待付款', 1: '待发货', 2: '待收货', 3: '已完成', 4: '已取消'}
# 支付方式中文映射
_PAYMENT_NAMES = {'wechat': '微信支付', '': '未支付'}


def _status_name(status):
    return _ORDER_STATUS_NAMES.get(status, '未知')


def _payment_name(method):
    return _PAYMENT_NAMES.get(method) or method or '未支付'


def build_ticket_content(order, shop):
    """订单小票打印内容（57mm 热敏，飞鹅标签语法）

    与前端 print.vue 预览保持一致，实现所见即所得。
    order: _format_admin_order 返回的订单 dict（金额单位：分）
    shop: 店铺信息 dict(name/phone/email)
    """
    lines = []
    # ===== 店铺头部 =====
    lines.append("<C>{}</C>".format(shop.get('name', '商城')))
    if shop.get('phone'):
        lines.append("<C>电话: {}</C>".format(shop.get('phone')))
    lines.append(LINE)
    # ===== 订单信息 =====
    lines.append("<L>订单号: {}</L>".format(order.get('orderNo', '')))
    if order.get('createTime'):
        lines.append("<L>下单时间: {}</L>".format(order.get('createTime')))
    if order.get('paidAt'):
        lines.append("<L>支付时间: {}</L>".format(order.get('paidAt')))
    lines.append("<L>订单状态: {}</L>".format(_status_name(order.get('status'))))
    lines.append("<L>支付方式: {}</L>".format(_payment_name(order.get('paymentMethod'))))
    if order.get('shippingNo'):
        lines.append("<L>物流: {} {}</L>".format(
            order.get('shippingCompany') or '', order.get('shippingNo')))
    lines.append(LINE)
    # ===== 商品明细（单行紧凑排版） =====
    for it in order.get('orderItemList', []):
        title = it.get('title', '')
        barcode = it.get('barcode', '')
        spec = ''
        specs = it.get('specInfo') or []
        if specs and specs[0].get('specValue'):
            spec = '({})'.format(specs[0]['specValue'])
        name = (barcode + '|' if barcode else '') + title + spec
        qty = it.get('quantity', 0)
        subtotal = _fen_to_yuan(it.get('subtotal'))
        # 名称 + 数量 + 小计压缩为一行（长名称自动换行）
        lines.append("<L>{} x{}  ¥{:.2f}</L>".format(name, qty, subtotal))
    lines.append(LINE)
    # ===== 金额汇总 =====
    lines.append("<L>商品金额: {:.2f}</L>".format(_fen_to_yuan(order.get('goodsAmount'))))
    lines.append("<L>运费: {:.2f}</L>".format(_fen_to_yuan(order.get('freightAmount'))))
    if (order.get('discountAmount') or 0) > 0:
        lines.append("<L>优惠: -{:.2f}</L>".format(_fen_to_yuan(order.get('discountAmount'))))
    lines.append("<L>实付金额: ¥{:.2f}</L>".format(_fen_to_yuan(order.get('payAmount'))))
    lines.append(LINE)
    # ===== 收货信息 =====
    consignee = order.get('consignee', '')
    phone = order.get('phone', '')
    if consignee or phone:
        lines.append("<L>收货人: {} {}</L>".format(consignee, phone))
    if order.get('address'):
        lines.append("<L>收货地址: {}</L>".format(order['address']))
    if order.get('remark'):
        lines.append("<L>备注: {}</L>".format(order['remark']))
    lines.append(LINE)
    # ===== 页脚 =====
    lines.append("<C>谢谢惠顾，欢迎再次光临！</C>")
    lines.append("<L>打印时间: {}</L>".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    # ===== 订单号二维码（飞鹅<QR>固定底部居中，内容为订单号，供门店PDA扫码） =====
    order_no = order.get('orderNo', '')
    if order_no:
        lines.append("<QR>{}</QR>".format(order_no))
    lines.append("<BR>")
    return "<BR>".join(lines)


# ==================== 打印入口 ====================

def print_ticket(order_no, sn=''):
    """打印订单小票（手动/自动共用入口）

    流程：查订单 → 生成 content → 策略选设备 → 飞鹅提交 → 写流水
    """
    from mall.db.models.Order.sql import OrderDao
    data = OrderDao.admin_print(order_no)
    if not data.get('success'):
        return data
    order = data['data']['order']
    shop = data['data']['shop']

    session = get_session()
    with session.begin():
        row = session.query(PrinterConfig).filter(PrinterConfig.brand == 'feie').first()
        if not row:
            return {"success": False, "message": "请先在[系统设置-小票机]配置飞鹅"}
        try:
            config = json.loads(row.config_json) if row.config_json else {}
        except Exception:
            config = {}
        try:
            devices = json.loads(row.devices_json) if row.devices_json else []
        except Exception:
            devices = []

    if not config.get('user') or not config.get('ukey'):
        return {"success": False, "message": "请先配置飞鹅开发者账号和密钥"}
    device = _pick_device(config, devices, sn)
    if not device:
        return {"success": False, "message": "未找到可用打印设备，请先在[系统设置-小票机]添加并启用设备"}

    content = build_ticket_content(order, shop)
    result = _feie_request(config, device.get('sn', ''), content,
                           backurl=config.get('backurl', ''))
    if result.get('ret') == 0:
        _write_log(order_no=order_no, biz_type=1, sn=device.get('sn', ''),
                   feie_order_id=result.get('data', ''), status=0,
                   message="已提交飞鹅受理")
        return {"success": True, "message": "打印指令已发送"}
    _write_log(order_no=order_no, biz_type=1, sn=device.get('sn', ''),
               feie_order_id='', status=2,
               message="飞鹅受理失败: {}".format(result.get('msg', '未知错误')))
    return {"success": False, "message": "打印失败: {}".format(result.get('msg', '未知错误'))}


# ==================== 飞鹅打印结果回调 ====================

def handle_verify_file(filename):
    """飞鹅域名验证文件响应

    飞鹅平台要求回调地址所在目录可访问验证文件 feieyun_verify_xxx.txt：
    https://域名/v1/printer/callback/feieyun_verify_xxx.txt
    文件名中的随机串在飞鹅配置 verifyToken 中维护，验证内容即 token 本身，
    无需手动上传文件；token 未配置或文件名不匹配时返回 None（404）。
    """
    session = get_session()
    with session.begin():
        row = session.query(PrinterConfig).filter(PrinterConfig.brand == 'feie').first()
        if not row:
            return None
        try:
            config = json.loads(row.config_json) if row.config_json else {}
        except Exception:
            config = {}
    token = config.get('verifyToken', '')
    scan_token = config.get('scanVerifyToken', '')
    for t in (token, scan_token):
        if t and filename == 'feieyun_verify_{}.txt'.format(t):
            return t
    return None


def handle_scan_callback(params, remote_ip=''):
    """处理飞鹅扫码数据回调

    扫码一体机/带扫码枪打印机扫码后，飞鹅按平台配置的扫码回调地址推送数据。
    当前记录完整参数日志（格式以飞鹅实际推送为准），立即返回 SUCCESS 防止重推；
    后续如需业务处理（如扫码查库存/自动补打）在此扩展。
    """
    LOG.info("收到飞鹅扫码回调: 来源IP={}, 参数={}".format(remote_ip or '未知', params))
    return "SUCCESS"


def _verify_callback_sign(params):
    """飞鹅回调验签：SHA256WithRSA，公钥文件不存在时跳过验签并告警"""
    if not os.path.exists(FEIE_PUBLIC_KEY_FILE):
        LOG.warning("飞鹅回调公钥不存在({}), 本次回调跳过验签，请下载公钥放置该路径".format(FEIE_PUBLIC_KEY_FILE))
        return True
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        sign = params.pop('sign', '')
        items = sorted((k, v) for k, v in params.items() if v not in (None, ''))
        raw = "&".join("{}={}".format(k, v) for k, v in items)
        with open(FEIE_PUBLIC_KEY_FILE, 'rb') as f:
            pub_key = serialization.load_pem_public_key(f.read())
        pub_key.verify(
            __import__('base64').b64decode(sign),
            raw.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256())
        return True
    except Exception as e:
        LOG.error("飞鹅回调验签失败: {}".format(e))
        return False


def handle_print_callback(params, remote_ip=''):
    """处理飞鹅打印结果回调

    飞鹅 POST 表单: orderId/status/stime/sign，需立即返回 SUCCESS，否则 5 秒后重推。
    """
    order_id = (params or {}).get('orderId', '')
    status = (params or {}).get('status', '')
    stime = (params or {}).get('stime', '')
    sign = (params or {}).get('sign', '')
    LOG.info("收到飞鹅打印结果回调: orderId={}, status={}, stime={}, 来源IP={}, 签名前16位={}".format(
        order_id, status, stime or '无', remote_ip or '未知', sign[:16] if sign else '无'))
    if not order_id:
        LOG.warning("飞鹅回调缺少 orderId 参数，忽略本次回调（可能是飞鹅平台测试推送）: 完整参数={}".format(params))
        return "SUCCESS"

    if not _verify_callback_sign(dict(params)):
        LOG.error("飞鹅回调验签失败，拒绝更新打印状态: orderId={}, status={}".format(order_id, status))
        return "SUCCESS"

    session = get_session()
    with session.begin():
        log = session.query(PrintLog).filter(
            PrintLog.feie_order_id == order_id).first()
        if not log:
            LOG.warning("飞鹅回调找不到对应打印流水，忽略: orderId={}, status={}（流水可能已被清理，或该任务不是本系统发起的打印）".format(order_id, status))
            return "SUCCESS"
        old_status = log.status
        order_no = log.order_no
        printer_sn = log.printer_sn
        biz_type = log.biz_type
        LOG.info("飞鹅回调匹配到打印流水: orderId={}, 订单={}, 设备SN={}, 业务类型={}, 变更前状态={}".format(
            order_id, order_no, printer_sn, biz_type, old_status))
        if str(status) == '1':
            log.status = 1
            log.message = "打印成功"
            new_status = 1
        else:
            log.status = 2
            log.message = "飞鹅回调状态: {}".format(status)
            new_status = 2
        if old_status == new_status:
            LOG.info("飞鹅回调重复推送，状态未变化: orderId={}, 订单={}, 状态={}".format(order_id, order_no, new_status))
        else:
            LOG.info("飞鹅回调更新打印状态完成: orderId={}, 订单={}, 状态 {}→{}".format(
                order_id, order_no, old_status, new_status))
    return "SUCCESS"
