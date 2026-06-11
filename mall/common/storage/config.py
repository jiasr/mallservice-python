"""存储配置读取模块

从数据库 SystemConfig 表读取通用 S3 兼容存储配置，
不再区分具体厂商类型。
"""
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

# 通用存储配置 key（与数据库 config_key 一一对应）
_STORAGE_KEYS = [
    "storage_endpoint",       # S3 兼容端点（如 127.0.0.1:9000 / cos.ap-guangzhou.myqcloud.com）
    "storage_access_key",     # AccessKey
    "storage_secret_key",     # SecretKey
    "storage_bucket_name",    # Bucket 名称
    "storage_region",         # 地域（可选，默认 us-east-1）
    "storage_public_endpoint",# 公网访问地址（CDN/自定义域名）
]

# 配置 key -> 内部字段名映射
_KEY_FIELD_MAP = {
    "storage_endpoint": "endpoint",
    "storage_access_key": "access_key",
    "storage_secret_key": "secret_key",
    "storage_bucket_name": "bucket_name",
    "storage_region": "region",
    "storage_public_endpoint": "public_endpoint",
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
