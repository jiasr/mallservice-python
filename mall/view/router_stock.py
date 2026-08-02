# -*- encoding : utf-8 -*-
"""库存管理相关API路由"""
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource
from oslo_log import log as logging

from mall.service import stock_in_service
from mall.service import goods_service
from mall.common.common import admin_required

LOG = logging.getLogger(__name__)

app_stock = Blueprint('stock', __name__)
ns_stock = Namespace("stock", description="库存管理接口", path="/v1/stock")


# ==================== 按条码查询SKU ====================
@ns_stock.route('/sku/by-barcode', methods=['GET'])
class SkuByBarcode(Resource):
    """根据条形码查询SKU信息"""
    def get(self):
        barcode = request.args.get('barcode', '').strip()
        if not barcode:
            return {"flag": False, "errCode": "PARAM_ERROR", "errMessage": "条码不能为空", "resData": None}
        return goods_service.sku_by_barcode(barcode)


# ==================== 库存查询 ====================
@ns_stock.route('/sku/query', methods=['GET'])
class SkuQuery(Resource):
    """查询SKU库存（支持按条码或SKU ID）"""
    def get(self):
        barcode = request.args.get('barcode', '').strip()
        sku_id = request.args.get('skuId', '').strip()
        if barcode:
            return goods_service.sku_by_barcode(barcode)
        elif sku_id:
            return goods_service.sku_detail(sku_id)
        return {"flag": False, "errCode": "PARAM_ERROR", "errMessage": "请提供条码或SKU ID", "resData": None}


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
