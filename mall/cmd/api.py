from mall import  app
import os
from oslo_config import cfg
import logging

LOG = logging.getLogger(__name__)
CONF_FILE_PATH = os.path.join('../../resource/conf', "mall.conf")
CONF = cfg.CONF

def load_config():
    print(CONF_FILE_PATH)
    CONF(['--config-file', CONF_FILE_PATH], project="mall")
    CONF.log_opt_values(LOG, logging.INFO)


def main():
    LOG.info(app.url_map)
    load_config()
    app.run(host="0.0.0.0", port=8099, threaded=True)


if __name__ == "__main__":
    main()