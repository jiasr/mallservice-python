"""微信小程序 access_token 获取与缓存（client_credential 方式）

供微信物流助手、手机号获取等需要 access_token 的服务端接口复用。
缓存采用内存字典，过期前复用，避免频繁调用 /cgi-bin/token 触发微信频率限制。
"""
import time
import requests
import logging

from mall.common.constant import wx_app_id, wx_app_secret

LOG = logging.getLogger(__name__)

# 内存缓存：多 worker 各自独立，token 有效期 7200s，单进程内复用足够
_TOKEN_CACHE = {
    "access_token": None,
    "expire_at": 0,  # 过期时间戳（秒）
}


def get_access_token(force_refresh=False):
    """获取小程序 access_token，带内存缓存，过期前复用。

    Args:
        force_refresh: 是否强制刷新（默认 False，缓存有效时直接返回）
    Returns:
        str: access_token
    Raises:
        Exception: 获取失败（微信返回非 access_token）
    """
    now = time.time()
    if not force_refresh and _TOKEN_CACHE["access_token"] and _TOKEN_CACHE["expire_at"] > now + 300:
        return _TOKEN_CACHE["access_token"]

    resp = requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={
            "grant_type": "client_credential",
            "appid": wx_app_id,
            "secret": wx_app_secret,
        },
        timeout=10,
    )
    data = resp.json()
    if "access_token" not in data:
        LOG.error("获取微信 access_token 失败: %s", data)
        raise Exception("获取微信 access_token 失败: {}".format(data.get("errmsg")))

    _TOKEN_CACHE["access_token"] = data["access_token"]
    # expires_in 通常 7200 秒，预留 5 分钟缓冲再刷新
    _TOKEN_CACHE["expire_at"] = now + int(data.get("expires_in", 7200))
    LOG.info("微信 access_token 获取成功")
    return _TOKEN_CACHE["access_token"]
