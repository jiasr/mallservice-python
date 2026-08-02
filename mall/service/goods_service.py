"""商品Service层 - 处理业务逻辑"""
from mall.common.common import deco_catch_view_exception
from mall.db.models.Goods.sql import (
    GoodsSpuDao
)
from oslo_log import log as logging
from mall.common.common import Fail
LOG = logging.getLogger(__name__)




@deco_catch_view_exception("搜索商品列表")
def goods_list(params):
    """搜索/筛选商品列表"""
    return GoodsSpuDao.search_list(params)

@deco_catch_view_exception("获取商品详情")
def goods_detail(spu_id):
    """获取单个商品详情"""
    result = GoodsSpuDao.get_by_spu_id(spu_id)
    if not result:
        raise Fail("GOODS_NOT_FOUND", {"spuId": spu_id}, "商品不存在")
    return result




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
        raise Fail("ADD_GOODS_FAIL", None, error)
    return result


@deco_catch_view_exception("更新商品")
def admin_goods_update(id, data):
    return GoodsSpuDao.update_spu(id, data)


@deco_catch_view_exception("删除商品")
def admin_goods_delete(id):
    return GoodsSpuDao.delete_spu(id)


@deco_catch_view_exception("上架商品")
def admin_goods_put_on_sale(id):
    return GoodsSpuDao.put_on_sale(id)


@deco_catch_view_exception("下架商品")
def admin_goods_pull_off_sale(id):
    return GoodsSpuDao.pull_off_sale(id)


# ==================== PDA 端：条码查询 ====================

@deco_catch_view_exception("根据条码查询SKU")
def sku_by_barcode(barcode):
    """根据条形码查询SKU信息（PDA扫码用）"""
    result = GoodsSpuDao.get_sku_by_barcode(barcode)
    if not result:
        raise Fail('SKU_NOT_FOUND', {'barcode': barcode}, '未找到该条码对应的商品')
    return result


@deco_catch_view_exception("根据SKU ID查询")
def sku_detail(sku_id):
    """根据SKU ID查询SKU详情"""
    result = GoodsSpuDao.get_sku_detail(sku_id)
    if not result:
        raise Fail('SKU_NOT_FOUND', {'skuId': sku_id}, '未找到该SKU')
    return result