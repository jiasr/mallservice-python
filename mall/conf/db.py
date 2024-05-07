from oslo_config import cfg
from oslo_db import options

db_driver_opt = cfg.StrOpt('db_driver',
                           default='venus.db',
                           help='Driver to use for database access')


def register_opts(conf):
    options.set_defaults(conf, connection='sqlite:///$state_path/venus.sqlite')
    conf.register_opt(db_driver_opt)
