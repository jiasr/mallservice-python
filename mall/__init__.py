from datetime import datetime, date
from json import JSONEncoder

from flask import Flask ,request
from flask_cors import CORS
from flask_restx import  Api
import flask_excel
import logging
import json

from mall.view.router_demo import app_demo,ns_demo
from mall.view.router_user import app_user,ns_user
from mall.view.router_address import app_address,ns_address
from mall.view.router_goodscatalog import app_goodscatalog,ns_goodscatalog
from mall.view.router_good import app_goods,ns_goods


LOG = logging.getLogger(__name__)


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        return super().default(obj)



class CustomJSONProvider:
    def __init__(self, app):
        self.app = app

    def dumps(self, obj, **kwargs):
        def default(o):
            if isinstance(o, datetime):
                return o.strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(o, date):
                return o.strftime('%Y-%m-%d')
            raise TypeError(f"Type {type(o)} not serializable")
        return json.dumps(obj, default=default, **kwargs)

    def loads(self, s, **kwargs):
        return json.loads(s, **kwargs)



app = Flask(__name__)
app.json = CustomJSONProvider(app)
flask_excel.init_excel(app)
CORS(app)
api = Api(app, version='1.0', title='inspur cloud rest api doc', description='inspur cloud rest api doc')


@app.before_request
def log_req1():
    LOG.info(request.path)

@app.after_request
def log_req2(res):
    LOG.info(res)
    return res
# 注册BP组件
app.register_blueprint(app_demo, url_prefix="/v1/demo")
app.register_blueprint(app_user, url_prefix="/v1/user")
app.register_blueprint(app_address, url_prefix="/v1/address")
app.register_blueprint(app_goodscatalog, url_prefix="/v1/goodscatalog")
app.register_blueprint(app_goodscatalog, url_prefix="/v1/goods")



api.add_namespace(ns_demo)
api.add_namespace(ns_user)
api.add_namespace(ns_address)
api.add_namespace(ns_goodscatalog)
api.add_namespace(ns_goods)

