# -*- encoding : utf-8 -*-
from mall.db.models.GoodsCatalog.model import GoodsCatalog
import uuid
from mall.db.engines.mysql import get_session
from mall.common.constant import SETTING_LIST_DEFAILT_PAGESIZE

class GoodsCatalogDao:

    @classmethod
    def goods_catalog_add(cls):
        session = get_session()
        with session.begin():
            instance = GoodsCatalog(
                id=uuid.uuid4().hex,
                name = "tttttttt",
            )
            session.add(instance)

        return instance.id


    @classmethod
    def goods_catalog_list(cls,params):
        page_num = params.get("currentPage", 1)
        page_size = params.get("pageSize", SETTING_LIST_DEFAILT_PAGESIZE)

        session = get_session()
        with session.begin():
            query = session.query(GoodsCatalog)
            count = query.count()

            page_size = int(page_size)
            page_num = int(page_num)
            start = (page_num - 1) * page_size
            query = query.limit(page_size).offset(start)
            result = query.all()

        return count, result
