from flask import Flask ,request
from flask_cors import CORS
from flask_restx import  Api
import flask_excel
import logging


from mall.view.router_demo import app_demo,ns_demo
from mall.view.router_user import app_user,ns_user

LOG = logging.getLogger(__name__)

app = Flask(__name__)
flask_excel.init_excel(app)
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


api.add_namespace(ns_demo)
api.add_namespace(ns_user)

