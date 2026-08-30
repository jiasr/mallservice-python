"""扫码备货记录 Service 层"""
from mall.common.common import Fail
from mall.db.models.PickRecord.sql import PickRecordDao
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def pick_record_create(data):
    """记录一次备货完成。同单重复备货返回失败提示"""
    order_no = (data.get('orderNo') or '').strip()
    if not order_no:
        raise Fail('PARAM_ERROR', None, '订单号不能为空')
    item_count = int(data.get('itemCount') or 0)
    total_quantity = int(data.get('totalQuantity') or 0)
    operator_id = data.get('operatorId') or 0
    operator_name = data.get('operatorName') or ''
    remark = data.get('remark') or ''
    rec, error = PickRecordDao.create(
        order_no, item_count, total_quantity,
        operator_id=operator_id, operator_name=operator_name, remark=remark,
    )
    if error:
        raise Fail('PICK_ALREADY_EXISTS', {'orderNo': order_no}, error)
    return rec


def pick_record_check(order_no):
    """查询订单是否已备货（PDA 加载订单时预检，防重复拣货）"""
    order_no = (order_no or '').strip()
    if not order_no:
        raise Fail('PARAM_ERROR', None, '订单号不能为空')
    rec = PickRecordDao.get_by_order_no(order_no)
    return {'picked': rec is not None, 'record': rec}


def pick_record_list(params):
    """备货记录分页列表"""
    page_index = int(params.get('pageIndex', 1) or 1)
    page_size = int(params.get('pageSize', 10) or 10)
    order_no = params.get('orderNo', '')
    return PickRecordDao.list(page_index, page_size, order_no)
