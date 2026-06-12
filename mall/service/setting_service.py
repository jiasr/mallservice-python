"""系统配置服务 - 仅处理 SystemConfig（通用键值对配置）"""
from mall.db.engines.mysql import get_session
from mall.db.models.SystemConfig.model import SystemConfig
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def get_all_settings():
    """获取所有系统配置"""
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
    """保存系统配置"""
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
    if key in ("site_name", "logo", "service_phone", "service_email"):
        return "general"
    elif key in ("allow_register", "register_need_audit", "enable_distribution"):
        return "access"
    return "general"
