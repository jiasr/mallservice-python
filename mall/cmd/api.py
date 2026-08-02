import os
from oslo_log import log as logging
from mall import app
from mall.conf import CONF
from mall.db.init_db import init_all


LOG = logging.getLogger(__name__)
CONF_FILE_PATH = os.path.join('../../etc/mall', "mall.conf")

logging.setup(CONF, "mall")


def load_config():
    print(CONF_FILE_PATH)
    CONF(['--config-file', CONF_FILE_PATH], project="mall")
    CONF.log_opt_values(LOG, logging.INFO)
    LOG.info(app.url_map)




def main():
    load_config()

    # 自动初始化数据库（建表 + 种子数据）
    #init_all()




    app.run(host=CONF.api_mall_listen, port=CONF.api_mall_listen_port, threaded=True)


if __name__ == "__main__":
    main()
