"""图片上传服务"""
from mall.common.minio_utils import (
    get_minio_client,
    generate_object_name,
    get_presigned_upload_url,
    get_public_url,
    delete_file,
)
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

# 场景到存储路径的映射
SCENE_PREFIX_MAP = {
    "product": "images/product",       # 商品图片
    "system": "images/system",         # 系统图片（Logo 等）
    "avatar": "images/avatar",         # 头像
    "banner": "images/banner",         # Banner
    "editor": "images/editor",         # 富文本编辑器
}


def get_upload_credential(scene, filename, count=1):
    """获取上传凭证

    Args:
        scene: 场景标识（product/system/avatar/banner/editor）
        filename: 原始文件名（单文件时）或文件扩展名（批量时）
        count: 上传文件数量

    Returns:
        dict: {
            "credentials": [
                {
                    "object_name": "images/product/202406/xxx.jpg",
                    "upload_url": "http://...",
                    "public_url": "http://..."
                }
            ]
        }
    """
    prefix = SCENE_PREFIX_MAP.get(scene, "images/other")

    credentials = []
    for i in range(count):
        if count == 1:
            obj_name = generate_object_name(prefix, filename)
        else:
            obj_name = generate_object_name(prefix, "file_{}{}".format(i, filename))

        upload_url = get_presigned_upload_url(obj_name)
        public_url = get_public_url(obj_name)

        credentials.append({
            "object_name": obj_name,
            "upload_url": upload_url,
            "public_url": public_url,
        })

    return {"credentials": credentials}


def confirm_upload(object_name):
    """确认上传完成（可选：检查文件是否存在）

    Args:
        object_name: 对象名称

    Returns:
        dict: {"object_name": "...", "public_url": "..."}
    """
    try:
        client, config = get_minio_client()
        client.stat_object(config["bucket_name"], object_name)
        public_url = get_public_url(object_name)
        return {
            "object_name": object_name,
            "public_url": public_url,
        }
    except Exception as e:
        LOG.error("确认上传失败: {}".format(e))
        return None


def delete_image(object_name):
    """删除图片

    Args:
        object_name: 对象名称

    Returns:
        bool: 是否成功
    """
    return delete_file(object_name)
