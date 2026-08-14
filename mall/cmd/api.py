import os
from oslo_log import log as logging
from mall import app
from mall.conf import CONF

LOG = logging.getLogger(__name__)
# 用 __file__ 绝对定位配置文件，保证在 Docker 等任意工作目录下都能找到
CONF_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'etc', 'mall', 'mall.conf'
)

_configured = False


def load_config():
    """加载配置文件（幂等，模块导入和 main 都可安全调用）"""
    global _configured
    if _configured:
        return
    if os.path.exists(CONF_FILE_PATH):
        CONF(['--config-file', CONF_FILE_PATH], project="mall")
    else:
        CONF([], project="mall")
    _configured = True


def setup_logging():
    """初始化 oslo_log 日志（仅开发服务器 main() 需要，gunicorn 场景无需）"""
    log_dir = getattr(CONF, 'log_dir', '') or ''
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            pass
    logging.setup(CONF, "mall")


# 模块顶层加载配置：gunicorn 走 mall.cmd.api:app 时配置即已就绪（不触发日志文件）
load_config()


def main():
    # 配置已在模块顶层加载，此处补初始化日志并启动开发服务器
    setup_logging()
    app.run(host=CONF.api_mall_listen, port=CONF.api_mall_listen_port, threaded=True)


# gunicorn 直接引用的 WSGI 应用实例（mall.cmd.api:app / :application 均可）
application = app


if __name__ == "__main__":
    main()
