"""对象存储工具函数"""
import os
import uuid
from datetime import datetime


def generate_object_name(prefix, filename):
    """生成唯一的对象名称

    Args:
        prefix: 目录前缀，如 'images/goods'
        filename: 原始文件名

    Returns:
        str: 唯一对象名，如 'images/goods/a1b2c3d4.jpg'
    """
    ext = os.path.splitext(filename)[1] if '.' in filename else '.jpg'
    unique_id = uuid.uuid4().hex
    object_name = "{}/{}{}".format(prefix, unique_id, ext)
    return object_name
