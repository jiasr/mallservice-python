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


# ==================== 商品分类 ====================
@ns_goods.route('/category', methods=['GET'])
class GoodsCategory(Resource):
    """获取商品三级分类树"""
    def get(self):
        return goods_service.goods_category_tree()


# ==================== 商品评价列表 ====================
@ns_goods.route('/comments', methods=['GET'])
class GoodsComments(Resource):
    """获取商品评价列表"""
    def get(self):
        spu_id = request.args.get('spuId', '0')
        return goods_service.goods_comments_list(spu_id)


# ==================== 商品评价统计 ====================
@ns_goods.route('/comments-count', methods=['GET'])
class GoodsCommentsCount(Resource):
    """获取商品评价统计"""
    def get(self):
        spu_id = request.args.get('spuId', '0')
        return goods_service.goods_comments_count(spu_id)


# ==================== 添加商品评价 ====================
@ns_goods.route('/comment-add', methods=['POST'])
class GoodsCommentAdd(Resource):
    """添加商品评价"""
    def post(self):
        data = json.loads(request.data)
        return goods_service.goods_comment_add(data)


# ==================== 搜索历史 ====================
@ns_goods.route('/search-history', methods=['GET'])
class SearchHistory(Resource):
    """获取搜索历史"""
    def get(self):
        user_id = request.args.get('userId')
        return goods_service.search_history(user_id)


# ==================== 热门搜索 ====================
@ns_goods.route('/search-popular', methods=['GET'])
class SearchPopular(Resource):
    """获取热门搜索词"""
    def get(self):
        return goods_service.search_popular()


# ==================== 添加搜索记录 ====================
@ns_goods.route('/search-add', methods=['POST'])
class SearchAdd(Resource):
    """添加搜索记录"""
    def post(self):
        data = json.loads(request.data)
        keyword = data.get('keyword', '')
        user_id = data.get('userId')
        return goods_service.search_add_history(keyword, user_id)
