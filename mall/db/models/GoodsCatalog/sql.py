# -*- encoding : utf-8 -*-
from mall.db.models.GoodsCatalog.model import GoodsCatalog
import uuid
from mall.db.engines.mysql import get_session
from mall.common.constant import SETTING_LIST_DEFAILT_PAGESIZE
from oslo_log import log as logging
from mall.common.common import build_tree
from mall.common.common import Fail


LOG = logging.getLogger(__name__)


class GoodsCatalogDao:

    @classmethod
    def goods_catalog_add(cls,data):
        session = get_session()
        with session.begin():
            level = 0
            if data.get("parentId") !="0":
                parent = session.query(GoodsCatalog).filter(GoodsCatalog.id == data.get("parentId")).first()
                if parent is  None:
                    raise Fail("父分类不存在")
                #开始添加
                level = parent.level +1
            instance = GoodsCatalog(
                id=uuid.uuid4().hex,
                name = data.get("name"),
                parentid=data.get("parentId"),
                sort_order=data.get("sort"),
                thumbnail=data.get("thumbnail"),
                level = level

            )
            session.add(instance)

        return instance.id

    @classmethod
    def goods_catalog_update(cls, data):
        session = get_session()
        with session.begin():
            catalog = session.query(GoodsCatalog).filter(GoodsCatalog.id == data.get("id")).first()
            if catalog is None:
                raise Fail("分类不存在")
            if data.get("name") is not None:
                catalog.name = data.get("name")
            if data.get("sortOrder") is not None:
                catalog.sort_order = data.get("sortOrder")
            if data.get("thumbnail") is not None:
                catalog.thumbnail = data.get("thumbnail")

        return {}

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

    @classmethod
    def goods_catalog_tree(cls, params):

        session = get_session()
        with session.begin():
            all_categories = session.query(GoodsCatalog).order_by(
                GoodsCatalog.sort_order.desc()
            ).all()

            return build_tree(all_categories, id_field="id", parent_field="parentid")

    @classmethod
    def goods_catalog_delete(cls, data):
        id = data.get("id", None)
        session = get_session()
        result = {}
        with session.begin():

            if data.get("id") is not None:
                childlist = session.query(GoodsCatalog).filter(GoodsCatalog.parentid == id).all()
                if len(childlist)>0:
                    result["status"] = "先删除子分类"
                else:
                    session.query(GoodsCatalog).filter(GoodsCatalog.id == id).delete()
                    result["status"] = "ok"
            else:
                result["status"]="未找到相关id"
        return result

    @classmethod
    def goods_catalog_update_sort(cls, data):
        """批量更新分类排序：接收 [{id:..., sortOrder:...}, ...]"""
        items = data.get("items", [])
        session = get_session()
        with session.begin():
            for item in items:
                catalog = session.query(GoodsCatalog).filter(
                    GoodsCatalog.id == item.get("id")
                ).first()
                if catalog:
                    catalog.sort_order = item.get("sortOrder", 0)
        return {}

    @classmethod
    def goods_catalog_batch_delete(cls, data):
        """批量删除分类：接收 {ids: [...]}，有子分类的跳过"""
        ids = data.get("ids", [])
        session = get_session()
        with session.begin():
            deleted = []
            skipped = []
            for id in ids:
                # 检查是否有子分类
                children = session.query(GoodsCatalog).filter(
                    GoodsCatalog.parentid == id
                ).count()
                if children > 0:
                    skipped.append(id)
                else:
                    session.query(GoodsCatalog).filter(GoodsCatalog.id == id).delete()
                    deleted.append(id)
        return {"deleted": deleted, "skipped": skipped}