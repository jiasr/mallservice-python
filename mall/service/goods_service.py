"""商品Service层 - 处理业务逻辑"""
from mall.common.common import deco_catch_view_exception
from mall.db.models.Goods.sql import (
    GoodsSpuDao
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



# ==================== Admin 端商品管理 ====================

@deco_catch_view_exception("新增商品")
def admin_goods_add(data):
    """新增商品（SPU + 规格 + SKU）"""
    result, error = GoodsSpuDao.create_spu(data)
    if error:
        from mall.common.common import Fail
        raise Fail("ADD_GOODS_FAIL", None, error)
    return result