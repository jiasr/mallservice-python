from mall.common.common import deco_catch_view_exception
from mall.db.models.GoodsCatalog.sql import GoodsCatalogDao
from oslo_log import log as logging


@deco_catch_view_exception("分类添加")
def goodscatalog_add(data):
    cata = GoodsCatalogDao.goods_catalog_add(data)
    return cata

@deco_catch_view_exception("分类修改")
def goodscatalog_update(data):
    cata = GoodsCatalogDao.goods_catalog_update(data)
    return cata

@deco_catch_view_exception("分类列表")
def goodscatalog_list(params):

    count,users = GoodsCatalogDao.goods_catalog_list(params)
    result = {}
    result["total"] =count
    result["data"] =[row.to_dict() for row in users]

    # thumbnail 相对路径动态拼接完整URL（已完整URL原样返回）
    from mall.db.engines.s3 import get_image_display_url
    for item in result["data"]:
        if item.get("thumbnail"):
            item["thumbnail"] = get_image_display_url(item["thumbnail"])

    return result

@deco_catch_view_exception("分类树")
def goodscatalog_tree(params):
    return  GoodsCatalogDao.goods_catalog_tree(params)

@deco_catch_view_exception("分类树")
def goodscatalog_delete(params):
    return  GoodsCatalogDao.goods_catalog_delete(params)

@deco_catch_view_exception("分类排序")
def goodscatalog_update_sort(data):
    return GoodsCatalogDao.goods_catalog_update_sort(data)

@deco_catch_view_exception("批量删除分类")
def goodscatalog_batch_delete(data):
    return GoodsCatalogDao.goods_catalog_batch_delete(data)
