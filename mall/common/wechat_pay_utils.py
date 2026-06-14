"""微信支付工具函数：签名、XML 转换"""
import hashlib
import random
import string
import time
import xml.etree.ElementTree as ET


def generate_nonce(length=32):
    """生成随机字符串"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_timestamp():
    """生成10位时间戳"""
    return str(int(time.time()))


def sign_md5(params, key):
    """微信 MD5 签名"""
    keys = sorted(params.keys())
    raw = '&'.join(['{}={}'.format(k, params[k]) for k in keys if params[k] != ''])
    raw += '&key=' + key
    return hashlib.md5(raw.encode('utf-8')).hexdigest().upper()


def dict_to_xml(params):
    """字典转 XML"""
    root = ET.Element('xml')
    for k, v in params.items():
        child = ET.SubElement(root, k)
        child.text = str(v)
    return ET.tostring(root, encoding='utf-8', method='xml').decode('utf-8')


def xml_to_dict(xml_str):
    """XML 转字典"""
    root = ET.fromstring(xml_str)
    return {child.tag: child.text for child in root}


def build_pay_sign(prepay_id, app_id, mch_key):
    """生成前端 wx.requestPayment 需要的签名参数"""
    params = {
        'appId':     app_id,
        'timeStamp': generate_timestamp(),
        'nonceStr':  generate_nonce(),
        'package':   'prepay_id=' + prepay_id,
        'signType':  'MD5',
    }
    params['paySign'] = sign_md5(params, mch_key)
    return params
