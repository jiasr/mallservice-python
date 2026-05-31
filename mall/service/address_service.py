from mall.common.common import deco_catch_view_exception
from mall.db.models.User.useraddresssql import AddressDao
from oslo_log import log as logging
from mall.common.constant import wx_app_id,wx_app_secret
LOG = logging.getLogger(__name__)
import requests





@deco_catch_view_exception("地址添加")
def address_add(params):
    result_list = []
    # {'userid': '33918da754964edda37da983403ebc3d',
    # 'address': {'saasId': '88888888',
    # 'uid': '88888888205500',
    # 'authToken': None,
    # 'id': '', 'addressId': '',
    # 'phone': '15562542222',
    # 'name': 'dadf',
    # 'countryName': '',
    # 'countryCode': '',
    # 'provinceName': '北京市',
    # 'provinceCode': '110000',
    # 'cityName': '北京市',
    # 'cityCode': '110100',
    # 'districtName': '朝阳区',
    # 'districtCode': '110105',
    # 'detailAddress': '2132',
    # 'isDefault': 0,
    # 'addressTag': '',
    # 'storeId': None}}


    users = AddressDao.user_address_add(params)
    return users

@deco_catch_view_exception("地址列表")
def address_list(params):
    count,address = AddressDao.user_address_list(params)
    result = {}
    result["total"] =count
    result["data"] =[row.to_dict() for row in address]
    return result