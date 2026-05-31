from mall.common.common import deco_catch_view_exception
from mall.db.models.User.useraddresssql import AddressDao
from oslo_log import log as logging
from mall.common.constant import wx_app_id,wx_app_secret
LOG = logging.getLogger(__name__)
import requests


@deco_catch_view_exception("地址添加")
def address_add(params):
    result_list = []
    users = AddressDao.user_address_add()
    return users

@deco_catch_view_exception("地址列表")
def address_list(params):
    count,address = AddressDao.user_address_list(params)
    result = {}
    result["total"] =count
    result["data"] =[row.to_dict() for row in address]

    return result