# -*- encoding : utf-8 -*-
import json

from flask import Blueprint
from flask import request
from flask_restx import Namespace, Resource, fields
from oslo_log import log as logging
from mall.service import goodscatalog_service

LOG = logging.getLogger(__name__)

app_goodscatalog = Blueprint('goodscatalog', __name__)
ns_goodscatalog = Namespace("crud demo", description="用户测试", path="/v1/goodscatalog")


@ns_goodscatalog.route('/add', methods=['POST'])
class GoodsCatalogAdd(Resource):
    def post(self):
        data = json.loads(request.data)
        return goodscatalog_service.goodscatalog_add(data)


@ns_goodscatalog.route('/list', methods=['GET'])
class GoodsCatalogList(Resource):
    def get(self):
        params = request.args
        return goodscatalog_service.goodscatalog_list(params)