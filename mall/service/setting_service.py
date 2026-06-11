"""系统设置服务"""
import json

from mall.db.engines.mysql import get_session
from mall.db.models.SystemConfig.model import SystemConfig
from mall.db.models.StorageConfig.model import StorageConfig
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


# ==================== 通用系统配置 ====================

def get_all_settings():
    """获取所有系统配置，以字典形式返回"""
    session = get_session()
    try:
        with session.begin():
            configs = session.query(SystemConfig).all()
            result = {}
            for c in configs:
                val = c.config_value
                if val.lower() in ("true", "false"):
                    val = val.lower() == "true"
                elif val.isdigit():
                    val = int(val)
                result[c.config_key] = val
            return result
    except Exception as e:
        LOG.error("获取系统配置失败: {}".format(e))
        return {}


def save_settings(settings_dict):
    """保存系统配置

    Args:
        settings_dict: 配置键值对字典
    """
    session = get_session()
    try:
        with session.begin():
            for key, value in settings_dict.items():
                if isinstance(value, bool):
                    str_value = "true" if value else "false"
                elif isinstance(value, (int, float)):
                    str_value = str(value)
                else:
                    str_value = value if value else ""

                existing = session.query(SystemConfig).filter(
                    SystemConfig.config_key == key
                ).first()

                if existing:
                    existing.config_value = str_value
                else:
                    new_config = SystemConfig(
                        config_key=key,
                        config_value=str_value,
                        description="",
                        config_group=_guess_group(key),
                    )
                    session.add(new_config)

        LOG.info("系统配置保存成功，共 {} 项".format(len(settings_dict)))
        return True
    except Exception as e:
        LOG.error("保存系统配置失败: {}".format(e))
        return False


def _guess_group(key):
    """根据配置键名猜测分组"""
    if key.startswith("upload_"):
        return "upload"
    elif key in ("site_name", "logo", "service_phone", "service_email"):
        return "general"
    elif key in ("allow_register", "register_need_audit", "enable_distribution"):
        return "access"
    return "general"


# ==================== 对象存储配置（独立表） ====================

def get_storage_settings():
    """获取对象存储配置"""
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
                    "upload_max_size": config.upload_max_size or 10,
                    "upload_allowed_types": config.upload_allowed_types or "",
                }
            return {}
    except Exception as e:
        LOG.error("获取存储配置失败: {}".format(e))
        return {}


def save_storage_settings(data):
    """保存对象存储配置

    Args:
        data: dict 包含 endpoint/access_key/secret_key/bucket_name/region/public_endpoint/upload_max_size/upload_allowed_types
    """
    session = get_session()
    try:
        with session.begin():
            config = session.query(StorageConfig).first()
            if not config:
                config = StorageConfig()
                session.add(config)

            for field in ("endpoint", "access_key", "secret_key", "bucket_name",
                          "region", "public_endpoint", "upload_max_size", "upload_allowed_types"):
                if field in data:
                    setattr(config, field, data[field])

        # 重置 S3 client 单例
        from mall.common.storage.base import reset_client
        reset_client()

        LOG.info("存储配置保存成功")
        return True
    except Exception as e:
        LOG.error("保存存储配置失败: {}".format(e))
        return False
