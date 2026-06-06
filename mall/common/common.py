import json
import traceback

from flask import request
from flask import g
from flask import make_response
from oslo_log import log as logging
from flask import jsonify


LOG = logging.getLogger(__name__)


def result_ok(data=""):
    data = {"errCode": None, "errMessage": None, "exceptionMsg": None, "flag": True, "resData": data}
    LOG.info(data)
    return data

def result_fail(error_code, params, error_massage=None):
    lang = request.headers.get('X-Accept-Language')
    return {"errCode": error_code, "errMessage": "result_fail", "exceptionMsg": error_massage, "flag": False, "resData": None}


def result_error():
    error_code = 'INTERNAL_ERROR'
    lang = request.headers.get('X-Accept-Language')
    return {"errCode": error_code, "errMessage": "result_error", "exceptionMsg": None, "flag": False, "resData": None}



class Fail(Exception):
    """
    自定义业务触发，不需要追踪
    """

    def __init__(self, error_code, params=None, error_message=None):
        self.error_code = error_code
        self.params = params
        self.error_message = error_message

    def __str__(self):
        return self.error_code




def deco_catch_view_exception(func_desc="外部接口"):
    def catch_exception(origin_func):
        def wrapper(*args, **kwargs):
            func_name = "未知函数"
            headers = {
                'content-type': 'application/json; charset=UTF-8'
            }
            result = None
            try:
                g.lang = request.headers.get('X-Accept-Language')
                func_name = origin_func.__name__
                u = origin_func(*args, **kwargs)

                result = make_response(json.dumps(result_ok(u)))
                #jsonify(result_ok(u))

            except Fail as e:
                LOG.error("方法:{} 的错误信息:{}".format(func_name, e))
                result = make_response(json.dumps(result_fail(e.error_code, e.params, e.error_message)))
            except Exception as e:
                traceback.print_exc()
                LOG.error("方法:{} 的异常信息:{}".format(func_name, e))
                result = make_response(json.dumps(result_error()))

            result.headers = headers

            return result

        return wrapper

    return catch_exception



def build_tree(flat_list, id_field="id", parent_field="parentId", children_field="children", root_parent_val=None):
    """
    通用多级级联树构建函数，支持任意深度。

    参数:
        flat_list:      扁平的节点列表（dict 列表或 ORM 对象列表）
        id_field:       节点 ID 的字段名，默认 "id"
        parent_field:   父节点 ID 的字段名，默认 "parentId"
        children_field: 子节点列表的字段名，默认 "children"
        root_parent_val: 根节点的 parent 值（判断标准），默认 None 表示 "0" 或 None 或 0 都算根

    返回:
        roots: 树根节点列表，每个节点都包含 children_field 指向其子节点列表
    """
    def _val(obj, field):
        if isinstance(obj, dict):
            return obj.get(field)
        return getattr(obj, field, None)

    # 第一步：构建节点字典，统一转为 dict 格式
    node_dict = {}
    for item in flat_list:
        node_id = _val(item, id_field)
        pid = _val(item, parent_field) or "0"
        node_dict[str(node_id)] = {
            "id": _val(item, id_field),
            "name": _val(item, "name"),
            "level": _val(item, "level"),
            "parentId": str(pid),
            "createtime":str(item.create_time),
            "sort":_val(item, "sort_order"),
            children_field: [],
        }

    # 第二步：组装树
    roots = []
    for item in flat_list:
        node_id = str(_val(item, id_field))
        pid = str(_val(item, parent_field) or "0")

        if root_parent_val is not None:
            is_root = (pid == str(root_parent_val))
        else:
            is_root = (pid == "0" or pid not in node_dict)

        if is_root:
            roots.append(node_dict[node_id])
        else:
            if pid in node_dict:
                node_dict[pid][children_field].append(node_dict[node_id])
            else:
                roots.append(node_dict[node_id])

    return roots
