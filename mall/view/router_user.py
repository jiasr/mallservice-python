# -*- encoding : utf-8 -*-
import json

from flask import Blueprint
from flask import request
from flask_restx import Namespace, Resource, fields
from oslo_log import log as logging
from mall.service import  user_service

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