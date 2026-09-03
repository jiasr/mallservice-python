from datetime import datetime, date
from json import JSONEncoder

from flask import Flask ,request
from flask_cors import CORS
from flask_restx import  Api
import flask_excel
import logging
import json

import socket
import threading
import os

from mall.conf import CONF


def _bootstrap_config():
    """在模块导入时尽早加载配置文件，保证 auto_migrate / TCP / 数据库操作之前配置就绪"""
    try:
        if CONF.database.connection:
            return
    except Exception:
        pass
    config_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'etc', 'mall', 'mall.conf'
    )
    if os.path.exists(config_file):
        CONF(['--config-file', config_file], project="mall")
    else:
        CONF([], project="mall")


_bootstrap_config()

from mall.view.router_user import app_user,ns_user
from mall.view.router_address import app_address,ns_address
from mall.view.router_goodscatalog import app_goodscatalog,ns_goodscatalog
from mall.view.router_good import app_goods,ns_goods
from mall.view.router_admin import app_admin,ns_admin
from mall.view.router_upload import app_upload,ns_upload
from mall.view.router_setting import app_setting,ns_setting
from mall.view.router_s3 import app_storage,ns_storage
from mall.view.router_cart import app_cart,ns_cart
from mall.view.router_order import app_order,ns_order
from mall.view.router_freight import app_freight,ns_freight
from mall.view.router_express import app_express, ns_express
from mall.view.router_wechatpay import app_wechatpay,ns_wechatpay
from mall.view.router_stock import app_stock,ns_stock
from mall.view.router_printer import app_printer,ns_printer, app_printer_cb, ns_printer_cb
from mall.view.router_agreement import app_agreement, ns_agreement, ns_agreement_admin

from mall.common.gds_login import query_barcode


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

def handle_tcp_client(client_socket, address):
    LOG.info(f"TCP连接来自 {address}")
    try:
        data = client_socket.recv(1024)
        if data:
            message = data.decode('utf-8').strip()
            LOG.info(f"接收到条码: {message}")
            query_barcode(message)

            # 🔥 在这里调用你的业务处理逻辑
            # 例如：process_barcode(message)

            client_socket.send(b"OK\n")
        else:
            LOG.warning(f"来自 {address} 的数据为空")
    except Exception as e:
        LOG.error(f"处理TCP数据错误: {e}")
    finally:
        client_socket.close()

def start_tcp_server(host='0.0.0.0', port=5001):
    """在后台线程中运行的TCP服务器"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    LOG.info(f"TCP Socket服务器已启动，监听 {host}:{port}")

    while True:
        try:
            client, addr = server.accept()
            # 每个客户端连接开一个新线程处理
            t = threading.Thread(target=handle_tcp_client, args=(client, addr))
            t.daemon = True
            t.start()
        except Exception as e:
            LOG.error(f"TCP服务器异常: {e}")
            break
    server.close()

# 1. 先启动TCP服务器线程（daemon=True，主程序退出时自动结束）
#    注意：gunicorn 多 worker 会各自 import 本模块，为避免端口冲突，
#    仅当端口未被占用时才启动（首个进程持有，其余跳过）。
def _safe_start_tcp_server():
    try:
        start_tcp_server()
    except OSError:
        # 端口已被其他 worker/进程占用，说明 TCP 服务已就绪，跳过即可
        pass


tcp_thread = threading.Thread(target=_safe_start_tcp_server, daemon=True)
tcp_thread.start()


app = Flask(__name__)
app.json = CustomJSONProvider(app)
flask_excel.init_excel(app)
CORS(app)
api = Api(app, version='1.0', title='inspur cloud rest api doc', description='inspur cloud rest api doc')


@app.before_request
def log_req1():

    LOG.info(f"req: {request.path}")

@app.after_request
def log_req2(res):
    LOG.info(res)
    return res
# 注册BP组件
app.register_blueprint(app_user, url_prefix="/v1/user")
app.register_blueprint(app_address, url_prefix="/v1/address")
app.register_blueprint(app_goodscatalog, url_prefix="/v1/goodscatalog")
app.register_blueprint(app_goods, url_prefix="/v1/goods")
app.register_blueprint(app_admin, url_prefix="/v1/admin")
app.register_blueprint(app_upload, url_prefix="/v1/upload")
app.register_blueprint(app_setting, url_prefix="/v1/admin")
app.register_blueprint(app_storage, url_prefix="/v1/admin")
app.register_blueprint(app_cart, url_prefix="/v1/cart")
app.register_blueprint(app_order, url_prefix="/v1/order")
app.register_blueprint(app_freight, url_prefix="/v1/order/admin/freight")
app.register_blueprint(app_express, url_prefix="/v1/express")
app.register_blueprint(app_wechatpay, url_prefix="/v1/admin")
app.register_blueprint(app_stock, url_prefix="/v1/stock")
app.register_blueprint(app_printer, url_prefix="/v1/admin")
app.register_blueprint(app_printer_cb, url_prefix="/v1/printer")
app.register_blueprint(app_agreement, url_prefix="/v1")







api.add_namespace(ns_user)
api.add_namespace(ns_address)
api.add_namespace(ns_goodscatalog)
api.add_namespace(ns_goods)
api.add_namespace(ns_admin)
api.add_namespace(ns_upload)
api.add_namespace(ns_setting)
api.add_namespace(ns_storage)
api.add_namespace(ns_cart)
api.add_namespace(ns_order)
api.add_namespace(ns_freight)
api.add_namespace(ns_express)
api.add_namespace(ns_wechatpay)
api.add_namespace(ns_stock)
api.add_namespace(ns_printer)
api.add_namespace(ns_printer_cb)
api.add_namespace(ns_agreement)
api.add_namespace(ns_agreement_admin)

# 启动时自动执行数据库迁移
try:
    from mall.cmd.dbsync import auto_migrate
    auto_migrate()
except Exception as e:
    LOG.warning("数据库迁移失败: {}".format(e))






