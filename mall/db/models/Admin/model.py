"""管理员相关数据模型：用户、角色、菜单、角色-菜单关联"""
from datetime import datetime
from mall.db.models.base import BASE, DbBase
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey
)


class AdminUser(BASE, DbBase):
    """管理员用户表"""
    __tablename__ = 't_mall_admin_user'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, comment='用户名')
    password_hash = Column(String(128), nullable=False, comment='密码哈希')
    avatar = Column(String(500), default='', comment='头像URL')
    role_id = Column(Integer, ForeignKey('t_mall_admin_role.id'), comment='角色ID')
    status = Column(Integer, default=1, comment='状态 1启用 0禁用')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AdminRole(BASE, DbBase):
    """管理员角色表"""
    __tablename__ = 't_mall_admin_role'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, comment='角色名称')
    description = Column(String(255), default='', comment='角色描述')
    status = Column(Integer, default=1, comment='状态 1启用 0禁用')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AdminMenu(BASE, DbBase):
    """管理员菜单/权限表"""
    __tablename__ = 't_mall_admin_menu'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, comment='菜单名称')
    frontpath = Column(String(255), default='', comment='前端路由路径')
    icon = Column(String(64), default='', comment='图标名称')
    parent_id = Column(Integer, default=0, comment='父菜单ID,0为顶级')
    sort_order = Column(Integer, default=0, comment='排序号')
    permission = Column(String(128), default='', comment='权限标识如 goods:add')
    visible = Column(Integer, default=1, comment='是否可见 1是 0否')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AdminRoleMenu(BASE, DbBase):
    """角色-菜单关联表"""
    __tablename__ = 't_mall_admin_role_menu'

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey('t_mall_admin_role.id'), nullable=False, comment='角色ID')
    menu_id = Column(Integer, ForeignKey('t_mall_admin_menu.id'), nullable=False, comment='菜单ID')
    create_time = Column(DateTime, default=datetime.now)
