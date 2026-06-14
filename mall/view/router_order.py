"""订单 API 路由"""
import json
from flask import Blueprint, request
from flask_restx import Namespace, Resource

from mall.common.common import deco_catch_view_exception
from mall.service import order_service

app_order = Blueprint('order', __name__)
ns_order = Namespace("order", description="订单", path="/v1/order")


def _get_user_id():
    user_id = request.headers.get('token', '') or request.headers.get('userid', '')
    return user_id if user_id else None


@ns_order.route('/preview', methods=['POST'])
class OrderPreview(Resource):
    @deco_catch_view_exception("订单预览")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.preview(user_id, data)


@ns_order.route('/create', methods=['POST'])
class OrderCreate(Resource):
    @deco_catch_view_exception("创建订单")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.create(user_id, data)


@ns_order.route('/detail', methods=['GET'])
class OrderDetail(Resource):
    @deco_catch_view_exception("订单详情")
    def get(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        order_id = request.args.get('orderId', '')
        return order_service.detail(user_id, order_id)


@ns_order.route('/cancel', methods=['POST'])
class OrderCancel(Resource):
    @deco_catch_view_exception("取消订单")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.cancel(user_id, data)
