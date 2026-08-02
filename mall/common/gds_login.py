"""
GDS 条码查询工具 - 自动登录，返回 JSON 到 stdout
"""
import requests, re, json, os, base64, sys, hashlib, logging
from datetime import datetime

LOG = logging.getLogger(__name__)
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "gds_token.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0"


def _dump(method, url, resp, note=""):
    """打印请求 URL 和返回数据"""
    LOG.info("[GDS] >>> %s %s  %s", method, url, note)
    try:
        body = resp.text[:2000]
    except Exception:
        body = "<无法读取响应>"
    LOG.info("[GDS] <<< %s %s\n%s", method, url, body)


def gen_pkce():
    import random, string
    cv = ''.join(random.choices(string.ascii_letters + string.digits + '-._~', k=64))
    cc = base64.urlsafe_b64encode(hashlib.sha256(cv.encode()).digest()).rstrip(b'=').decode()
    return cv, cc


def do_login():
    LOG.info("[GDS] 开始登录流程")
    sess = requests.Session()
    for attempt in range(30):
        LOG.info("[GDS] 登录尝试第 %d 次", attempt + 1)

        # 1. 获取登录页 CSRF Token
        url = "https://passport.gds.org.cn/Account/Login"
        r = sess.get(url, headers={"User-Agent": UA})
        r.encoding = 'utf-8'
        _dump("GET", url, r)
        m = re.search(r'__RequestVerificationToken["\'].*?value=["\']([^"\']+)', r.text)
        csrf = m.group(1) if m else ""
        LOG.info("[GDS] CSRF Token 获取%s", "成功" if csrf else "失败")

        # 2. 获取验证码
        url = "https://passport.gds.org.cn/Account/Captcha"
        cap = sess.get(url, headers={"User-Agent": UA, "Referer": "https://passport.gds.org.cn/Account/Login"}).json()
        _dump("GET", url, type('obj', (object,), {'text': json.dumps(cap, ensure_ascii=False)})())
        LOG.info("[GDS] 验证码已获取")

        # 3. OCR 识别验证码
        import ddddocr
        vcode = ddddocr.DdddOcr(show_ad=False).classification(base64.b64decode(cap["Base64"])).strip()
        LOG.info("[GDS] 验证码识别结果: %s", vcode)

        # 4. 提交登录
        url = "https://passport.gds.org.cn/Account/Login"
        r2 = sess.post(url, data={
            "ReturnUrl": "", "Type": "account", "Button": "login", "data": "",
            "username": "jiasirui888", "password": "huarui0123A?",
            "phone": "", "phoneVer": "", "barCode": "", "passwordBar": "",
            "codekey": cap["Id"], "verCode": vcode, "__RequestVerificationToken": csrf
        }, headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                     "X-Requested-With": "XMLHttpRequest", "Origin": "https://passport.gds.org.cn"})
        _dump("POST", url, r2)
        d = r2.json()
        if d.get('Code') != 1 or d.get('Msg') != 'Success':
            LOG.warning("[GDS] 登录失败: %s", d.get('Msg', '未知错误'))
            continue
        LOG.info("[GDS] 账号密码登录成功")

        # 5. PKCE 授权码流程
        cv, cc = gen_pkce()
        url = "https://passport.gds.org.cn/connect/authorize"
        r3 = sess.get(url, params={
            "client_id": "vuejs_code_client", "redirect_uri": "https://www.gds.org.cn/#/callback",
            "response_type": "code", "scope": "openid profile api1 offline_access",
            "state": "state123", "code_challenge": cc, "code_challenge_method": "S256", "response_mode": "query"
        }, headers={"User-Agent": UA}, allow_redirects=False)
        _dump("GET", url, r3, f"Location={r3.headers.get('Location','')}")
        loc = r3.headers.get("Location", "")
        mc = re.search(r'code=([A-F0-9]+)', loc)
        if not mc:
            LOG.warning("[GDS] 未获取到授权码，重试")
            continue
        LOG.info("[GDS] 授权码获取成功")

        # 6. 换取 access_token
        url = "https://passport.gds.org.cn/connect/token"
        r4 = sess.post(url, data={
            "client_id": "vuejs_code_client", "grant_type": "authorization_code",
            "code": mc.group(1), "redirect_uri": "https://www.gds.org.cn/#/callback", "code_verifier": cv
        }, headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
        _dump("POST", url, r4)
        tj = r4.json()
        if "access_token" in tj:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({"token": tj["access_token"]}, f)
            LOG.info("[GDS] access_token 获取并缓存成功")
            return tj["access_token"]
        LOG.warning("[GDS] 获取 access_token 失败")

    LOG.error("[GDS] 登录失败，已达最大重试次数")
    return None


def query_barcode(barcode):
    LOG.info("[GDS] 开始查询条码: %s", barcode)
    log = {"barcode": barcode, "time": datetime.now().isoformat()}

    token = ""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            token = json.load(f).get("token", "")
        LOG.info("[GDS] 从缓存读取 token: %s", "存在" if token else "为空")
    else:
        LOG.info("[GDS] 本地 token 缓存不存在")

    if not token:
        LOG.info("[GDS] 需要重新登录获取 token")
        token = do_login()
    if not token:
        LOG.error("[GDS] 登录失败，无法查询条码")
        log["error"] = "登录失败"
        lines = [f"{k}: {v}" for k, v in log.items()]
        print("\n".join(lines))
        return

    search_item = "0" + barcode
    headers = {
        "User-Agent": UA, "Referer": "https://www.gds.org.cn/",
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "currentrole": "Mine", "Origin": "https://www.gds.org.cn"
    }

    url = (f"https://bff.gds.org.cn/gds/searching-api/ProductService/ProductListByGTIN"
           f"?PageSize=30&PageIndex=1&SearchItem={search_item}")
    LOG.info("[GDS] 调用商品搜索接口")
    r = requests.get(url, headers=headers, timeout=15)
    r.encoding = 'utf-8'
    _dump("GET", url, r)
    data = r.json()

    if data.get("Code") == 40000:
        LOG.warning("[GDS] token 已过期，重新登录")
        token = do_login()
        if token:
            return query_barcode(barcode)
        log["error"] = "登录失败"
        lines = [f"{k}: {v}" for k, v in log.items()]
        print("\n".join(lines))
        return

    if data.get("Code") != 1 or not data.get("Data", {}).get("Items"):
        LOG.warning("[GDS] 未找到条码 %s 对应的商品", barcode)
        log["error"] = "未找到"
        lines = [f"{k}: {v}" for k, v in log.items()]
        print("\n".join(lines))
        return

    item = data["Data"]["Items"][0]
    item_id = item.get('base_id', '')
    LOG.info("[GDS] 搜索到商品: %s, base_id=%s", item.get('keyword', ''), item_id)

    log["name"] = item.get('keyword', '')
    log["brand"] = item.get('brandcn', '')
    log["manufacturer"] = item.get('firm_name', '')
    log["spec"] = item.get('specification', '')
    log["category"] = item.get('gpcname', '')

    if item_id:
        url = (f"https://bff.gds.org.cn/gds/searching-api/ProductService/ProductInfoByGTIN"
               f"?gtin={search_item}&id={item_id}")
        LOG.info("[GDS] 调用商品详情接口")
        r2 = requests.get(url, headers=headers, timeout=15)
        r2.encoding = 'utf-8'
        _dump("GET", url, r2)
        detail = r2.json()

        if detail.get("Code") == 1 and detail.get("Data", {}).get("Items"):
            items = detail["Data"]["Items"]
            if items:
                if items[0].get("ProductDetailsViewInfoNationalList"):
                    di = items[0]["ProductDetailsViewInfoNationalList"][0]
                    log["name"] = di.get('BrandName', log["name"])
                    log["brand"] = di.get('BrandName', log["brand"])
                    log["spec"] = di.get('NetContentStatement', log["spec"])
                    log["category"] = di.get('GlobalProductCategoryName', log["category"])
                    log["origin"] = di.get('CountryOfOriginCodeDescription', '')
                    log["net_content"] = f"{di.get('NetContent', '')} {di.get('NetContentUnitofMeasureDescription', '')}".strip()
                    log["gpc_code"] = di.get('GlobalProductCategoryCode', '')
                    log["product_type"] = di.get('ProductType', '')
                    log["reg_name"] = di.get('RegulatedProductName', '')
                    if di.get('ProductDescription'):
                        log["description"] = di.get('ProductDescription', '')
                    if di.get('ProductImageUrls'):
                        urls = [f"https://www.gds.org.cn{u['Url']}" for u in di['ProductImageUrls'] if u.get('Url')]
                        if urls:
                            log["image"] = urls[0]
                            log["image_count"] = len(urls)

                studio = items[0].get("ProductDetailsViewInfoStudio")
                if studio:
                    log["manufacturer"] = studio.get('ManufacturerName', log["manufacturer"])
                    log["category"] = studio.get('GlobalProductCategoryName', log["category"])
                    log["spec"] = studio.get('NetContentStatement', log["spec"])
                    log["reg_name"] = studio.get('RegulatedProductName', log["reg_name"])

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
                            log[key] = f"{val} {unit}".strip()

                    for extra in ['PackagingTypeCodeDescription', 'RegulatoryPermitIdentification',
                                  'CertificationStandard', 'ProductGrade', 'BrandOwnerName',
                                  'ConsumerUsageInstructions', 'ConsumerStorageInstructions',
                                  'WarningInformation', 'FeaturesandBenefits',
                                  'AdditionalProductDescription', 'MinimumDaysofShelfLifefromProduction',
                                  'SellingUnitofMeasureDescription', 'ModelNumber', 'SubBrandName',
                                  'ProductTypeDescription', 'ManufacturerName']:
                        val = studio.get(extra)
                        if val and str(val).strip() not in ['', 'None']:
                            log[extra] = val
        else:
            LOG.warning("[GDS] 详情接口返回异常: Code=%s", detail.get("Code"))

    LOG.info("[GDS] 条码 %s 查询完成，共获取 %d 个字段", barcode, len(log))
    lines = [f"{k}: {v}" for k, v in log.items()]
    print("\n".join(lines))


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    if len(sys.argv) > 1:
        for bc in sys.argv[1:]:
            query_barcode(bc)
    else:
        print("用法: python gds_login.py <条码> [条码2 ...]")
