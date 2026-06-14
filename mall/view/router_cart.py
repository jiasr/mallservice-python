"""购物车 API 路由"""
import json
from flask import Blueprint, request
from flask_restx import Namespace, Resource

from mall.common.common import deco_catch_view_exception
from mall.service import cart_service

app_cart = Blueprint('cart', __name__)
ns_cart = Namespace("cart", description="购物车", path="/v1/cart")


def _get_user_id():
    """从请求头获取用户ID"""
    user_id = request.headers.get('token', '') or request.headers.get('userid', '')
    return user_id if user_id else None


@ns_cart.route('/list', methods=['GET'])
class CartList(Resource):
    @deco_catch_view_exception("购物车列表")
    def get(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        return cart_service.get_cart(user_id)


@ns_cart.route('/add', methods=['POST'])
class CartAdd(Resource):
    @deco_catch_view_exception("加入购物车")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return cart_service.add_to_cart(user_id, data)


@ns_cart.route('/update', methods=['POST'])
class CartUpdate(Resource):
    @deco_catch_view_exception("更新购物车")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return cart_service.update_cart(user_id, data)


@ns_cart.route('/delete', methods=['POST'])
class CartDelete(Resource):
    @deco_catch_view_exception("删除购物车")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return cart_service.delete_cart(user_id, data)


@ns_cart.route('/clear', methods=['POST'])
class CartClear(Resource):
    @deco_catch_view_exception("清空购物车")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        return cart_service.clear_cart(user_id)
