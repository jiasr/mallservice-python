import os
from oslo_config import cfg
import logging
from sqlalchemy import create_engine
from mall.db.models.base import BASE


LOG = logging.getLogger(__name__)
CONF_FILE_PATH = os.path.join('../../resource/conf', "mall.conf")
CONF = cfg.CONF

def load_config():
    print(CONF_FILE_PATH)
    CONF(['--config-file', CONF_FILE_PATH], project="mall")
    CONF.log_opt_values(LOG, logging.INFO)



def table_sync():
    from mall.db.engines.mysql import get_engine
    from mall.db.models.base import BASE
    from mall.db.models.User.model import User

    tables = [
        BASE.metadata.tables["t_mall_user"],
        # BASE.metadata.tables["t_mo_dict_series"]
    ]
    BASE.metadata.create_all(get_engine(), tables=tables, checkfirst=True)


def main():
    load_config()
    table_sync()



if __name__ == "__main__":
    main()