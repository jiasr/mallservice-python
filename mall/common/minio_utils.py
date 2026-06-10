"""MinIO 对象存储工具类"""
import os
import uuid
from datetime import timedelta

from minio import Minio
from minio.error import S3Error
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

# 默认配置（可通过系统设置覆盖）
DEFAULT_CONFIG = {
    "endpoint": "127.0.0.1:9000",
    "access_key": "minioadmin",
    "secret_key": "minioadmin",
    "bucket_name": "mall-images",
    "secure": False,
    "public_endpoint": "http://127.0.0.1:9000",  # 公网访问地址
}

_client = None
_current_config_hash = None


def _get_config():
    """从数据库获取 MinIO 配置，如果数据库中没有则使用默认值"""
    try:
        from mall.db.engines.mysql import get_session
        from mall.db.models.SystemConfig.model import SystemConfig

        session = get_session()
        with session.begin():
            configs = session.query(SystemConfig).filter(
                SystemConfig.config_key.in_([
                    "minio_endpoint", "minio_access_key", "minio_secret_key",
                    "minio_bucket_name", "minio_secure", "minio_public_endpoint",
                ])
            ).all()

        config_dict = {c.config_key: c.config_value for c in configs}

        return {
            "endpoint": config_dict.get("minio_endpoint") or DEFAULT_CONFIG["endpoint"],
            "access_key": config_dict.get("minio_access_key") or DEFAULT_CONFIG["access_key"],
            "secret_key": config_dict.get("minio_secret_key") or DEFAULT_CONFIG["secret_key"],
            "bucket_name": config_dict.get("minio_bucket_name") or DEFAULT_CONFIG["bucket_name"],
            "secure": config_dict.get("minio_secure", "false").lower() == "true",
            "public_endpoint": config_dict.get("minio_public_endpoint") or DEFAULT_CONFIG["public_endpoint"],
        }
    except Exception as e:
        LOG.warning("从数据库加载 MinIO 配置失败，使用默认配置: {}".format(e))
        return dict(DEFAULT_CONFIG)


def get_minio_client():
    """获取 MinIO 客户端（单例模式，配置变化时自动重建）"""
    global _client, _current_config_hash

    config = _get_config()
    config_hash = str(sorted(config.items()))

    if _client is None or config_hash != _current_config_hash:
        _client = Minio(
            endpoint=config["endpoint"],
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            secure=config["secure"],
        )
        _current_config_hash = config_hash

        # 确保 bucket 存在
        _ensure_bucket(_client, config["bucket_name"])

    return _client, config


def _ensure_bucket(client, bucket_name):
    """确保 bucket 存在，不存在则创建并设为公开读"""
    try:
        found = client.bucket_exists(bucket_name)
        if not found:
            client.make_bucket(bucket_name)
            LOG.info("已创建 MinIO bucket: {}".format(bucket_name))

            # 设置 bucket 为公开读策略
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": ["arn:aws:s3:::{}/*".format(bucket_name)],
                    }
                ],
            }
            client.set_bucket_policy(bucket_name, str(policy).replace("'", '"'))
            LOG.info("已设置 bucket {} 为公开读权限".format(bucket_name))
        else:
            LOG.info("MinIO bucket {} 已存在".format(bucket_name))
    except S3Error as e:
        LOG.error("MinIO bucket 操作失败: {}".format(e))


def generate_object_name(prefix, filename):
    """生成唯一的对象名称

    Args:
        prefix: 目录前缀，如 'images/product'
        filename: 原始文件名

    Returns:
        str: 唯一对象名，如 'images/product/202406/a1b2c3d4.jpg'
    """
    from datetime import datetime

    ext = os.path.splitext(filename)[1] if '.' in filename else '.jpg'
    date_prefix = datetime.now().strftime('%Y%m')
    unique_id = uuid.uuid4().hex[:12]
    object_name = "{}/{}/{}{}".format(prefix, date_prefix, unique_id, ext)
    return object_name


def get_presigned_upload_url(object_name, expires=300):
    """生成预签名上传 URL

    Args:
        object_name: 对象名称（含路径）
        expires: URL 有效期（秒），默认 5 分钟

    Returns:
        str: 预签名上传 URL
    """
    client, config = get_minio_client()
    url = client.presigned_put_object(
        bucket_name=config["bucket_name"],
        object_name=object_name,
        expires=timedelta(seconds=expires),
    )
    return url


def get_public_url(object_name):
    """获取对象公网访问 URL

    Args:
        object_name: 对象名称（含路径）

    Returns:
        str: 公网 URL
    """
    _, config = get_minio_client()
    public_endpoint = config["public_endpoint"].rstrip('/')
    bucket = config["bucket_name"]
    return "{}/{}/{}".format(public_endpoint, bucket, object_name)


def delete_file(object_name):
    """删除 MinIO 中的文件

    Args:
        object_name: 对象名称（含路径）

    Returns:
        bool: 是否删除成功
    """
    try:
        client, config = get_minio_client()
        client.remove_object(config["bucket_name"], object_name)
        return True
    except S3Error as e:
        LOG.error("MinIO 删除文件失败: {}".format(e))
        return False


def upload_file(object_name, file_path_or_data, content_type=None):
    """服务端直接上传文件到 MinIO

    Args:
        object_name: 对象名称（含路径）
        file_path_or_data: 文件路径或二进制数据
        content_type: MIME 类型

    Returns:
        str: 公网 URL
    """
    client, config = get_minio_client()

    if isinstance(file_path_or_data, str):
        # 文件路径
        with open(file_path_or_data, 'rb') as f:
            data = f.read()
            length = os.path.getsize(file_path_or_data)
    else:
        # 二进制数据
        data = file_path_or_data
        length = len(data)

    from io import BytesIO
    client.put_object(
        bucket_name=config["bucket_name"],
        object_name=object_name,
        data=BytesIO(data),
        length=length,
        content_type=content_type or 'application/octet-stream',
    )

    return get_public_url(object_name)
