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


@deco_catch_view_exception("微信手机号绑定")
def wx_phone(user_id, params):
    """通过 getPhoneNumber 返回的 code 换取并绑定手机号"""
    code = params.get("code", "")
    if not code:
        return {"success": False, "message": "缺少手机号授权 code"}
    # 用 access_token 调微信接口换取手机号
    token_data = {
        "grant_type": "client_credential",
        "appid": wx_app_id,
        "secret": wx_app_secret,
    }
    token_resp = requests.get('https://api.weixin.qq.com/cgi-bin/token', params=token_data).json()
    access_token = token_resp.get('access_token')
    if not access_token:
        LOG.error("获取 access_token 失败: {}".format(token_resp))
        return {"success": False, "message": "获取微信凭证失败"}

    url = 'https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token=' + access_token
    resp = requests.post(url, json={"code": code}).json()
    LOG.info("getPhoneNumber 返回: {}".format(resp))
    if resp.get('errcode') != 0 or not resp.get('phone_info'):
        return {"success": False, "message": resp.get('errmsg', '手机号获取失败')}
    phone = resp['phone_info'].get('purePhoneNumber', '')
    if not phone:
        return {"success": False, "message": "手机号为空"}

    success, error = UserDao.bind_phone(user_id, phone)
    if not success:
        return {"success": False, "message": error}
    return {"success": True, "phone": phone}


def update_profile(user_id, data):
    from mall.db.engines.mysql import get_session
    from mall.db.models.User.model import User
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


@deco_catch_view_exception("后台用户列表")
def admin_user_list(params):
    """后台用户列表（分页 + 条件筛选）"""
    return UserDao.admin_list(params)


@deco_catch_view_exception("后台用户详情")
def admin_user_detail(user_id):
    """后台用户详情"""
    result = UserDao.admin_detail(user_id)
    if result is None:
        return {"success": False, "message": "用户不存在"}
    return result


@deco_catch_view_exception("后台用户状态修改")
def admin_user_set_status(user_id, params):
    """后台禁用/启用用户"""
    status = params.get("status")
    if status not in (0, 1, "0", "1"):
        return {"success": False, "message": "状态参数不合法"}
    success, msg = UserDao.admin_set_status(user_id, status)
    if not success:
        return {"success": False, "message": msg}
    return {"success": True}


@deco_catch_view_exception("后台用户删除")
def admin_user_delete(user_id):
    """后台删除用户"""
    success, msg = UserDao.admin_delete(user_id)
    if not success:
        return {"success": False, "message": msg}
    return {"success": True}


@deco_catch_view_exception("用户基础信息")
def user_base_info(user_id):
    """用户基础信息（昵称/头像/手机号），轻量接口，供购物车等仅需登录态校验的页面使用"""
    if not user_id:
        return {}
    from mall.db.models.User.model import User
    from mall.db.engines.mysql import get_session

    session = get_session()
    nickname = ''
    avatar = ''
    phone = ''
    with session.begin():
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            nickname = user.name or ''
            avatar = user.avatar or ''
            phone = user.phone or ''

    # 相对路径动态拼接完整URL（避免硬编码IP/端口），已在函数内import避免循环依赖
    try:
        from mall.db.engines.s3 import get_image_display_url
        avatar_url = get_image_display_url(avatar) if avatar else ''
    except Exception:
        avatar_url = avatar

    return {
        'userInfo': {'avatarUrl': avatar_url, 'nickName': nickname, 'phoneNumber': phone},
    }


@deco_catch_view_exception("用户订单统计")
def user_order_count(user_id):
    """各状态订单数量，仅个人中心订单入口角标使用"""
    if not user_id:
        return {}
    from mall.db.models.Order.sql import OrderDao

    counts = OrderDao.count_by_status(user_id) or {}
    data = counts.get('data', [])
    return {'orderTagInfos': data}


@deco_catch_view_exception("客服信息")
def user_customer_service(user_id):
    """客服信息（服务时间/客服电话），独立接口，目前后端暂无配置数据源，返回空结构预留"""
    if not user_id:
        return {}
    return {'customerServiceInfo': {}}


@deco_catch_view_exception("用户信息")
def user_info(user_id):
    """聚合用户信息（兼容旧接口，组合基础信息 + 订单统计）"""
    if not user_id:
        return {}
    base = user_base_info(user_id)
    order = user_order_count(user_id)
    customer = user_customer_service(user_id)
    return {
        'userInfo': base['userInfo'],
        'countsData': [],
        'orderTagInfos': order['orderTagInfos'],
        'customerServiceInfo': customer['customerServiceInfo'],
    }
