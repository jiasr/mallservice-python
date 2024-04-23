# -*- encoding : utf-8 -*-
from mall.db.models.User.model import User
import uuid
from mall.db.engines.mysql import get_session


class UserDao:

    @classmethod
    def useradd(cls):
        session = get_session()
        with session.begin():
            instance = User(
                id=uuid.uuid4().hex,
                name = "tttttttt",
            )
            session.add(instance)

        return instance.id


    @classmethod
    def listalluser(cls,params):
        page_num = params.get("page", 1)
        page_size = params.get("pageSize", 10)

        session = get_session()
        with session.begin():
            query = session.query(User)
            count = query.count()
            page_size = int(page_size)
            page_num = int(page_num)

            start = (page_num - 1) * page_size
            query = query.limit(page_size).offset(start)
            result = query.all()

        return count, result
