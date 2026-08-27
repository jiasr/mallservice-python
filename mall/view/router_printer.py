"""云打印机配置与测试 API"""
import json

from flask import Blueprint, request, Response
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


@ns_printer.route('/printer/feie/logs', methods=['GET'])
class PrinterFeieLogs(Resource):
    """打印流水分页查询（订单打印记录/设置页共用）"""

    @admin_required
    @deco_catch_view_exception("查询打印记录")
    def get(self):
        args = request.args
        return printer_service.list_logs(
            args.get('orderNo', ''),
            args.get('status', ''),
            int(args.get('pageNum', 1) or 1),
            int(args.get('pageSize', 10) or 10),
        )


# ==================== 飞鹅打印结果回调（无鉴权，飞鹅服务器调用） ====================

app_printer_cb = Blueprint('printer_cb', __name__)
ns_printer_cb = Namespace("printer_cb", description="云打印机回调", path="/v1/printer")


@ns_printer_cb.route('/callback/feie', methods=['POST'])
class PrinterFeieCallback(Resource):
    """飞鹅打印结果回调：需立即返回 SUCCESS，否则飞鹅 5 秒后重推"""

    def post(self):
        params = request.form.to_dict()
        return printer_service.handle_print_callback(params, request.remote_addr or '')


@ns_printer_cb.route('/callback/feie/scan', methods=['POST'])
class PrinterFeieScanCallback(Resource):
    """飞鹅扫码数据回调（无鉴权，飞鹅服务器调用）：需立即返回 SUCCESS 防止重推"""

    def post(self):
        params = request.form.to_dict()
        return printer_service.handle_scan_callback(params, request.remote_addr or '')


@ns_printer_cb.route('/callback/<filename>', methods=['GET'])
class PrinterFeieVerifyFile(Resource):
    """飞鹅域名验证文件（GET，无鉴权）

    飞鹅平台域名验证：https://域名/v1/printer/callback/feieyun_verify_xxx.txt
    文件名与内容来自飞鹅配置 verifyToken / scanVerifyToken（打印/扫码回调各一个），
    无需手动上传文件。
    """

    def get(self, filename):
        content = printer_service.handle_verify_file(filename)
        if content is None:
            return {'message': 'Not Found'}, 404
        return Response(content, mimetype='text/plain')
