from mall.common.common import deco_catch_view_exception
from mall.db.models.User.usersql import UserDao
from oslo_log import log as logging
from mall.common.constant import wx_app_id,wx_app_secret
LOG = logging.getLogger(__name__)
import requests


@deco_catch_view_exception("用户添加")
def user_add(params):

    result_list = []
    users = UserDao.useradd()

    return users

@deco_catch_view_exception("用户列表")
def user_list(params):

    count,users = UserDao.listalluser(params)
    result = {}
    result["total"] =count
    result["data"] =[row.to_dict() for row in users]

    return result

@deco_catch_view_exception("微信登录")
def wx_login(params):
    LOG.info(params)
    data = {
            "appid": wx_app_id,
            "secret": wx_app_secret,
            "js_code": params.get("code"),
            "grant_type":'authorization_code'
    }
    response = requests.get('https://api.weixin.qq.com/sns/jscode2session', params=data)
    result = response.json()
    LOG.info(result)

    if result.get('errcode') is  None:
        # 请求成功,创建用户
        openid = result['openid']
        session_key = result['session_key']
        params={}
        params["openid"] =openid
        params["session_key"] =session_key

        return  UserDao.add_wxuser(params)
    else:
        # 请求失败
        print(f"错误码: {result.get('errcode')}, 错误信息: {result.get('errmsg')}")
        return None, None

    return result
