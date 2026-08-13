"""用户协议与隐私政策服务"""
from mall.common.common import deco_catch_view_exception, Fail
from mall.db.models.Agreement.sql import AgreementDao


@deco_catch_view_exception("获取协议列表")
def agreement_list(params):
    """后台配置：分页查询所有协议"""
    count, rows = AgreementDao.list(params)
    return {
        'totalCount': count,
        'list': rows,
        'pageIndex': int(params.get('pageIndex', 1)),
        'pageSize': int(params.get('pageSize', 10)),
    }


@deco_catch_view_exception("获取协议内容")
def agreement_get(agreement_type):
    """小程序端：获取指定类型启用的协议"""
    result = AgreementDao.get_by_type(agreement_type)
    if not result:
        raise Fail('AGREEMENT_NOT_FOUND', None, '协议不存在')
    return result


@deco_catch_view_exception("保存协议")
def agreement_save(data):
    """后台配置：新增或更新协议"""
    result, error = AgreementDao.save(data)
    if error:
        raise Fail('AGREEMENT_SAVE_FAIL', None, error)
    return result


@deco_catch_view_exception("删除协议")
def agreement_delete(agreement_id):
    """后台配置：删除协议"""
    success, error = AgreementDao.delete(agreement_id)
    if not success:
        raise Fail('AGREEMENT_DELETE_FAIL', None, error)
    return {'success': True}
