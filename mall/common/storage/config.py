"""存储配置读取模块

从数据库 SystemConfig 表读取对象存储配置。
"""
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

# 对象存储配置 key（与数据库 config_key 一一对应）
_STORAGE_KEYS = [
    "objectsto_endpoint",       # S3 端点地址（如 http://127.0.0.1:9000）
    "objectsto_access_key",     # AccessKey ID
    "objectsto_secret_key",     # AccessKey Secret
    "objectsto_bucket_name",    # Bucket 名称
    "objectsto_region",         # 地域（S3 默认 us-east-1）
    "objectsto_public_endpoint",# 公网访问地址
]

# 配置 key -> 内部字段名映射
_KEY_FIELD_MAP = {
    "objectsto_endpoint": "endpoint",
    "objectsto_access_key": "access_key",
    "objectsto_secret_key": "secret_key",
    "objectsto_bucket_name": "bucket_name",
    "objectsto_region": "region",
    "objectsto_public_endpoint": "public_endpoint",
}


def get_storage_config():
    """从数据库读取通用存储配置

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
        from mall.db.engines.mysql import get_session
        from mall.db.models.SystemConfig.model import SystemConfig

        session = get_session()
        with session.begin():
            configs = session.query(SystemConfig).filter(
                SystemConfig.config_key.in_(_STORAGE_KEYS)
            ).all()

        db_config = {c.config_key: c.config_value for c in configs}
    except Exception as e:
        LOG.warning("从数据库加载存储配置失败: {}".format(e))
        db_config = {}

    result = {}
    for db_key, internal_key in _KEY_FIELD_MAP.items():
        result[internal_key] = db_config.get(db_key, "")

    return result
