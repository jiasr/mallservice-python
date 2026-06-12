from oslo_config import cfg
from oslo_log import log as logging


def register_opts(conf):
    logging.register_options(conf)
