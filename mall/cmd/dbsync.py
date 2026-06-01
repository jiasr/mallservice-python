import os
from oslo_config import cfg
import  json
from sqlalchemy import create_engine
from mall.db.models.base import BASE
from oslo_log import log as logging
from mall.db.engines.mysql import get_session
import uuid

LOG = logging.getLogger(__name__)
CONF_FILE_PATH = os.path.join('../../etc/mall', "mall.conf")
CONF = cfg.CONF

def load_config():
    print(CONF_FILE_PATH)
    CONF(['--config-file', CONF_FILE_PATH], project="mall")
    CONF.log_opt_values(LOG, logging.INFO)



def table_sync():
    from mall.db.engines.mysql import get_engine
    from mall.db.models.base import BASE
    from mall.db.models.User.model import User,UserAddress
    from mall.db.models.GoodsCatalog.model import GoodsCatalog

    tables = [
        BASE.metadata.tables["t_mall_user"],
        BASE.metadata.tables["t_mall_user_address"],
        BASE.metadata.tables["t_mall_goodscatalog"]
    ]
    BASE.metadata.create_all(get_engine(), tables=tables, checkfirst=True)

def init_area():

    data = {}
    with open("./area.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
        session = get_session()
        result = session.execute("SELECT * FROM regions limit 1")
        print(result)
        if result.rowcount == 0:
            sql = "insert into regions(id,code, name, parent_code, level) VALUES('{}', '{}', '{}','{}',{}) "
            for provinces in data:
                plabel = provinces.get("label")
                pvalue = provinces.get("value")
                citys=provinces.get("children")
                psql=sql.format(uuid.uuid4().hex,pvalue,plabel,'',1)
                print(psql)
                session.execute(psql)
                for city in citys:
                    clabel = city.get("label")
                    cvalue = city.get("value")
                    districts = city.get("children")
                    csql =sql.format(uuid.uuid4().hex, cvalue, clabel, pvalue, 2)
                    print(csql)
                    session.execute(csql)
                    for district in districts:
                        dlabel = district.get("label")
                        dvalue = district.get("value")
                        dsql = sql.format(uuid.uuid4().hex,dvalue , dlabel, cvalue, 3)
                        print(dsql)
                        session.execute(dsql)
        else:
            LOG.info("area has been inited")







def main():
    load_config()
    table_sync()
    init_area()



if __name__ == "__main__":
    main()