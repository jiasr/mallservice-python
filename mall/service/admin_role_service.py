"""角色与菜单管理服务层"""
from oslo_log import log as logging

from mall.db.models.Admin.adminsql import AdminUserDao, _hash_password
from mall.db.models.Admin.model import AdminUser, AdminRole, AdminMenu, AdminRoleMenu
from mall.db.engines.mysql import get_session
from mall.common.common import Fail

LOG = logging.getLogger(__name__)


# ==================== 角色管理 ====================

def role_list():
    """获取角色列表"""
    session = get_session()
    with session.begin():
        roles = session.query(AdminRole).order_by(AdminRole.id).all()
        result = []
        for r in roles:
            result.append({
                "id": r.id,
                "name": r.name,
                "description": r.description or "",
                "status": r.status,
                "create_time": r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else "",
            })
        return {"list": result}


def role_create(name, description=""):
    """创建角色"""
    if not name or not name.strip():
        raise Fail("PARAM_ERROR", error_message="角色名称不能为空")
    session = get_session()
    with session.begin():
        exists = session.query(AdminRole).filter(AdminRole.name == name.strip()).first()
        if exists:
            raise Fail("DUPLICATE", error_message="角色名称已存在")
        role = AdminRole(name=name.strip(), description=description, status=1)
        session.add(role)
        session.flush()
        LOG.info("创建角色: {} (id={})".format(name, role.id))
        return {"id": role.id, "name": role.name}


def role_update(role_id, name=None, description=None, status=None):
    """更新角色"""
    session = get_session()
    with session.begin():
        role = session.query(AdminRole).filter(AdminRole.id == role_id).first()
        if not role:
            raise Fail("NOT_FOUND", error_message="角色不存在")
        if role_id == 1:
            raise Fail("FORBIDDEN", error_message="超级管理员角色不可修改")
        if name is not None:
            if not name.strip():
                raise Fail("PARAM_ERROR", error_message="角色名称不能为空")
            dup = session.query(AdminRole).filter(
                AdminRole.name == name.strip(), AdminRole.id != role_id
            ).first()
            if dup:
                raise Fail("DUPLICATE", error_message="角色名称已存在")
            role.name = name.strip()
        if description is not None:
            role.description = description
        if status is not None:
            role.status = status
        LOG.info("更新角色: id={}".format(role_id))
        return {"id": role.id, "name": role.name}


def role_delete(role_id):
    """删除角色"""
    if role_id == 1:
        raise Fail("FORBIDDEN", error_message="超级管理员角色不可删除")
    session = get_session()
    with session.begin():
        # 删除角色关联的菜单
        session.query(AdminRoleMenu).filter(AdminRoleMenu.role_id == role_id).delete()
        # 将该角色下的用户设为无角色
        session.query(AdminUser).filter(AdminUser.role_id == role_id).update({"role_id": None})
        session.query(AdminRole).filter(AdminRole.id == role_id).delete()
        LOG.info("删除角色: id={}".format(role_id))
        return {"message": "删除成功"}


# ==================== 角色菜单分配 ====================

def role_get_menus(role_id):
    """获取角色已分配的菜单ID列表"""
    session = get_session()
    with session.begin():
        menus = session.query(AdminRoleMenu.menu_id).filter(
            AdminRoleMenu.role_id == role_id
        ).all()
        return {"menu_ids": [m.menu_id for m in menus]}


def role_set_menus(role_id, menu_ids):
    """设置角色的菜单权限（全量替换）"""
    if role_id == 1:
        raise Fail("FORBIDDEN", error_message="超级管理员角色的权限不可修改")
    session = get_session()
    with session.begin():
        # 清除旧权限
        session.query(AdminRoleMenu).filter(AdminRoleMenu.role_id == role_id).delete()
        # 添加新权限
        for mid in (menu_ids or []):
            rm = AdminRoleMenu(role_id=role_id, menu_id=mid)
            session.add(rm)
        LOG.info("设置角色 {} 的菜单权限: {}".format(role_id, menu_ids))
        return {"message": "权限设置成功"}


# ==================== 菜单管理 ====================

def menu_list():
    """获取所有菜单（扁平列表）"""
    session = get_session()
    with session.begin():
        menus = session.query(AdminMenu).order_by(AdminMenu.sort_order).all()
        result = []
        for m in menus:
            result.append({
                "id": m.id,
                "name": m.name,
                "frontpath": m.frontpath or "",
                "icon": m.icon or "",
                "parent_id": m.parent_id,
                "sort_order": m.sort_order,
                "permission": m.permission or "",
                "visible": m.visible,
            })
        return {"list": result}


def menu_tree():
    """获取菜单树"""
    data = menu_list()
    tree = AdminUserDao.build_menu_tree(data["list"])
    return {"tree": tree}


def menu_create(name, frontpath="", icon="", parent_id=0, sort_order=0, permission="", visible=1):
    """创建菜单"""
    if not name or not name.strip():
        raise Fail("PARAM_ERROR", error_message="菜单名称不能为空")
    session = get_session()
    with session.begin():
        menu = AdminMenu(
            name=name.strip(),
            frontpath=frontpath,
            icon=icon,
            parent_id=parent_id,
            sort_order=sort_order,
            permission=permission,
            visible=visible,
        )
        session.add(menu)
        session.flush()
        LOG.info("创建菜单: {} (id={})".format(name, menu.id))
        return {"id": menu.id, "name": menu.name}


def menu_update(menu_id, **kwargs):
    """更新菜单"""
    session = get_session()
    with session.begin():
        menu = session.query(AdminMenu).filter(AdminMenu.id == menu_id).first()
        if not menu:
            raise Fail("NOT_FOUND", error_message="菜单不存在")
        for field in ["name", "frontpath", "icon", "parent_id", "sort_order", "permission", "visible"]:
            if field in kwargs and kwargs[field] is not None:
                setattr(menu, field, kwargs[field])
        LOG.info("更新菜单: id={}".format(menu_id))
        return {"id": menu.id, "name": menu.name}


def menu_delete(menu_id):
    """删除菜单及其子菜单"""
    session = get_session()
    with session.begin():
        # 收集所有需要删除的菜单ID（含子菜单）
        ids_to_delete = {menu_id}
        children = session.query(AdminMenu.id).filter(AdminMenu.parent_id == menu_id).all()
        for (cid,) in children:
            ids_to_delete.add(cid)
            # 递归孙子
            grandchildren = session.query(AdminMenu.id).filter(AdminMenu.parent_id == cid).all()
            for (gid,) in grandchildren:
                ids_to_delete.add(gid)

        # 删除角色关联
        session.query(AdminRoleMenu).filter(AdminRoleMenu.menu_id.in_(ids_to_delete)).delete(synchronize_session=False)
        # 删除菜单
        session.query(AdminMenu).filter(AdminMenu.id.in_(ids_to_delete)).delete(synchronize_session=False)
        LOG.info("删除菜单: ids={}".format(ids_to_delete))
        return {"message": "删除成功", "deleted_ids": list(ids_to_delete)}


def menu_save_sort(items):
    """保存菜单拖拽排序（整树全量更新）

    items: [{id, parent_id, sort_order}, ...]，按前端拖拽后的树顺序全量覆盖。
    仅更新 id/parent_id/sort_order 三个字段，避免影响其他配置。
    """
    if not items:
        return {"message": "无排序数据"}
    session = get_session()
    with session.begin():
        count = 0
        for it in items:
            menu = session.query(AdminMenu).filter(AdminMenu.id == int(it.get("id"))).first()
            if not menu:
                continue
            if "parent_id" in it and it.get("parent_id") is not None:
                menu.parent_id = int(it.get("parent_id", 0))
            if "sort_order" in it and it.get("sort_order") is not None:
                menu.sort_order = int(it.get("sort_order", 0))
            count += 1
        LOG.info("保存菜单排序: 共更新 {} 条".format(count))
        return {"message": "排序保存成功", "updated": count}


# ==================== 管理员用户管理 ====================

def admin_user_list():
    """获取管理员用户列表"""
    session = get_session()
    with session.begin():
        users = session.query(AdminUser).order_by(AdminUser.id).all()
        result = []
        for u in users:
            role_name = ""
            if u.role_id:
                role = session.query(AdminRole).filter(AdminRole.id == u.role_id).first()
                role_name = role.name if role else ""
            result.append({
                "id": u.id,
                "username": u.username,
                "avatar": u.avatar or "",
                "role_id": u.role_id,
                "role_name": role_name,
                "status": u.status,
                "create_time": u.create_time.strftime('%Y-%m-%d %H:%M:%S') if u.create_time else "",
            })
        return {"list": result}


def admin_user_create(username, password, role_id=None, status=1):
    """创建管理员用户"""
    if not username or not password:
        raise Fail("PARAM_ERROR", error_message="用户名和密码不能为空")
    session = get_session()
    with session.begin():
        exists = session.query(AdminUser).filter(AdminUser.username == username.strip()).first()
        if exists:
            raise Fail("DUPLICATE", error_message="用户名已存在")
        user = AdminUser(
            username=username.strip(),
            password_hash=_hash_password(password),
            role_id=role_id,
            status=status,
        )
        session.add(user)
        session.flush()
        LOG.info("创建管理员: {} (id={})".format(username, user.id))
        return {"id": user.id, "username": user.username}


def admin_user_update(user_id, username=None, password=None, role_id=None, status=None):
    """更新管理员用户"""
    session = get_session()
    with session.begin():
        user = session.query(AdminUser).filter(AdminUser.id == user_id).first()
        if not user:
            raise Fail("NOT_FOUND", error_message="用户不存在")
        if user_id == 1:
            # 超级管理员不可被修改角色或禁用
            if role_id is not None or status is not None:
                raise Fail("FORBIDDEN", error_message="超级管理员不可修改角色或状态")
        if username is not None:
            dup = session.query(AdminUser).filter(
                AdminUser.username == username.strip(), AdminUser.id != user_id
            ).first()
            if dup:
                raise Fail("DUPLICATE", error_message="用户名已存在")
            user.username = username.strip()
        if password is not None:
            user.password_hash = _hash_password(password)
        if role_id is not None:
            user.role_id = role_id
        if status is not None:
            user.status = status
        LOG.info("更新管理员: id={}".format(user_id))
        return {"id": user.id, "username": user.username}


def admin_user_delete(user_id):
    """删除管理员用户"""
    if user_id == 1:
        raise Fail("FORBIDDEN", error_message="超级管理员不可删除")
    session = get_session()
    with session.begin():
        session.query(AdminUser).filter(AdminUser.id == user_id).delete()
        LOG.info("删除管理员: id={}".format(user_id))
        return {"message": "删除成功"}
