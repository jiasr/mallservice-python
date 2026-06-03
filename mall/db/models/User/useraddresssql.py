# -*- encoding : utf-8 -*-
from mall.db.models.User.model import UserAddress
import uuid
from mall.db.engines.mysql import get_session
from mall.common.constant import SETTING_LIST_DEFAILT_PAGESIZE
from oslo_log import log as logging


LOG = logging.getLogger(__name__)


class AddressDao:

    @classmethod
    def user_address_add(cls,data):
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
        if data.get("address").get("id")  is not None:
            session = get_session()
            with session.begin():
                instance = session.query(UserAddress).filter(UserAddress.id ==data.get("address").get("id")).first()
                if instance is None:
                    LOG.info("传入id不正确")
                else:
                    instance.name = data.get("address").get("name")
                    instance.name = data.get("address").get("name"),
                    instance.mobile = data.get("address").get("phone"),
                    instance.province = data.get("address").get("provinceName"),
                    instance.provincecode = data.get("address").get("provinceCode"),
                    instance.city = data.get("address").get("cityName"),
                    instance.citycode = data.get("address").get("cityCode"),
                    instance.district = data.get("address").get("districtName"),
                    instance.districtcode = data.get("address").get("districtCode"),
                    instance.detail = data.get("address").get("detailAddress"),
                    instance.is_defalut = int(data.get("address").get("isDefault")),
                    instance.addressTag = data.get("address").get("addressTag")
                    LOG.info("修改完成")

        else:
            session = get_session()
            with session.begin():
                instance = UserAddress(
                    id=uuid.uuid4().hex,
                    userid=data.get("userid"),
                    name =data.get("address").get("name"),
                    mobile=data.get("address").get("phone"),
                    province=data.get("address").get("provinceName"),
                    provincecode = data.get("address").get("provinceCode"),
                    city=data.get("address").get("cityName"),
                    citycode=data.get("address").get("cityCode"),
                    district=data.get("address").get("districtName"),
                    districtcode=data.get("address").get("districtCode"),
                    detail=data.get("address").get("detailAddress"),
                    is_defalut=int(data.get("address").get("isDefault")),
                    addressTag=data.get("address").get("addressTag")

                )
                session.add(instance)
            return instance.id

    @classmethod
    def user_address_list(cls, params):
        page_num = params.get("currentPage", 1)
        page_size = params.get("pageSize", SETTING_LIST_DEFAILT_PAGESIZE)

        session = get_session()
        with session.begin():
            query = session.query(UserAddress)
            count = query.count()

            page_size = int(page_size)
            page_num = int(page_num)
            start = (page_num - 1) * page_size
            query = query.limit(page_size).offset(start)
            result = query.all()

        return count, result

    @classmethod
    def user_address_detail(cls, data):
        session = get_session()
        with session.begin():
            address = session.query(UserAddress).filter_by(id=data.get("id")).one_or_none()
            if address:
                print(f"找到地址: {address.detail}")
            else:
                print("地址不存在")
        return address

    @classmethod
    def user_address_delete(cls, data):
        if data.get("id") is not None:
            session = get_session()
            with session.begin():
                session.query(UserAddress).filter(UserAddress.id == data.get("id").get("id")).filter(UserAddress.userid==data.get("userid")).delete()
        result={}
        result["status"]="ok"
        return result

