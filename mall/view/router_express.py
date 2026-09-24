"""快递（微信物流助手）API 路由

蓝图 + Namespace 双注册（规范一.2）；每个 Resource 方法加 deco_catch_view_exception（规范一.5）。
业务逻辑下沉到 mall.service.delivery_service，本层只做参数解析与鉴权。
路由前缀 /v1/express，文档参考：《微信物流配送接入设计文档》4.4
"""
import json
from flask import Blueprint, request
from flask_restx import Namespace, Resource

from mall.common.common import deco_catch_view_exception, admin_required
from mall.service import delivery_service

app_express = Blueprint('express', __name__)
ns_express = Namespace("express", description="快递（微信物流助手）管理", path="/v1/express")


@ns_express.route('/account/list', methods=['GET'])
class ExpressAccountList(Resource):
    @admin_required
    @deco_catch_view_exception("快递账号列表")
    def get(self):
        params = {
            'pageNum': request.args.get('pageNum', 1),
            'pageSize': request.args.get('pageSize', 20),
            'status': request.args.get('status', ''),
        }
        return delivery_service.list_accounts(params)


@ns_express.route('/account/bind', methods=['POST'])
class ExpressAccountBind(Resource):
    @admin_required
    @deco_catch_view_exception("绑定快递账号")
    def post(self):
        data = json.loads(request.data)
        return delivery_service.bind_account(data)


@ns_express.route('/account/sync', methods=['POST'])
class ExpressAccountSync(Resource):
    @admin_required
    @deco_catch_view_exception("同步快递账号")
    def post(self):
        return delivery_service.sync_accounts()


@ns_express.route('/track', methods=['GET'])
class ExpressTrack(Resource):
    @admin_required
    @deco_catch_view_exception("物流轨迹查询")
    def get(self):
        delivery_id = request.args.get('deliveryId', '')
        waybill_id = request.args.get('waybillId', '')
        return delivery_service.query_track(delivery_id, waybill_id)


@ns_express.route('/order/waybill', methods=['GET'])
class ExpressOrderWaybill(Resource):
    @admin_required
    @deco_catch_view_exception("获取电子面单")
    def get(self):
        order_no = request.args.get('orderNo', '')
        if not order_no:
            return {'success': False, 'message': '缺少订单号'}
        return delivery_service.get_waybill(order_no)


@ns_express.route('/account/update', methods=['POST'])
class ExpressAccountUpdate(Resource):
    @admin_required
    @deco_catch_view_exception("更新快递账号")
    def post(self):
        data = json.loads(request.data)
        return delivery_service.update_account(data)


@ns_express.route('/account/delete/<account_id>', methods=['POST'])
class ExpressAccountDelete(Resource):
    @admin_required
    @deco_catch_view_exception("删除快递账号")
    def post(self, account_id):
        return delivery_service.delete_account(account_id)


@ns_express.route('/delivery/list', methods=['GET'])
class ExpressDeliveryList(Resource):
    @admin_required
    @deco_catch_view_exception("支持的快递公司列表")
    def get(self):
        return delivery_service.list_deliveries()


@ns_express.route('/waybill/list', methods=['GET'])
class ExpressWaybillList(Resource):
    @admin_required
    @deco_catch_view_exception("运单管理列表")
    def get(self):
        params = {
            'pageNum': request.args.get('pageNum', 1),
            'pageSize': request.args.get('pageSize', 20),
            'orderNo': request.args.get('orderNo', ''),
            'waybillNo': request.args.get('waybillNo', ''),
            'company': request.args.get('company', ''),
            'withWxStatus': request.args.get('withWxStatus', ''),
        }
        return delivery_service.list_waybills(params)


@ns_express.route('/waybill/print', methods=['GET'])
class ExpressWaybillPrint(Resource):
    @admin_required
    @deco_catch_view_exception("获取电子面单")
    def get(self):
        order_no = request.args.get('orderNo', '')
        if not order_no:
            return {'success': False, 'message': '缺少订单号'}
        return delivery_service.get_waybill_print(order_no)


@ns_express.route('/waybill/test-update', methods=['POST'])
class ExpressWaybillTestUpdate(Resource):
    @admin_required
    @deco_catch_view_exception("模拟更新运单状态")
    def post(self):
        data = json.loads(request.data or '{}')
        order_no = data.get('orderNo', '')
        if not order_no:
            return {'success': False, 'message': '缺少订单号'}
        return delivery_service.test_update_waybill(order_no, data.get('actionType'))


@ns_express.route('/waybill/cancel', methods=['POST'])
class ExpressWaybillCancel(Resource):
    @admin_required
    @deco_catch_view_exception("取消运单")
    def post(self):
        data = json.loads(request.data or '{}')
        order_no = data.get('orderNo', '')
        if not order_no:
            return {'success': False, 'message': '缺少订单号'}
        return delivery_service.cancel_waybill(order_no, bool(data.get('force')))
