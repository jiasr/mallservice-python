# -*- encoding : utf-8 -*-
from mall.db.models.User.model import User
import uuid
from mall.db.engines.mysql import get_session
from mall.common.constant import SETTING_LIST_DEFAILT_PAGESIZE

class UserDao:

    @classmethod
    def useradd(cls):
        session = get_session()
        with session.begin():
            instance = User(
                id=uuid.uuid4().hex,
                name = "tttttttt",
            )
            session.add(instance)

        return instance.id


    @classmethod
    def listalluser(cls,params):
        page_num = params.get("currentPage", 1)
        page_size = params.get("pageSize", SETTING_LIST_DEFAILT_PAGESIZE)

        session = get_session()
        with session.begin():
            query = session.query(User)
            count = query.count()

            page_size = int(page_size)
            page_num = int(page_num)
            start = (page_num - 1) * page_size
            query = query.limit(page_size).offset(start)
            result = query.all()

        return count, result

    @classmethod
    def add_wxuser(cls, params):
        openid = params["openid"]
        session_key =params["session_key"]
        session = get_session()
        result ={}
        result["userid"] = ""
        with session.begin():
            # 先查询是否已存在
            existing_user = session.query(User).filter_by(wx_openid=openid).first()
            if existing_user:
                # 更新 session_key
                existing_user.wx_session_key = session_key
                result["userid"] =  existing_user.id
            else: # 创建新用户
                instance = User(
                    id=uuid.uuid4().hex,
                    name="wx_"+openid,
                    wx_openid= openid,
                )
                session.add(instance)
                result["userid"]=instance.id
        return result

    @classmethod
    def bind_phone(cls, user_id, phone):
        """将手机号绑定到指定用户"""
        session = get_session()
        with session.begin():
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False, '用户不存在'
            user.phone = phone
        return True, ''

    @classmethod
    def get_by_phone(cls, phone):
        """按手机号查询用户（用于手机号换绑/合并）"""
        session = get_session()
        with session.begin():
            return session.query(User).filter(User.phone == phone).first()