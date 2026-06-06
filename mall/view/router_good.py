# -*- encoding : utf-8 -*-
"""商品相关API路由"""
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource, fields
from oslo_log import log as logging

from mall.service import goods_service

LOG = logging.getLogger(__name__)

app_goods = Blueprint('goods', __name__)
ns_goods = Namespace("goods", description="商品相关接口", path="/v1/goods")

# ==================== 商品详情 ====================
@ns_goods.route('/detail', methods=['GET'])
class GoodsDetail(Resource):
    """获取商品详情"""
    def get(self):
        spu_id = request.args.get('spuId', '0')
        return goods_service.goods_detail(spu_id)


# ==================== 商品列表（搜索+筛选） ====================
@ns_goods.route('/list', methods=['GET'])
class GoodsList(Resource):
    """搜索/筛选商品列表
    参数: keyword, pageNum, pageSize, sort(0综合1价格), sortType(0升序1降序), minPrice, maxPrice, categoryId
    """
    def get(self):
        params = request.args.to_dict()
        return goods_service.goods_list(params)


# ==================== 简单商品列表（首页） ====================
@ns_goods.route('/simple-list', methods=['GET'])
class GoodsSimpleList(Resource):
    """获取简单商品列表（首页推荐等）"""
    def get(self):
        page_index = int(request.args.get('pageIndex', 1))
        page_size = int(request.args.get('pageSize', 20))
        return goods_service.goods_simple_list(page_index, page_size)





# ==================== Admin 端：商品管理 ====================
@ns_goods.route('/admin/goods/add', methods=['POST'])
class AdminGoodsAdd(Resource):
    """新增商品"""
    def post(self):
        data = json.loads(request.data)
        return goods_service.admin_goods_add(data)