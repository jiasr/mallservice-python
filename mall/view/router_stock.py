# -*- encoding : utf-8 -*-
"""进销存库存管理相关API路由"""
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource
from oslo_log import log as logging

from mall.service import stock_in_service
from mall.common.common import admin_required

LOG = logging.getLogger(__name__)

app_stock = Blueprint('stock', __name__)
ns_stock = Namespace("stock", description="进销存库存管理接口", path="/v1/stock")


# ==================== 库存商品管理 ====================
@ns_stock.route('/goods/create', methods=['POST'])
class InvGoodsCreate(Resource):
    """新增库存商品"""
    @admin_required
    def post(self):
        data = json.loads(request.data)
        return stock_in_service.inv_goods_create(data)


@ns_stock.route('/goods/update', methods=['POST'])
class InvGoodsUpdate(Resource):
    """修改库存商品"""
    @admin_required
    def post(self):
        data = json.loads(request.data)
        return stock_in_service.inv_goods_update(data)


@ns_stock.route('/goods/by-barcode', methods=['GET'])
class InvGoodsByBarcode(Resource):
    """按条码查询库存商品（PDA扫码用）"""
    def get(self):
        barcode = request.args.get('barcode', '').strip()
        return stock_in_service.inv_goods_by_barcode(barcode)


@ns_stock.route('/goods/gds-query', methods=['GET'])
class InvGoodsGdsQuery(Resource):
    """调用 GDS 查询条码商品信息（自动补全新商品）"""
    def get(self):
        barcode = request.args.get('barcode', '').strip()
        return stock_in_service.inv_goods_gds_query(barcode)


@ns_stock.route('/goods/detail', methods=['GET'])
class InvGoodsDetail(Resource):
    """库存商品详情"""
    def get(self):
        params = request.args.to_dict()
        return stock_in_service.inv_goods_detail(params)


@ns_stock.route('/goods/list', methods=['GET'])
class InvGoodsList(Resource):
    """库存商品列表"""
    def get(self):
        params = request.args.to_dict()
        return stock_in_service.inv_goods_list(params)


# ==================== 入库单管理 ====================
@ns_stock.route('/in/create', methods=['POST'])
class StockInCreate(Resource):
    """创建入库单（草稿）"""
    @admin_required
    def post(self):
        data = json.loads(request.data)
        return stock_in_service.stock_in_create(data)


@ns_stock.route('/in/submit', methods=['POST'])
class StockInSubmit(Resource):
    """提交入库单（更新库存+写流水）"""
    @admin_required
    def post(self):
        data = json.loads(request.data)
        return stock_in_service.stock_in_submit(data)


@ns_stock.route('/in/cancel', methods=['POST'])
class StockInCancel(Resource):
    """取消入库单"""
    @admin_required
    def post(self):
        data = json.loads(request.data)
        return stock_in_service.stock_in_cancel(data)


@ns_stock.route('/in/list', methods=['GET'])
class StockInList(Resource):
    """入库单列表"""
    def get(self):
        params = request.args.to_dict()
        return stock_in_service.stock_in_list(params)


@ns_stock.route('/in/detail', methods=['GET'])
class StockInDetail(Resource):
    """入库单详情"""
    def get(self):
        params = request.args.to_dict()
        return stock_in_service.stock_in_detail(params)


# ==================== 库存流水 ====================
@ns_stock.route('/log/list', methods=['GET'])
class StockLogList(Resource):
    """库存流水列表"""
    def get(self):
        params = request.args.to_dict()
        return stock_in_service.stock_log_list(params)
