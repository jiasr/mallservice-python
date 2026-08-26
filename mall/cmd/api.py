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
    # mall/__init__.py 的 _bootstrap_config 已在 import 时加载过配置，避免重复加载
    try:
        if CONF.database.connection:
            _configured = True
            return
    except Exception:
        pass
    if os.path.exists(CONF_FILE_PATH):
        CONF(['--config-file', CONF_FILE_PATH], project="mall")
    else:
        CONF([], project="mall")
    _configured = True


def _fallback_stderr_logging():
    """oslo_log 初始化失败时的降级方案：INFO 级日志输出到 stderr"""
    import logging as std_logging
    root = std_logging.getLogger()
    root.setLevel(std_logging.DEBUG)
    for h in root.handlers:
        if isinstance(h, std_logging.StreamHandler):
            return
    h = std_logging.StreamHandler()
    h.setFormatter(std_logging.Formatter(
        '%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s',
        '%Y-%m-%d %H:%M:%S'))
    root.addHandler(h)


def setup_logging():
    """初始化 oslo_log 日志（幂等；日志文件不可用时降级为 stderr 输出）"""
    log_dir = getattr(CONF, 'log_dir', '') or ''
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            pass
    try:
        logging.setup(CONF, "mall")
    except Exception as e:
        # 日志文件不可用（如 Windows 下 log_dir 路径非法/无权限）时降级，
        # 保证 INFO 级别日志至少输出到 stderr，不阻塞服务启动
        print("WARNING: oslo_log setup 失败({}), 降级为 stderr 输出".format(e), file=sys.stderr)
        _fallback_stderr_logging()


# 模块顶层加载配置：gunicorn 走 mall.cmd.api:app 时配置即已就绪（不触发日志文件）
load_config()
# 初始化 oslo_log：gunicorn 场景 main() 不执行，必须在模块顶层初始化，
# 否则应用内 LOG.info 等日志全部丢失（root logger 默认 WARNING 级别）
setup_logging()


def main():
    # 配置与日志已在模块顶层就绪，此处直接启动开发服务器
    app.run(host=CONF.api_mall_listen, port=CONF.api_mall_listen_port, threaded=True)


# gunicorn 直接引用的 WSGI 应用实例（mall.cmd.api:app / :application 均可）
application = app


if __name__ == "__main__":
    main()
