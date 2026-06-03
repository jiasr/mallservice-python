from mall.common.common import deco_catch_view_exception
from mall.db.models.User.useraddresssql import AddressDao
from oslo_log import log as logging
from mall.common.constant import wx_app_id,wx_app_secret
LOG = logging.getLogger(__name__)
import requests





@deco_catch_view_exception("地址添加")
def address_add(params):
    address = AddressDao.user_address_add(params)
    return address

@deco_catch_view_exception("地址详情")
def address_detail(params):
    address = AddressDao.user_address_detail(params)
    return address.to_dict()

@deco_catch_view_exception("地址列表")
def address_list(params):
    count,address = AddressDao.user_address_list(params)
    result = {}
    result["total"] =count
    result["data"] =[row.to_dict() for row in address]
    return result

@deco_catch_view_exception("删除地址")
def address_delete(params):
    result = AddressDao.user_address_delete(params)
    return result