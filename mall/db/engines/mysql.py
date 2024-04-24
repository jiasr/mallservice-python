import threading
from oslo_config import cfg

from oslo_db.sqlalchemy import session as db_session
from oslo_db import options
from oslo_log import log as logging

from sqlalchemy.ext.declarative import declarative_base

LOG = logging.getLogger(__name__)

CONF = cfg.CONF

options.set_defaults(CONF, connection=r"sqlite:///test.db")

_LOCK = threading.Lock()
_FACADE = None

BASE = declarative_base()

def _create_facade_lazily():
    global _LOCK
    with _LOCK:
        global _FACADE
        if _FACADE is None:
            _FACADE = db_session.EngineFacade(
                CONF.database.connection,
                **dict(CONF.database)
            )
        return _FACADE


def get_engine():
    facade = _create_facade_lazily()
    return facade.get_engine()




def get_session(**kwargs):
    facade = _create_facade_lazily()
    return facade.get_session(**kwargs)

