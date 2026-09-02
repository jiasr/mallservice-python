# -*- encoding : utf-8 -*-
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource, fields
from oslo_log import log as logging

from mall.common.common import admin_required, deco_catch_view_exception
from mall.common.jwt_utils import verify_token
from mall.service import admin_service, admin_role_service

LOG = logging.getLogger(__name__)

app_admin = Blueprint('admin', __name__)
ns_admin = Namespace("admin", description="admin ", path="/v1/admin")


@ns_admin.route('/login', methods=['POST'])
class AdminLogin(Resource):

    @deco_catch_view_exception("管理员登录")
    def post(self):
        data = json.loads(request.data)
        username = data.get("username", "")
        password = data.get("password", "")
        LOG.info("管理员登录请求: username={}".format(username))
        result = admin_service.admin_login(username, password)
        return result


@ns_admin.route('/getinfo', methods=['POST'])
class AdminGetInfo(Resource):

    @deco_catch_view_exception("获取管理员信息")
    def post(self):
        token = request.headers.get("token") or request.headers.get("Authorization")
        if token and token.startswith("Bearer "):
            token = token[7:]

        payload = verify_token(token)
        if payload is None:
            return {"flag": False, "errCode": 401, "errMessage": "登录已过期", "resData": None}

        admin_id = payload.get("admin_id")
        result = admin_service.admin_getinfo(admin_id)
        return result


@ns_admin.route('/logout', methods=['POST'])
class AdminLogout(Resource):

    @admin_required
    @deco_catch_view_exception("管理员登出")
    def post(self):
        result = admin_service.admin_logout(request.admin_id)
        return result


@ns_admin.route('/updatepassword', methods=['POST'])
class AdminUpdatePassword(Resource):

    @admin_required
    @deco_catch_view_exception("修改密码")
    def post(self):
        data = json.loads(request.data)
        old_password = data.get("oldpassword", "")
        new_password = data.get("newpassword", "")
        result = admin_service.admin_update_password(
            request.admin_id, old_password, new_password
        )
        return result


# ==================== 角色管理 ====================

@ns_admin.route('/role/list', methods=['POST'])
class AdminRoleList(Resource):

    @admin_required
    @deco_catch_view_exception("角色列表")
    def post(self):
        return admin_role_service.role_list()


@ns_admin.route('/role/create', methods=['POST'])
class AdminRoleCreate(Resource):

    @admin_required
    @deco_catch_view_exception("创建角色")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.role_create(
            name=data.get("name", ""),
            description=data.get("description", ""),
        )


@ns_admin.route('/role/update', methods=['POST'])
class AdminRoleUpdate(Resource):

    @admin_required
    @deco_catch_view_exception("更新角色")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.role_update(
            role_id=data.get("id"),
            name=data.get("name"),
            description=data.get("description"),
            status=data.get("status"),
        )


@ns_admin.route('/role/delete', methods=['POST'])
class AdminRoleDelete(Resource):

    @admin_required
    @deco_catch_view_exception("删除角色")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.role_delete(role_id=data.get("id"))


# ==================== 角色菜单分配 ====================

@ns_admin.route('/role/menus', methods=['POST'])
class AdminRoleMenus(Resource):

    @admin_required
    @deco_catch_view_exception("获取角色菜单")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.role_get_menus(role_id=data.get("role_id"))


@ns_admin.route('/role/set_menus', methods=['POST'])
class AdminRoleSetMenus(Resource):

    @admin_required
    @deco_catch_view_exception("设置角色菜单")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.role_set_menus(
            role_id=data.get("role_id"),
            menu_ids=data.get("menu_ids", []),
        )


# ==================== 菜单管理 ====================

@ns_admin.route('/menu/list', methods=['POST'])
class AdminMenuList(Resource):

    @admin_required
    @deco_catch_view_exception("菜单列表")
    def post(self):
        return admin_role_service.menu_list()


@ns_admin.route('/menu/tree', methods=['POST'])
class AdminMenuTree(Resource):

    @admin_required
    @deco_catch_view_exception("菜单树")
    def post(self):
        return admin_role_service.menu_tree()


@ns_admin.route('/menu/create', methods=['POST'])
class AdminMenuCreate(Resource):

    @admin_required
    @deco_catch_view_exception("创建菜单")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.menu_create(
            name=data.get("name", ""),
            frontpath=data.get("frontpath", ""),
            icon=data.get("icon", ""),
            parent_id=data.get("parent_id", 0),
            sort_order=data.get("sort_order", 0),
            permission=data.get("permission", ""),
            visible=data.get("visible", 1),
        )


@ns_admin.route('/menu/update', methods=['POST'])
class AdminMenuUpdate(Resource):

    @admin_required
    @deco_catch_view_exception("更新菜单")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.menu_update(
            menu_id=data.get("id"),
            name=data.get("name"),
            frontpath=data.get("frontpath"),
            icon=data.get("icon"),
            parent_id=data.get("parent_id"),
            sort_order=data.get("sort_order"),
            permission=data.get("permission"),
            visible=data.get("visible"),
        )


@ns_admin.route('/menu/delete', methods=['POST'])
class AdminMenuDelete(Resource):

    @admin_required
    @deco_catch_view_exception("删除菜单")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.menu_delete(menu_id=data.get("id"))


@ns_admin.route('/menu/save_sort', methods=['POST'])
class AdminMenuSaveSort(Resource):

    @admin_required
    @deco_catch_view_exception("保存菜单排序")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.menu_save_sort(items=data.get("items") or [])


# ==================== 管理员用户管理 ====================

@ns_admin.route('/user/list', methods=['POST'])
class AdminUserList(Resource):

    @admin_required
    @deco_catch_view_exception("管理员列表")
    def post(self):
        return admin_role_service.admin_user_list()


@ns_admin.route('/user/create', methods=['POST'])
class AdminUserCreate(Resource):

    @admin_required
    @deco_catch_view_exception("创建管理员")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.admin_user_create(
            username=data.get("username", ""),
            password=data.get("password", ""),
            role_id=data.get("role_id"),
            status=data.get("status", 1),
        )


@ns_admin.route('/user/update', methods=['POST'])
class AdminUserUpdate(Resource):

    @admin_required
    @deco_catch_view_exception("更新管理员")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.admin_user_update(
            user_id=data.get("id"),
            username=data.get("username"),
            password=data.get("password"),
            role_id=data.get("role_id"),
            status=data.get("status"),
        )


@ns_admin.route('/user/delete', methods=['POST'])
class AdminUserDelete(Resource):

    @admin_required
    @deco_catch_view_exception("删除管理员")
    def post(self):
        data = json.loads(request.data)
        return admin_role_service.admin_user_delete(user_id=data.get("id"))
