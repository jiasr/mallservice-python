"""库存Service层 - 处理入库业务逻辑"""
from mall.common.common import deco_catch_view_exception, Fail
from mall.db.models.Stock.sql import StockInOrderDao, StockLogDao
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


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
    sku_id = params.get('sku_id')
    page_index = int(params.get('pageIndex', 1))
    page_size = int(params.get('pageSize', 20))
    biz_type = params.get('biz_type')
    return StockLogDao.get_list(sku_id, page_index, page_size, biz_type)
