"""GDS 商品信息查询Service - 供进销存接口调用"""
import base64
import hashlib
import json
import os
import random
import re
import string
import threading

import requests
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "common", "gds_token.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0"

# OCR 实例全局复用（懒加载），避免每次登录重复加载模型
_OCR_INSTANCE = None
_OCR_LOCK = threading.Lock()


def _get_ocr():
    """获取全局 OCR 实例（懒加载单例）"""
    global _OCR_INSTANCE
    if _OCR_INSTANCE is None:
        with _OCR_LOCK:
            if _OCR_INSTANCE is None:
                LOG.info("[GDS] 首次初始化OCR模型（约数秒）...")
                _ensure_dll()
                import ddddocr
                _OCR_INSTANCE = ddddocr.DdddOcr(show_ad=False)
                LOG.info("[GDS] OCR模型初始化完成")
    return _OCR_INSTANCE


def _ensure_dll():
    """显式添加 onnxruntime 的 DLL 搜索路径，解决服务进程 DLL 加载失败问题"""
    try:
        import onnxruntime.capi
        capi_dir = os.path.dirname(onnxruntime.capi.__file__)
        if os.path.exists(os.path.join(capi_dir, "onnxruntime.dll")):
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(capi_dir)
            else:
                os.environ["PATH"] = capi_dir + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        LOG.warning("[GDS] 添加onnxruntime DLL路径失败: %s", e)


def _gen_pkce():
    """生成 PKCE 验证码"""
    cv = ''.join(random.choices(string.ascii_letters + string.digits + '-._~', k=64))
    cc = base64.urlsafe_b64encode(hashlib.sha256(cv.encode()).digest()).rstrip(b'=').decode()
    return cv, cc


def _get_cached_token():
    """读取缓存的 token"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                return json.load(f).get("token", "")
    except Exception as e:
        LOG.warning("[GDS] 读取缓存token失败: %s", e)
    return ""


def _save_token(token):
    """缓存 token"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"token": token}, f)
    except Exception as e:
        LOG.warning("[GDS] 保存token失败: %s", e)


def gds_login():
    """GDS 登录，返回 access_token，失败返回 None"""
    sess = requests.Session()
    for attempt in range(30):
        LOG.info("[GDS] 登录尝试第 %d 次", attempt + 1)
        try:
            # 1. 获取 CSRF Token
            r = sess.get("https://passport.gds.org.cn/Account/Login", headers={"User-Agent": UA}, timeout=15)
            r.encoding = 'utf-8'
            m = re.search(r'__RequestVerificationToken["\'].*?value=["\']([^"\']+)', r.text)
            csrf = m.group(1) if m else ""

            # 2. 获取验证码
            cap = sess.get(
                "https://passport.gds.org.cn/Account/Captcha",
                headers={"User-Agent": UA, "Referer": "https://passport.gds.org.cn/Account/Login"},
                timeout=15,
            ).json()

            # 3. OCR 识别验证码（复用全局实例，避免重复加载模型）
            vcode = _get_ocr().classification(base64.b64decode(cap["Base64"])).strip()

            # 4. 提交登录
            r2 = sess.post(
                "https://passport.gds.org.cn/Account/Login",
                data={
                    "ReturnUrl": "", "Type": "account", "Button": "login", "data": "",
                    "username": "jiasirui888", "password": "huarui0123A?",
                    "phone": "", "phoneVer": "", "barCode": "", "passwordBar": "",
                    "codekey": cap["Id"], "verCode": vcode, "__RequestVerificationToken": csrf,
                },
                headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                         "X-Requested-With": "XMLHttpRequest", "Origin": "https://passport.gds.org.cn"},
                timeout=15,
            )
            d = r2.json()
            if d.get('Code') != 1 or d.get('Msg') != 'Success':
                LOG.warning("[GDS] 登录失败: %s", d.get('Msg', '未知错误'))
                continue

            # 5. PKCE 授权码流程
            cv, cc = _gen_pkce()
            r3 = sess.get(
                "https://passport.gds.org.cn/connect/authorize",
                params={
                    "client_id": "vuejs_code_client", "redirect_uri": "https://www.gds.org.cn/#/callback",
                    "response_type": "code", "scope": "openid profile api1 offline_access",
                    "state": "state123", "code_challenge": cc, "code_challenge_method": "S256", "response_mode": "query",
                },
                headers={"User-Agent": UA}, allow_redirects=False, timeout=15,
            )
            mc = re.search(r'code=([A-F0-9]+)', r3.headers.get("Location", ""))
            if not mc:
                LOG.warning("[GDS] 未获取到授权码，重试")
                continue

            # 6. 换取 access_token
            r4 = sess.post(
                "https://passport.gds.org.cn/connect/token",
                data={
                    "client_id": "vuejs_code_client", "grant_type": "authorization_code",
                    "code": mc.group(1), "redirect_uri": "https://www.gds.org.cn/#/callback", "code_verifier": cv,
                },
                headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            tj = r4.json()
            if "access_token" in tj:
                _save_token(tj["access_token"])
                LOG.info("[GDS] access_token 获取成功")
                return tj["access_token"]
            LOG.warning("[GDS] 获取 access_token 失败")
        except Exception as e:
            LOG.warning("[GDS] 登录异常: %s", e)
            continue

    LOG.error("[GDS] 登录失败，已达最大重试次数")
    return None


def gds_query_barcode(barcode):
    """根据条码查询 GDS 商品信息，返回 dict 或 None"""
    LOG.info("[GDS] 查询条码: %s", barcode)

    token = _get_cached_token()
    if not token:
        token = gds_login()
    if not token:
        return None

    search_item = "0" + barcode
    headers = {
        "User-Agent": UA, "Referer": "https://www.gds.org.cn/",
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "currentrole": "Mine", "Origin": "https://www.gds.org.cn",
    }

    try:
        # 搜索接口
        url = (f"https://bff.gds.org.cn/gds/searching-api/ProductService/ProductListByGTIN"
               f"?PageSize=30&PageIndex=1&SearchItem={search_item}")
        r = requests.get(url, headers=headers, timeout=15)
        r.encoding = 'utf-8'
        data = r.json()

        if data.get("Code") == 40000:
            LOG.warning("[GDS] token 已过期，重新登录")
            token = gds_login()
            if token:
                return gds_query_barcode(barcode)
            return None

        if data.get("Code") != 1 or not data.get("Data", {}).get("Items"):
            LOG.warning("[GDS] 未找到条码 %s", barcode)
            return None

        item = data["Data"]["Items"][0]
        item_id = item.get('base_id', '')
        result = {
            "barcode": barcode,
            "name": item.get('keyword', ''),
            "brand": item.get('brandcn', ''),
            "manufacturer": item.get('firm_name', ''),
            "spec": item.get('specification', ''),
            "category": item.get('gpcname', ''),
        }

        # 详情接口补充信息
        if item_id:
            url = (f"https://bff.gds.org.cn/gds/searching-api/ProductService/ProductInfoByGTIN"
                   f"?gtin={search_item}&id={item_id}")
            r2 = requests.get(url, headers=headers, timeout=15)
            r2.encoding = 'utf-8'
            detail = r2.json()

            if detail.get("Code") == 1 and detail.get("Data", {}).get("Items"):
                items = detail["Data"]["Items"]
                if items:
                    # 国标信息
                    if items[0].get("ProductDetailsViewInfoNationalList"):
                        di = items[0]["ProductDetailsViewInfoNationalList"][0]
                        # 商品名优先用注册名称(RegulatedProductName)，品牌名作为品牌
                        reg_name = di.get('RegulatedProductName', '')
                        brand_name = di.get('BrandName', '')
                        if reg_name and str(reg_name).strip() not in ['', 'None']:
                            result["name"] = reg_name
                            result["reg_name"] = reg_name
                        else:
                            result["name"] = brand_name or result["name"]
                        result["brand"] = brand_name or result["brand"]
                        result["spec"] = di.get('NetContentStatement', result["spec"])
                        result["category"] = di.get('GlobalProductCategoryName', result["category"])
                        result["origin"] = di.get('CountryOfOriginCodeDescription', '')
                        result["gpc_code"] = di.get('GlobalProductCategoryCode', '')
                        result["product_type"] = di.get('ProductType', '')
                        nc = di.get('NetContent')
                        ncu = di.get('NetContentUnitofMeasureDescription', '')
                        if nc is not None and str(nc).strip() not in ['', '0', 'None']:
                            result["net_content"] = f"{nc} {ncu}".strip()
                        if di.get('ProductDescription'):
                            result["description"] = di.get('ProductDescription', '')
                        if di.get('ProductImageUrls'):
                            urls = [f"https://www.gds.org.cn{u['Url']}" for u in di['ProductImageUrls'] if u.get('Url')]
                            if urls:
                                result["image_url"] = urls[0]
                                result["image_count"] = len(urls)

                    # Studio 信息（厂商、尺寸、重量、使用说明等）
                    studio = items[0].get("ProductDetailsViewInfoStudio")
                    if studio:
                        result["manufacturer"] = studio.get('ManufacturerName', result["manufacturer"])
                        result["category"] = studio.get('GlobalProductCategoryName', result["category"])
                        result["spec"] = studio.get('NetContentStatement', result["spec"])
                        result["reg_name"] = studio.get('RegulatedProductName', result.get("reg_name", ''))

                        # 尺寸重量（过滤空值）
                        dim_map = {
                            "width": ("Width", "WidthUnitofMeasureDescription"),
                            "height": ("Height", "HeightUnitofMeasureDescription"),
                            "depth": ("DepthLength", "DepthUnitofMeasureDescription"),
                            "gross_weight": ("GrossWeight", "GrossWeightUnitofMeasureDescription"),
                            "net_weight": ("NetWeight", "NetWeightUnitofMeasureDescription"),
                        }
                        for key, (val_key, unit_key) in dim_map.items():
                            val = studio.get(val_key)
                            unit = studio.get(unit_key, '')
                            if val is not None and str(val).strip() not in ['', '0', 'None', '0.0']:
                                result[key] = f"{val} {unit}".strip()

                        # 其他可读字段
                        extra_fields = [
                            'PackagingTypeCodeDescription', 'RegulatoryPermitIdentification',
                            'CertificationStandard', 'ProductGrade', 'BrandOwnerName',
                            'ConsumerUsageInstructions', 'ConsumerStorageInstructions',
                            'WarningInformation', 'FeaturesandBenefits', 'AdditionalProductDescription',
                            'MinimumDaysofShelfLifefromProduction', 'SellingUnitofMeasureDescription',
                            'ModelNumber', 'SubBrandName', 'ProductTypeDescription',
                        ]
                        for f in extra_fields:
                            val = studio.get(f)
                            if val and str(val).strip() not in ['', 'None']:
                                result[f] = val
        LOG.info("[GDS] 条码 %s 查询完成，共获取 %d 个字段", barcode, len(result))
        return result
    except Exception as e:
        LOG.warning("[GDS] 查询异常: %s", e)
        return None
