"""系统设置服务"""
import json

from mall.db.engines.mysql import get_session
from mall.db.models.SystemConfig.model import SystemConfig
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def get_all_settings():
    """获取所有系统配置，以字典形式返回"""
    session = get_session()
    try:
        with session.begin():
            configs = session.query(SystemConfig).all()
            result = {}
            for c in configs:
                # 尝试解析 JSON 值，如 "true"/"false" 转为布尔
                val = c.config_value
                if val.lower() in ("true", "false"):
                    val = val.lower() == "true"
                elif val.isdigit():
                    val = int(val)
                result[c.config_key] = val
            return result
    except Exception as e:
        LOG.error("获取系统配置失败: {}".format(e))
        # 如果表不存在（首次运行），返回空字典
        return {}


def save_settings(settings_dict):
    """保存系统配置

    Args:
        settings_dict: 配置键值对字典，如 {"site_name": "商城", "objectsto_endpoint": "oss-cn-hangzhou.aliyuncs.com"}
    """
    session = get_session()
    try:
        with session.begin():
            for key, value in settings_dict.items():
                # 将非字符串值转为字符串存储
                if isinstance(value, bool):
                    str_value = "true" if value else "false"
                elif isinstance(value, (int, float)):
                    str_value = str(value)
                else:
                    str_value = value if value else ""

                # 查找已存在的配置
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

        # 如果修改了对象存储相关配置，重置 S3 client 单例
        if any(k.startswith("objectsto_") for k in settings_dict):
            from mall.common.storage.base import reset_client
            reset_client()

        LOG.info("系统配置保存成功，共 {} 项".format(len(settings_dict)))
        return True
    except Exception as e:
        LOG.error("保存系统配置失败: {}".format(e))
        return False


def _guess_group(key):
    """根据配置键名猜测分组"""
    if key.startswith("objectsto_"):
        return "storage"
    elif key.startswith("upload_"):
        return "upload"
    elif key in ("site_name", "logo", "service_phone", "service_email"):
        return "general"
    elif key in ("allow_register", "register_need_audit", "enable_distribution"):
        return "access"
    return "general"
