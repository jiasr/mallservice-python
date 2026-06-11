"""对象存储工具函数"""
import os
import uuid
from datetime import datetime


def generate_object_name(prefix, filename):
    """生成唯一的对象名称

    Args:
        prefix: 目录前缀，如 'images/product'
        filename: 原始文件名

    Returns:
        str: 唯一对象名，如 'images/product/202406/a1b2c3d4.jpg'
    """
    ext = os.path.splitext(filename)[1] if '.' in filename else '.jpg'
    date_prefix = datetime.now().strftime('%Y%m')
    unique_id = uuid.uuid4().hex[:12]
    object_name = "{}/{}/{}{}".format(prefix, date_prefix, unique_id, ext)
    return object_name
