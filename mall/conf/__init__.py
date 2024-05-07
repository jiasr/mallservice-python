from oslo_config import cfg
from mall.conf import api
from mall.conf import common
from mall.conf import core
from mall.conf import db

CONF = cfg.CONF

common.register_opts(CONF)
api.register_opts(CONF)
core.register_opts(CONF)
db.register_opts(CONF)

