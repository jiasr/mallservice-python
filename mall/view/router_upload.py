"""图片上传 API 路由"""
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource
from oslo_log import log as logging

from mall.common.common import admin_required, deco_catch_view_exception, result_ok
from mall.service import image_service

LOG = logging.getLogger(__name__)

app_upload = Blueprint('upload', __name__)
ns_upload = Namespace("upload", description="upload ", path="/v1/upload")


@ns_upload.route('/credential', methods=['POST'])
class UploadCredential(Resource):
    """获取上传凭证"""

    @admin_required
    @deco_catch_view_exception("获取上传凭证")
    def post(self):
        data = json.loads(request.data)
        scene = data.get("scene", "product")
        filename = data.get("filename", "image.jpg")
        count = data.get("count", 1)

        result = image_service.get_upload_credential(scene, filename, count)
        return result


@ns_upload.route('/confirm', methods=['POST'])
class UploadConfirm(Resource):
    """确认上传完成"""

    @admin_required
    @deco_catch_view_exception("确认上传")
    def post(self):
        data = json.loads(request.data)
        object_name = data.get("object_name", "")

        result = image_service.confirm_upload(object_name)
        return result


@ns_upload.route('/delete', methods=['POST'])
class UploadDelete(Resource):
    """删除图片"""

    @admin_required
    @deco_catch_view_exception("删除图片")
    def post(self):
        data = json.loads(request.data)
        object_name = data.get("object_name", "")

        success = image_service.delete_image(object_name)
        return {"success": success}


@ns_upload.route('/file', methods=['POST'])
class UploadFile(Resource):
    """服务端代理上传文件（不经过浏览器直传 MinIO）"""

    @admin_required
    def post(self):
        if 'file' not in request.files:
            return result_ok({"success": False, "message": "没有上传文件"})

        file = request.files['file']
        scene = request.form.get('scene', 'product')
        filename = file.filename or 'image.jpg'
        file_data = file.read()

        # 检查文件大小（10MB）
        max_size = 10 * 1024 * 1024
        if len(file_data) > max_size:
            return result_ok({"success": False, "message": "文件大小超过限制（10MB）"})

        result = image_service.upload_file(scene, file_data, filename)
        return result_ok({"success": True, "data": result})



