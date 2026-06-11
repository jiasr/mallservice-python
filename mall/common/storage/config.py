"""存储配置读取模块

从数据库 StorageConfig 独立表读取对象存储配置。
"""
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def get_storage_config():
    """从数据库读取对象存储配置

    Returns:
        dict: {
            endpoint: str,
            access_key: str,
            secret_key: str,
            bucket_name: str,
            region: str,
            public_endpoint: str,
            upload_max_size: int,
            upload_allowed_types: str,
        }
    """
    try:
        from mall.db.engines.mysql import get_session
        from mall.db.models.StorageConfig.model import StorageConfig

        session = get_session()
        with session.begin():
            config = session.query(StorageConfig).first()

        if config:
            return {
                "endpoint": config.endpoint or "",
                "access_key": config.access_key or "",
                "secret_key": config.secret_key or "",
                "bucket_name": config.bucket_name or "",
                "region": config.region or "us-east-1",
                "public_endpoint": config.public_endpoint or "",
                "upload_max_size": config.upload_max_size or 10,
                "upload_allowed_types": config.upload_allowed_types or "jpg,jpeg,png,gif,webp,bmp",
            }
    except Exception as e:
        LOG.warning("从数据库加载存储配置失败: {}".format(e))

    # 返回默认值
    return {
        "endpoint": "http://127.0.0.1:9000",
        "access_key": "",
        "secret_key": "",
        "bucket_name": "mall-images",
        "region": "us-east-1",
        "public_endpoint": "http://127.0.0.1:9000",
        "upload_max_size": 10,
        "upload_allowed_types": "jpg,jpeg,png,gif,webp,bmp",
    }
