"""云打印机服务

- 品牌注册表：每种品牌的字段定义（账号参数/设备字段）与打印实现
- 配置存储：t_mall_printer_config 每品牌一行，JSON 承载品牌差异字段
- 当前已实现品牌：feie（飞鹅），其他品牌仅注册占位

飞鹅 API: https://help.feieyun.com/home/doc/zh
"""
import hashlib
import json
import time
import uuid

import requests
from oslo_log import log as logging

from mall.db.engines.mysql import get_session
from mall.db.models.PrinterConfig.model import PrinterConfig

LOG = logging.getLogger(__name__)

# 飞鹅云 API 地址（表单方式 POST）
FEIE_API_URL = "https://api.feieyun.cn/Api/Open/"
APINAME_PRINT_MSG = "Open_printMsg"

# 密钥脱敏占位：前端保存时传该值表示"不修改原密钥"
MASKED_SECRET = "******"

# ==================== 品牌注册表 ====================
# config_fields: 账号参数表单定义; device_fields: 设备字段定义
BRANDS = [
    {
        "brand": "feie",
        "name": "飞鹅",
        "available": True,
        "configFields": [
            {"key": "user", "label": "开发者账号", "type": "text", "required": True},
            {"key": "ukey", "label": "开发者密钥", "type": "password", "required": True},
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


def _feie_request(config, sn, content):
    """调用飞鹅 Open_printMsg，返回解析后的 JSON"""
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
        result = _feie_request(config, sn, content)
        if result.get("ret") == 0:
            return {"success": True, "message": "打印指令已发送（订单号: {}）".format(result.get("data", ""))}
        return {"success": False, "message": "打印失败: {}".format(result.get("msg", "未知错误"))}

    return {"success": False, "message": "{} 品牌尚未接入".format(info["name"])}
