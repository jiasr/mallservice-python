import os
from oslo_log import log as logging
from mall import  app
from mall.conf import CONF


LOG = logging.getLogger(__name__)
CONF_FILE_PATH = os.path.join('../../resource/conf', "mall.conf")

logging.setup(CONF,"mall")

def load_config():
    print(CONF_FILE_PATH)
    CONF(['--config-file', CONF_FILE_PATH], project="mall")
    CONF.log_opt_values(LOG, logging.INFO)
    LOG.info(app.url_map)

def main():
    load_config()
    app.run(host=CONF.api_mall_listen, port=CONF.api_mall_listen_port, threaded=True)



if __name__ == "__main__":
    main()