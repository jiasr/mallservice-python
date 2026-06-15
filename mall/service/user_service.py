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


@deco_catch_view_exception("更新用户资料")
def update_profile(user_id, data):
    from mall.db.engines.mysql import get_session
    session = get_session()
    with session.begin():
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "message": "用户不存在"}
        if data.get('avatar'):
            user.avatar = data['avatar']
        if data.get('nickName') or data.get('name'):
            user.name = data.get('nickName') or data['name']
    return {"success": True}


@deco_catch_view_exception("用户信息")
def user_info(user_id):
    if not user_id:
        return {}
    from mall.db.models.User.model import User
    from mall.db.engines.mysql import get_session
    from mall.db.models.Order.sql import OrderDao

    session = get_session()
    nickname = ''
    avatar = ''
    with session.begin():
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            nickname = user.name or ''
            avatar = user.avatar or ''

    counts = OrderDao.count_by_status(user_id) or {}
    data = counts.get('data', [])

    return {
        'userInfo': {'avatarUrl': avatar, 'nickName': nickname, 'phoneNumber': ''},
        'countsData': [],
        'orderTagInfos': data,
        'customerServiceInfo': {},
    }
