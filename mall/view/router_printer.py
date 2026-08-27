"""云打印机配置与测试 API"""
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource
from oslo_log import log as logging

from mall.common.common import admin_required, deco_catch_view_exception
from mall.service import printer_service

LOG = logging.getLogger(__name__)

app_printer = Blueprint('printer', __name__)
ns_printer = Namespace("printer", description="云打印机", path="/v1/admin")


@ns_printer.route('/printer/brands', methods=['GET'])
class PrinterBrands(Resource):
    """支持的小票机品牌列表（含表单字段定义）"""

    @admin_required
    @deco_catch_view_exception("获取打印机品牌")
    def get(self):
        return printer_service.get_brands()


@ns_printer.route('/printer/<brand>', methods=['GET', 'POST'])
class PrinterConfigView(Resource):
    """读取/保存指定品牌配置"""

    @admin_required
    @deco_catch_view_exception("读取打印机配置")
    def get(self, brand):
        return printer_service.get_config(brand)

    @admin_required
    @deco_catch_view_exception("保存打印机配置")
    def post(self, brand):
        data = json.loads(request.data)
        return printer_service.save_config(brand, data)


@ns_printer.route('/printer/<brand>/test', methods=['POST'])
class PrinterTest(Resource):
    """发送测试打印到指定设备"""

    @admin_required
    @deco_catch_view_exception("测试打印")
    def post(self, brand):
        data = json.loads(request.data)
        return printer_service.test_print(brand, data.get("sn", ""))


@ns_printer.route('/printer/feie/print', methods=['POST'])
class PrinterFeiePrint(Resource):
    """打印订单小票（手动/补打，可选指定设备）"""

    @admin_required
    @deco_catch_view_exception("打印订单小票")
    def post(self):
        data = json.loads(request.data)
        return printer_service.print_ticket(data.get('orderNo', ''), data.get('sn', ''))


# ==================== 飞鹅打印结果回调（无鉴权，飞鹅服务器调用） ====================

app_printer_cb = Blueprint('printer_cb', __name__)
ns_printer_cb = Namespace("printer_cb", description="云打印机回调", path="/v1/printer")


@ns_printer_cb.route('/callback/feie', methods=['POST'])
class PrinterFeieCallback(Resource):
    """飞鹅打印结果回调：需立即返回 SUCCESS，否则飞鹅 5 秒后重推"""

    def post(self):
        params = request.form.to_dict()
        return printer_service.handle_print_callback(params, request.remote_addr or '')
