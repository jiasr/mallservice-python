# -*- encoding : utf-8 -*-
import json

from flask import Blueprint
from flask import request
from flask_restx import Namespace, Resource, fields
from oslo_log import log as logging


LOG = logging.getLogger(__name__)

app_demo = Blueprint('demotest', __name__)
ns_demo = Namespace("crud demo", description="告警设置", path="/v1/demo")


@ns_demo.route('/list', methods=['GET'])
class DemoInstance(Resource):

    def get(self):
        params = request.args
        return params

    def post(self):
        data = json.loads(request.data)
        return data