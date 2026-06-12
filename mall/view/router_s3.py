"""对象存储配置 API 路由"""
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource
from oslo_log import log as logging

from mall.common.common import admin_required, deco_catch_view_exception
from mall.db.engines.s3 import test_connection_with_config, list_objects, delete_object
from mall.service import s3_config_service

LOG = logging.getLogger(__name__)

app_storage = Blueprint('storage', __name__)
ns_storage = Namespace("storage", description="对象存储配置", path="/v1/admin")


@ns_storage.route('/storage/get', methods=['POST', 'GET'])
class StorageGet(Resource):
    """获取对象存储配置"""

    @admin_required
    @deco_catch_view_exception("获取存储配置")
    def post(self):
        return s3_config_service.get_storage_config()

    def get(self):
        return self.post()


@ns_storage.route('/storage/save', methods=['POST'])
class StorageSave(Resource):
    """保存对象存储配置"""

    @admin_required
    @deco_catch_view_exception("保存存储配置")
    def post(self):
        data = json.loads(request.data)
        success = s3_config_service.save_storage_config(data)
        return {"success": success}


@ns_storage.route('/storage/test', methods=['POST'])
class StorageTest(Resource):
    """测试存储连接"""

    @admin_required
    @deco_catch_view_exception("测试存储连接")
    def post(self):
        data = json.loads(request.data) if request.data else {}
        ok, err = test_connection_with_config(data)
        if ok:
            return {"success": True, "message": "连接成功"}
        else:
            return {"success": False, "message": "连接失败: " + (err or "未知错误")}


@ns_storage.route('/storage/files', methods=['GET'])
class StorageFiles(Resource):
    """获取文件列表"""

    @admin_required
    @deco_catch_view_exception("获取文件列表")
    def get(self):
        prefix = request.args.get("prefix", "")
        result = list_objects(prefix=prefix)
        return {"success": True, "data": result}


@ns_storage.route('/storage/files/delete', methods=['POST'])
class StorageFileDelete(Resource):
    """删除文件"""

    @admin_required
    @deco_catch_view_exception("删除文件")
    def post(self):
        data = json.loads(request.data)
        key = data.get("key", "")
        if not key:
            return {"success": False, "message": "缺少 key 参数"}
        ok = delete_object(key)
        return {"success": ok, "message": "删除成功" if ok else "删除失败"}
