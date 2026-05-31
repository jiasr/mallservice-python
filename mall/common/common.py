import json
import traceback

from flask import request
from flask import g
from flask import make_response
from oslo_log import log as logging

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