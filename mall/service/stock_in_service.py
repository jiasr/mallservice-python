"""进销存库存Service层 - 商品管理 + 入库业务"""
from mall.common.common import deco_catch_view_exception, Fail
from mall.db.models.Stock.sql import InvGoodsDao, StockInOrderDao, StockLogDao
from mall.service.gds_service import gds_query_barcode
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


# ==================== 库存商品管理 ====================

@deco_catch_view_exception("GDS条码商品查询")
def inv_goods_gds_query(barcode):
    """调用 GDS 查询条码商品信息（自动补全新商品）"""
    if not barcode:
        raise Fail('PARAM_ERROR', None, '条码不能为空')
    result = gds_query_barcode(barcode)
    if not result:
        raise Fail('GDS_NOT_FOUND', {'barcode': barcode}, 'GDS未找到该条码商品信息')
    return result


@deco_catch_view_exception("新增库存商品")
def inv_goods_create(data):
    """新增库存商品"""
    result, error = InvGoodsDao.create(data)
    if error:
        raise Fail('INV_GOODS_CREATE_FAIL', None, error)
    return result


@deco_catch_view_exception("修改库存商品")
def inv_goods_update(data):
    """修改库存商品"""
    goods_id = data.get('id')
    result, error = InvGoodsDao.update(goods_id, data)
    if error:
        raise Fail('INV_GOODS_UPDATE_FAIL', None, error)
    return result


@deco_catch_view_exception("删除库存商品")
def inv_goods_delete(data):
    """删除库存商品。

    有入库记录的也允许删除，返回 {deleted, hasStockRecord}：
    hasStockRecord 用于前端提示"该商品已有入库记录，已强制删除"。
    """
    goods_id = data.get('id')
    if not goods_id:
        raise Fail('PARAM_ERROR', None, '商品ID不能为空')
    result, error = InvGoodsDao.delete(goods_id)
    if error:
        raise Fail('INV_GOODS_DELETE_FAIL', None, error)
    return result


@deco_catch_view_exception("按条码查询库存商品")
def inv_goods_by_barcode(barcode):
    """按条码查询库存商品（PDA扫码用）"""
    if not barcode:
        raise Fail('PARAM_ERROR', None, '条码不能为空')
    result = InvGoodsDao.get_by_barcode(barcode)
    if not result:
        raise Fail('INV_GOODS_NOT_FOUND', {'barcode': barcode}, '未找到该条码对应的商品')
    return result


@deco_catch_view_exception("查询库存商品详情")
def inv_goods_detail(params):
    """按ID查询库存商品详情"""
    goods_id = int(params.get('id', 0))
    if not goods_id:
        raise Fail('PARAM_ERROR', None, '商品ID不能为空')
    result = InvGoodsDao.get_by_id(goods_id)
    if not result:
        raise Fail('INV_GOODS_NOT_FOUND', None, '商品不存在')
    return result


@deco_catch_view_exception("查询库存商品列表")
def inv_goods_list(params):
    """分页查询库存商品"""
    page_index = int(params.get('pageIndex', 1))
    page_size = int(params.get('pageSize', 20))
    keyword = params.get('keyword')
    category = params.get('category')
    return InvGoodsDao.get_list(page_index, page_size, keyword, category)


# ==================== 入库单管理 ====================

@deco_catch_view_exception("创建入库单")
def stock_in_create(data):
    """创建入库单（草稿）"""
    result = StockInOrderDao.create(data)
    return result


@deco_catch_view_exception("提交入库单")
def stock_in_submit(data):
    """提交入库单（更新库存+写流水）"""
    order_id = data.get('order_id')
    operator_id = data.get('operator_id', 0)
    operator_name = data.get('operator_name', '')
    result, error = StockInOrderDao.submit(order_id, operator_id, operator_name)
    if error:
        raise Fail('STOCK_IN_SUBMIT_FAIL', None, error)
    return result


@deco_catch_view_exception("取消入库单")
def stock_in_cancel(data):
    """取消入库单"""
    order_id = data.get('order_id')
    result, error = StockInOrderDao.cancel(order_id)
    if error:
        raise Fail('STOCK_IN_CANCEL_FAIL', None, error)
    return result


@deco_catch_view_exception("查询入库单列表")
def stock_in_list(params):
    """分页查询入库单"""
    page_index = int(params.get('pageIndex', 1))
    page_size = int(params.get('pageSize', 20))
    status = params.get('status')
    keyword = params.get('keyword')
    return StockInOrderDao.get_list(page_index, page_size, status, keyword)


@deco_catch_view_exception("查询入库单详情")
def stock_in_detail(params):
    """获取入库单详情"""
    order_id = int(params.get('id', 0))
    result = StockInOrderDao.get_detail(order_id)
    if not result:
        raise Fail('STOCK_IN_NOT_FOUND', None, '入库单不存在')
    return result


@deco_catch_view_exception("查询库存流水")
def stock_log_list(params):
    """分页查询库存流水"""
    goods_id = params.get('goods_id')
    page_index = int(params.get('pageIndex', 1))
    page_size = int(params.get('pageSize', 20))
    biz_type = params.get('biz_type')
    return StockLogDao.get_list(goods_id, page_index, page_size, biz_type)
