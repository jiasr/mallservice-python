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
