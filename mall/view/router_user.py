# -*- encoding : utf-8 -*-
import json

from flask import Blueprint
from flask import request
from flask_restx import Namespace, Resource, fields
import logging
from mall.service import  user_service

LOG = logging.getLogger(__name__)

app_user = Blueprint('user', __name__)
ns_user = Namespace("crud demo", description="告警设置", path="/v1/user")


@ns_user.route('/add', methods=['POST'])
class DemoInstance(Resource):

    def post(self):
        data = json.loads(request.data)
        return user_service.user_add(data)