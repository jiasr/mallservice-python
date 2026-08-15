"""图片上传服务（基于统一 boto3 S3 存储）"""
from mall.common.objectsto_utils import generate_object_name
from mall.db.engines import s3
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

# 场景到存储路径的映射
SCENE_PREFIX_MAP = {
    "product": "images/goods",         # 商品图片
    "editor": "images/goods",          # 富文本编辑器图片
    "avatar": "images/avatar",         # 头像（单独目录，与商品图分开）
    "banner": "images/goods",          # Banner
    "system": "images/system",         # 系统图片（Logo 等）
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

        upload_url = s3.get_presigned_upload_url(obj_name)
        # bucket 已设为公开读，直接使用公网 URL（不会过期）
        public_url = s3.get_public_url(obj_name)

        credentials.append({
            "object_name": obj_name,
            "upload_url": upload_url,
            "public_url": public_url,
        })

    return {"credentials": credentials}


def confirm_upload(object_name):
    """确认上传完成（检查文件是否已存在于存储中）

    Args:
        object_name: 对象名称

    Returns:
        dict or None: {"object_name": "...", "public_url": "..."}
    """
    try:
        if s3.object_exists(object_name):
            public_url = s3.get_public_url(object_name)
            return {
                "object_name": object_name,
                "public_url": public_url,
            }
        else:
            LOG.warning("确认上传时文件不存在: {}".format(object_name))
            return None
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
    return s3.delete_object(object_name)


def upload_file(scene, file_data, filename):
    """服务端直接上传文件到存储（代理上传，不依赖浏览器直传）

    对于 system 场景（Logo），上传后自动删除旧文件。

    Args:
        scene: 场景标识（product/system/avatar/banner/editor）
        file_data: 文件二进制数据 (bytes)
        filename: 原始文件名

    Returns:
        dict: {"object_name": str, "public_url": str}
    """
    prefix = SCENE_PREFIX_MAP.get(scene, "images/other")
    obj_name = generate_object_name(prefix, filename)

    # 如果是 Logo 更新，先查出旧图 key
    old_key = None
    if scene == 'system':
        try:
            from mall.db.models.SystemConfig.model import SystemConfig
            from mall.db.engines.mysql import get_session
            session = get_session()
            with session.begin():
                cfg = session.query(SystemConfig).filter(
                    SystemConfig.config_key == 'logo'
                ).first()
                if cfg and cfg.config_value:
                    val = cfg.config_value
                    # 相对路径格式: /mall-images1/images/system/xxx.jpg
                    # 提取 object key: images/system/xxx.jpg
                    if val.startswith('/'):
                        parts = val.split('/', 2)
                        if len(parts) > 2:
                            old_key = parts[2]
        except Exception:
            pass

    # 上传新文件
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    content_type = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'gif': 'image/gif',
        'webp': 'image/webp', 'bmp': 'image/bmp',
    }.get(ext, 'application/octet-stream')

    s3.upload_file(obj_name, file_data, content_type)

    # 删除旧 Logo
    if old_key:
        try:
            s3.delete_object(old_key)
            LOG.info("已删除旧 Logo: {}".format(old_key))
        except Exception:
            pass

    relative_url = s3.get_relative_url(obj_name)
    full_url = s3.get_image_display_url(relative_url)
    return {
        "object_name": obj_name,
        "public_url": full_url,
        "relative_url": relative_url,
    }


def test_storage_connection():
    """测试当前存储连接

    Returns:
        bool: 连接是否正常
    """
    return s3.test_connection()
