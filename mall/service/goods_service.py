"""商品Service层 - 处理业务逻辑"""
from mall.common.common import deco_catch_view_exception
from mall.db.models.Goods.sql import (
    GoodsSpuDao, GoodsCategoryDao, GoodsCommentDao, SearchDao
)
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


@deco_catch_view_exception("获取商品详情")
def goods_detail(spu_id):
    """获取单个商品详情"""
    result = GoodsSpuDao.get_by_spu_id(spu_id)
    if not result:
        from mall.common.common import Fail
        raise Fail("GOODS_NOT_FOUND", {"spuId": spu_id}, "商品不存在")
    return result


@deco_catch_view_exception("搜索商品列表")
def goods_list(params):
    """搜索/筛选商品列表"""
    return GoodsSpuDao.search_list(params)


@deco_catch_view_exception("获取简单商品列表")
def goods_simple_list(page_index=1, page_size=20):
    """获取简单商品列表（首页用）"""
    return GoodsSpuDao.get_simple_list(page_index, page_size)


@deco_catch_view_exception("获取商品分类树")
def goods_category_tree():
    """获取三级分类树"""
    return GoodsCategoryDao.get_category_tree()


@deco_catch_view_exception("获取商品评价列表")
def goods_comments_list(spu_id):
    """获取商品评价列表"""
    return GoodsCommentDao.get_comments_by_spu(spu_id)


@deco_catch_view_exception("获取商品评价统计")
def goods_comments_count(spu_id):
    """获取商品评价统计"""
    return GoodsCommentDao.get_comments_count(spu_id)


@deco_catch_view_exception("添加商品评价")
def goods_comment_add(data):
    """添加商品评价"""
    ok = GoodsCommentDao.add_comment(data)
    if not ok:
        from mall.common.common import Fail
        raise Fail("ADD_COMMENT_FAIL", None, "添加评价失败")
    return {"success": True}


@deco_catch_view_exception("获取搜索历史")
def search_history(user_id=None):
    """获取搜索历史"""
    return SearchDao.get_history(user_id)


@deco_catch_view_exception("获取热门搜索")
def search_popular():
    """获取热门搜索词"""
    return SearchDao.get_popular()


@deco_catch_view_exception("添加搜索记录")
def search_add_history(keyword, user_id=None):
    """添加搜索记录"""
    SearchDao.add_history(keyword, user_id)
    return {"success": True}
