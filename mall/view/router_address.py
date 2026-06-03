# -*- encoding : utf-8 -*-
import json

from flask import Blueprint
from flask import request
from flask_restx import Namespace, Resource, fields
from oslo_log import log as logging
from mall.service import  address_service

LOG = logging.getLogger(__name__)

app_address = Blueprint('address', __name__)
ns_address = Namespace("crud demo", description="添加地址", path="/v1/address")



@ns_address.route('/add', methods=['POST'])
class AddressAdd(Resource):

    def post(self):
        data = json.loads(request.data)
        LOG.info(data)
        return address_service.address_add(data)


@ns_address.route('/list', methods=['GET'])
class AddressList(Resource):

    def get(self):
        params = request.args
        LOG.info(params)
        return address_service.address_list(params)



@ns_address.route('/detail', methods=['GET'])
class AddressList(Resource):

    def get(self):
        params = request.args
        LOG.info(params)
        return address_service.address_detail(params)

@ns_address.route('/delete', methods=['POST'])
class DelAddress(Resource):

    def post(self):
        params = json.loads(request.data)
        LOG.info(params)
        return address_service.address_delete(params)