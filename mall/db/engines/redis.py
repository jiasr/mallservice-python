"""Redis 连接管理
提供 Redis 客户端单例，支持连接池复用。
"""
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

_client = None


def _get_redis_config():
    """获取 Redis 配置（当前使用默认值，后续可从配置文件读取）"""
    return {
        "host": "127.0.0.1",
        "port": 6379,
        "db": 0,
        "password": None,
        "decode_responses": True,
        "socket_timeout": 5,
        "socket_connect_timeout": 3,
    }


def get_client():
    """获取 Redis 客户端（单例，懒加载）"""
    global _client
    if _client is not None:
        return _client

    try:
        import redis as redis_mod

        cfg = _get_redis_config()
        _client = redis_mod.Redis(
            host=cfg["host"],
            port=cfg["port"],
            db=cfg["db"],
            password=cfg["password"],
            decode_responses=cfg["decode_responses"],
            socket_timeout=cfg["socket_timeout"],
            socket_connect_timeout=cfg["socket_connect_timeout"],
        )
        _client.ping()
        LOG.info("Redis 连接成功: {}:{}".format(cfg["host"], cfg["port"]))
    except ImportError:
        LOG.warning("redis 模块未安装，Redis 功能不可用")
        _client = None
    except Exception as e:
        LOG.warning("Redis 连接失败: {}".format(e))
        _client = None

    return _client


def reset_client():
    """重置 Redis 客户端（断开连接）"""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None
        LOG.info("Redis 连接已关闭")


def set(key, value, ex=None):
    """设置键值

    Args:
        key: 键
        value: 值
        ex: 过期时间（秒）

    Returns:
        bool: 是否成功
    """
    client = get_client()
    if client is None:
        return False
    try:
        return client.set(key, value, ex=ex)
    except Exception as e:
        LOG.error("Redis set 失败: {}".format(e))
        return False


def get(key):
    """获取键值

    Args:
        key: 键

    Returns:
        str or None: 值
    """
    client = get_client()
    if client is None:
        return None
    try:
        return client.get(key)
    except Exception as e:
        LOG.error("Redis get 失败: {}".format(e))
        return None


def delete(key):
    """删除键

    Args:
        key: 键

    Returns:
        bool: 是否成功
    """
    client = get_client()
    if client is None:
        return False
    try:
        return client.delete(key) > 0
    except Exception as e:
        LOG.error("Redis delete 失败: {}".format(e))
        return False


def exists(key):
    """检查键是否存在"""
    client = get_client()
    if client is None:
        return False
    try:
        return client.exists(key) > 0
    except Exception as e:
        LOG.error("Redis exists 失败: {}".format(e))
        return False


def expire(key, seconds):
    """设置过期时间"""
    client = get_client()
    if client is None:
        return False
    try:
        return client.expire(key, seconds)
    except Exception as e:
        LOG.error("Redis expire 失败: {}".format(e))
        return False
