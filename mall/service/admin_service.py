"""管理员服务层"""
from oslo_log import log as logging

from mall.common.jwt_utils import create_token
from mall.db.models.Admin.adminsql import AdminUserDao
from mall.common.common import Fail

LOG = logging.getLogger(__name__)


def admin_login(username, password):
    """管理员登录

    Returns:
        dict: {"token": "xxx"}
    Raises:
        Fail: 登录失败时抛出
    """
    if not username or not password:
        raise Fail("LOGIN_PARAM_ERROR", error_message="用户名和密码不能为空")

    user = AdminUserDao.verify_login(username, password)
    if not user:
        raise Fail("LOGIN_FAIL", error_message="用户名或密码错误")

    token = create_token(user["id"], user["username"])
    LOG.info("管理员 {} 登录成功".format(username))
    return {"token": token}


def admin_getinfo(admin_id):
    """获取管理员信息和菜单

    Args:
        admin_id: 当前登录的管理员ID

    Returns:
        dict: username, avatar, menus, ruleNames
    """
    user = AdminUserDao.get_by_id(admin_id)
    if not user:
        raise Fail("USER_NOT_FOUND", error_message="用户不存在")

    flat_menus = AdminUserDao.get_menus_by_role(user["role_id"])
    menu_tree = AdminUserDao.build_menu_tree(flat_menus)
    rule_names = AdminUserDao.get_rule_names_by_role(user["role_id"])

    return {
        "username": user["username"],
        "avatar": user["avatar"],
        "menus": menu_tree,
        "ruleNames": rule_names,
    }


def admin_logout(admin_id):
    """管理员登出（当前为无状态 JWT，仅记录日志）"""
    LOG.info("管理员 {} 登出".format(admin_id))
    return {"message": "登出成功"}


def admin_update_password(admin_id, old_password, new_password):
    """修改管理员密码"""
    if not old_password or not new_password:
        raise Fail("PARAM_ERROR", error_message="密码不能为空")
    if len(new_password) < 6:
        raise Fail("PARAM_ERROR", error_message="新密码长度不能少于6位")

    ok, msg = AdminUserDao.update_password(admin_id, old_password, new_password)
    if not ok:
        raise Fail("PASSWORD_ERROR", error_message=msg)

    LOG.info("管理员 {} 修改密码成功".format(admin_id))
    return {"message": msg}
