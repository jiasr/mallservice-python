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


# ==================== 通用系统配置 ====================

@ns_setting.route('/setting/get', methods=['POST', 'GET'])
class SettingGet(Resource):
    """获取系统设置"""

    @admin_required
    @deco_catch_view_exception("获取系统设置")
    def post(self):
        return setting_service.get_all_settings()

    def get(self):
        """兼容 GET 请求"""
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


# ==================== 对象存储配置（独立表） ====================

@ns_setting.route('/storage/get', methods=['POST', 'GET'])
class StorageGet(Resource):
    """获取对象存储配置"""

    @admin_required
    @deco_catch_view_exception("获取存储配置")
    def post(self):
        return setting_service.get_storage_settings()

    def get(self):
        """兼容 GET 请求"""
        return self.post()


@ns_setting.route('/storage/save', methods=['POST'])
class StorageSave(Resource):
    """保存对象存储配置"""

    @admin_required
    @deco_catch_view_exception("保存存储配置")
    def post(self):
        data = json.loads(request.data)
        success = setting_service.save_storage_settings(data)
        return {"success": success}
