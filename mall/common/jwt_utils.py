"""JWT 令牌工具"""
import time
import jwt
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

# JWT 密钥（生产环境应从配置文件读取）
JWT_SECRET = "mall_admin_jwt_secret_key_2024"
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def create_token(admin_id, username):
    """生成 JWT token

    Args:
        admin_id: 管理员用户ID
        username: 用户名

    Returns:
        str: JWT token 字符串
    """
    now = int(time.time())
    payload = {
        "admin_id": admin_id,
        "username": username,
        "iat": now,
        "exp": now + TOKEN_EXPIRE_HOURS * 3600,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def verify_token(token):
    """验证 JWT token

    Args:
        token: JWT token 字符串

    Returns:
        dict or None: 解析后的 payload，验证失败返回 None
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        LOG.warning("Token 已过期")
        return None
    except jwt.InvalidTokenError as e:
        LOG.warning("Token 无效: {}".format(e))
        return None
