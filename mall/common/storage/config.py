"""存储配置读取模块

从数据库 StorageConfig 独立表读取对象存储配置。
"""
from oslo_log import log as logging
from mall.db.engines.mysql import get_session
from mall.db.models.StorageConfig.model import StorageConfig

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
        }
    """
    try:
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
            }
    except Exception as e:
        LOG.warning("从数据库加载存储配置失败: {}".format(e))

    # 返回默认值
    return {
        "endpoint": "http://82.156.225.136:9000",
        "access_key": "admin",
        "secret_key": "password123",
        "bucket_name": "mall-images1",
        "region": "us-east-1",
        "public_endpoint": "http://82.156.225.136:9000",
    }
