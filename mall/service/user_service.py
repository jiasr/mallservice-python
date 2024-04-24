from mall.common.common import deco_catch_view_exception
from mall.db.models.User.sql import UserDao
from oslo_log import log as logging


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