"""对象存储配置服务 - 处理 StorageConfig 的读写
保存时同时重置 S3 client 单例，读路径统一走 storage/config.py（含缓存）
"""
from mall.db.engines.mysql import get_session
from mall.db.models.StorageConfig.model import StorageConfig
from mall.db.engines.storage import reset_client
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def get_storage_config():
    """获取对象存储配置（仅回显用，业务读走 storage/config.py）"""
    session = get_session()
    try:
        with session.begin():
            config = session.query(StorageConfig).first()
            if config:
                return {
                    "endpoint": config.endpoint or "",
                    "access_key": config.access_key or "",
                    "secret_key": config.secret_key or "",
                    "bucket_name": config.bucket_name or "",
                    "region": config.region or "",
                    "public_endpoint": config.public_endpoint or "",
                }
            return {}
    except Exception as e:
        LOG.error("获取存储配置失败: {}".format(e))
        return {}


def save_storage_config(data):
    """保存对象存储配置并重置 S3 client"""
    session = get_session()
    try:
        with session.begin():
            config = session.query(StorageConfig).first()
            if not config:
                config = StorageConfig()
                session.add(config)

            for field in ("endpoint", "access_key", "secret_key", "bucket_name",
                          "region", "public_endpoint"):
                if field in data:
                    setattr(config, field, data[field])

        reset_client()
        LOG.info("存储配置保存成功")
        return True
    except Exception as e:
        LOG.error("保存存储配置失败: {}".format(e))
        return False
