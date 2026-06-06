from mall.common.common import deco_catch_view_exception
from mall.db.models.GoodsCatalog.sql import GoodsCatalogDao
from oslo_log import log as logging


@deco_catch_view_exception("分类添加")
def goodscatalog_add(params):

    result_list = []
    cata = GoodsCatalogDao.goods_catalog_add()

    return cata

@deco_catch_view_exception("分类列表")
def goodscatalog_list(params):

    count,users = GoodsCatalogDao.goods_catalog_list(params)
    result = {}
    result["total"] =count
    result["data"] =[row.to_dict() for row in users]

    return result

@deco_catch_view_exception("分类树")
def goodscatalog_tree(params):

    return  GoodsCatalogDao.goods_catalog_tree(params)
