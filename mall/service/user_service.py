from mall.common.common import deco_catch_view_exception
from mall.db.models.User.sql import UserDao


@deco_catch_view_exception("用户添加")
def user_add(params):

    result_list = []
    users = UserDao.useradd()

    return users