# -*- encoding : utf-8 -*-
import json

from flask import Blueprint
from flask import request
from flask_restx import Namespace, Resource, fields
from oslo_log import log as logging
from mall.service import  user_service
from mall.service import image_service
from mall.common.common import deco_catch_view_exception, admin_required

LOG = logging.getLogger(__name__)

app_user = Blueprint('user', __name__)
ns_user = Namespace("crud demo", description="用户测试", path="/v1/user")


@ns_user.route('/add', methods=['POST'])
class UserAdd(Resource):

    def post(self):
        data = json.loads(request.data)
        return user_service.user_add(data)


@ns_user.route('/list', methods=['GET'])
class UserList(Resource):
    def get(self):
        params = request.args
        return user_service.user_list(params)


@ns_user.route('/wx_login', methods=['POST'])
class UserList(Resource):
    def post(self):
        data = json.loads(request.data)
        return user_service.wx_login(data)


@ns_user.route('/wx_phone', methods=['POST'])
class UserWxPhone(Resource):
    def post(self):
        data = json.loads(request.data)
        user_id = request.headers.get('token', '') or request.headers.get('userid', '')
        if not user_id:
            return {"success": False, "message": "未登录"}
        return user_service.wx_phone(user_id, data)


@ns_user.route('/info', methods=['GET'])
class UserInfo(Resource):
    def get(self):
        user_id = request.headers.get('token', '') or request.headers.get('userid', '')
        return user_service.user_info(user_id)


@ns_user.route('/updateProfile', methods=['POST'])
class UserUpdateProfile(Resource):
    @deco_catch_view_exception("更新用户信息")
    def post(self):
        user_id = request.headers.get('token', '') or request.headers.get('userid', '')
        if not user_id:
            return {"success": False, "message": "未登录"}
        data = json.loads(request.data)
        return user_service.update_profile(user_id, data)


@ns_user.route('/upload_avatar', methods=['POST'])
class UserUploadAvatar(Resource):
    """小程序用户上传头像：文件发后端转存，返回可访问的图片URL

    前端 wx.chooseAvatar 返回的是本地临时路径(http://tmp/...)，不能直接存库，
    必须先通过本接口上传到对象存储，拿到 public_url 后再调用 updateProfile 保存。
    """

    @deco_catch_view_exception("上传头像")
    def post(self):
        user_id = request.headers.get('token', '') or request.headers.get('userid', '')
        if not user_id:
            return {"success": False, "message": "未登录"}
        if 'file' not in request.files:
            return {"success": False, "message": "没有上传文件"}
        file = request.files['file']
        file_data = file.read()
        if not file_data:
            return {"success": False, "message": "文件为空"}
        # 检查文件大小（5MB）
        max_size = 5 * 1024 * 1024
        if len(file_data) > max_size:
            return {"success": False, "message": "文件大小超过限制（5MB）"}
        filename = file.filename or 'avatar.jpg'
        result = image_service.upload_file('avatar', file_data, filename)
        # relative_url 用于存库(避免硬编码IP/端口)；public_url 供前端临时预览
        relative_url = result.get('relative_url') or result.get('object_name', '')
        public_url = result.get('public_url', '')
        return {"success": True, "data": {"relative_url": relative_url, "public_url": public_url}}


# ========== 后台用户管理接口 ==========

@ns_user.route('/admin/list', methods=['GET'])
class UserAdminList(Resource):
    """后台用户列表（分页 + 条件筛选）"""
    @admin_required
    def get(self):
        params = request.args
        return user_service.admin_user_list(params)


@ns_user.route('/admin/detail', methods=['GET'])
class UserAdminDetail(Resource):
    """后台用户详情"""
    @admin_required
    def get(self):
        user_id = request.args.get("id", "")
        if not user_id:
            return {"success": False, "message": "缺少用户id"}
        return user_service.admin_user_detail(user_id)


@ns_user.route('/admin/status/<user_id>', methods=['POST'])
class UserAdminStatus(Resource):
    """后台禁用/启用用户"""
    @admin_required
    def post(self, user_id):
        data = json.loads(request.data)
        return user_service.admin_user_set_status(user_id, data)


@ns_user.route('/admin/delete/<user_id>', methods=['POST'])
class UserAdminDelete(Resource):
    """后台删除用户"""
    @admin_required
    def post(self, user_id):
        return user_service.admin_user_delete(user_id)