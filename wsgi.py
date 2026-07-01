import os
from oslo_log import log as logging
from mall import app
from mall.conf import CONF

LOG = logging.getLogger(__name__)
CONF_FILE_PATH = os.path.join(os.path.dirname(__file__), 'etc', 'mall', 'mall.conf')


def init_config():
    if os.path.exists(CONF_FILE_PATH):
        CONF(['--config-file', CONF_FILE_PATH], project="mall")
    else:
        CONF([], project="mall")


init_config()

# gunicorn 直接引用的 Flask app 实例
application = app
