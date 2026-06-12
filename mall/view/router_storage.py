"""对象存储配置 API 路由"""
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource
from oslo_log import log as logging

from mall.common.common import admin_required, deco_catch_view_exception
from mall.db.engines.storage import test_connection
from mall.service import storage_config_service

LOG = logging.getLogger(__name__)

app_storage = Blueprint('storage', __name__)
ns_storage = Namespace("storage", description="对象存储配置", path="/v1/admin")


@ns_storage.route('/storage/get', methods=['POST', 'GET'])
class StorageGet(Resource):
    """获取对象存储配置"""

    @admin_required
    @deco_catch_view_exception("获取存储配置")
    def post(self):
        return storage_config_service.get_storage_config()

    def get(self):
        return self.post()


@ns_storage.route('/storage/save', methods=['POST'])
class StorageSave(Resource):
    """保存对象存储配置"""

    @admin_required
    @deco_catch_view_exception("保存存储配置")
    def post(self):
        data = json.loads(request.data)
        success = storage_config_service.save_storage_config(data)
        return {"success": success}


@ns_storage.route('/storage/test', methods=['POST'])
class StorageTest(Resource):
    """测试存储连接"""

    @admin_required
    @deco_catch_view_exception("测试存储连接")
    def post(self):
        ok = test_connection()
        if ok:
            return {"success": True, "message": "连接成功"}
        else:
            return {"success": False, "message": "连接失败", "data": {}}
