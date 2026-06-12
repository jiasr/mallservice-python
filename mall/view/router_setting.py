"""系统设置 API 路由"""
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource
from oslo_log import log as logging

from mall.common.common import admin_required, deco_catch_view_exception
from mall.service import setting_service

LOG = logging.getLogger(__name__)

app_setting = Blueprint('setting', __name__)
ns_setting = Namespace("setting", description="setting ", path="/v1/admin")


@ns_setting.route('/setting/get', methods=['POST', 'GET'])
class SettingGet(Resource):
    """获取系统设置"""

    @admin_required
    @deco_catch_view_exception("获取系统设置")
    def post(self):
        return setting_service.get_all_settings()

    def get(self):
        return self.post()


@ns_setting.route('/setting/save', methods=['POST'])
class SettingSave(Resource):
    """保存系统设置"""

    @admin_required
    @deco_catch_view_exception("保存系统设置")
    def post(self):
        data = json.loads(request.data)
        success = setting_service.save_settings(data)
        return {"success": success}
