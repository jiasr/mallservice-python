# -*- encoding : utf-8 -*-
import json

from flask import Blueprint
from flask import request
from flask_restx import Namespace, Resource, fields
from oslo_log import log as logging
from mall.service import  user_service
from mall.common.common import deco_catch_view_exception

LOG = logging.getLogger(__name__)

app_user = Blueprint('user', __name__)
ns_user = Namespace("crud demo", description="用户测试", path="/v1/user")


@ns_user.route('/add', methods=['POST'])
class UserAdd(Resource):

    def post(self):
        data = json.loads(request.data)
        return user_service.user_add(data)


@ns_user.route('/list', methods=['GET'])
class UserList(Resource):
    def get(self):
        params = request.args
        return user_service.user_list(params)


@ns_user.route('/wx_login', methods=['POST'])
class UserList(Resource):
    def post(self):
        data = json.loads(request.data)
        return user_service.wx_login(data)


@ns_user.route('/info', methods=['GET'])
class UserInfo(Resource):
    def get(self):
        user_id = request.headers.get('token', '') or request.headers.get('userid', '')
        return user_service.user_info(user_id)


@ns_user.route('/updateProfile', methods=['POST'])
class UserUpdateProfile(Resource):
    @deco_catch_view_exception("更新用户信息")
    def post(self):
        user_id = request.headers.get('token', '') or request.headers.get('userid', '')
        if not user_id:
            return {"success": False, "message": "未登录"}
        data = json.loads(request.data)
        return user_service.update_profile(user_id, data)