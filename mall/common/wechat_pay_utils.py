"""微信支付 APIv3 工具函数：RSA 签名、AES-GCM 解密、JSON 交互"""

import json
import time
import random
import string
import base64
import logging as py_logging

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_private_key

LOG = py_logging.getLogger(__name__)


def generate_nonce(length=32):
    """生成随机字符串"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_timestamp():
    """生成10位秒级时间戳"""
    return str(int(time.time()))


def load_private_key(private_key_content: str):
    """加载 PEM 格式的商户 API 私钥"""
    return load_pem_private_key(private_key_content.encode('utf-8'), password=None)


def sign_rsa(message: str, private_key) -> str:
    """RSA-SHA256 签名，返回 Base64 编码结果"""
    signature = private_key.sign(
        message.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')


def build_authorization(method: str, url: str, body: str,
                        mchid: str, cert_serial_no: str,
                        private_key) -> str:
    """构建 APIv3 HTTP 请求的 Authorization 头"""
    nonce_str = generate_nonce()
    timestamp = generate_timestamp()
    message = f"{method}\n{url}\n{timestamp}\n{nonce_str}\n{body}\n"
    signature = sign_rsa(message, private_key)
    return (
        f'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{mchid}",'
        f'nonce_str="{nonce_str}",'
        f'signature="{signature}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{cert_serial_no}"'
    )


def build_jsapi_pay_sign(app_id: str, timestamp: str, nonce_str: str,
                         prepay_id: str, private_key) -> dict:
    """构建前端 wx.requestPayment / WeixinJSBridge 调起支付参数 (signType=RSA)

    Returns:
        dict: {appId, timeStamp, nonceStr, package, signType, paySign}
    """
    message = f"{app_id}\n{timestamp}\n{nonce_str}\nprepay_id={prepay_id}\n"
    pay_sign = sign_rsa(message, private_key)
    return {
        'appId': app_id,
        'timeStamp': timestamp,
        'nonceStr': nonce_str,
        'package': f'prepay_id={prepay_id}',
        'signType': 'RSA',
        'paySign': pay_sign,
    }


def decrypt_aes_gcm(ciphertext_b64: str, nonce_b64: str,
                    associated_data_b64: str, apiv3_key: str) -> dict:
    """使用 APIv3 密钥解密回调通知中的 resource 密文

    Returns:
        dict: 解密后的 JSON 业务数据
    """
    key = apiv3_key.encode('utf-8')
    nonce = nonce_b64.encode('utf-8')
    ad = associated_data_b64.encode('utf-8')
    ciphertext = base64.b64decode(ciphertext_b64.encode('utf-8'))
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, ad)
    return json.loads(plaintext.decode('utf-8'))
