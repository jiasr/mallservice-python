from datetime import datetime, date

from sqlalchemy.ext.declarative import declarative_base

from oslo_db.sqlalchemy import models


BASE = declarative_base()


def replace_regex(u_string):
    # .isspace() 是否只包含空格
    if u_string.isspace():
        u_string = u_string.replace(" ", "| ")

    u_string = u_string.strip()
    u_string = u_string.replace("_", "|_")
    u_string = u_string.replace("%", "|%")
    return u_string


class DbBase(models.ModelBase):

    def to_dict(self):
        result = {}
        for c in self.__table__.columns:
            value = getattr(self, c.name)
            if isinstance(value, datetime):
                result[c.name] = value.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(value, date):
                result[c.name] = value.strftime('%Y-%m-%d')
            else:
                result[c.name] = value
        return result
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
