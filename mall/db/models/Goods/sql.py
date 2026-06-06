"""商品数据访问层"""
import json
import uuid
import time
from datetime import datetime

from sqlalchemy import func, or_, and_
from mall.db.engines.mysql import get_session
from mall.db.models.Goods.model import (
    GoodsSpu, GoodsSku, GoodsSpec, GoodsCategory,
    GoodsComment, SearchHistory
)
from mall.common.constant import SETTING_LIST_DEFAILT_PAGESIZE
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class GoodsSpuDao:
    """商品SPU数据访问"""

    @classmethod
    def get_by_spu_id(cls, spu_id):
        """根据spuId获取商品详情"""
        session = get_session()
        with session.begin():
            spu = session.query(GoodsSpu).filter(
                GoodsSpu.spu_id == str(spu_id)
            ).first()
            if not spu:
                return None
            return cls._format_spu_detail(session, spu)

    @classmethod
    def search_list(cls, params):
        """搜索商品列表（分页+排序+筛选）"""
        session = get_session()
        page_num = int(params.get("pageNum", 1))
        page_size = int(params.get("pageSize", SETTING_LIST_DEFAILT_PAGESIZE))
        keyword = params.get("keyword", "")
        sort_type = int(params.get("sort", 0))  # 0综合 1价格
        sort_direction = params.get("sortType", "0")  # 0升序 1降序
        min_price = params.get("minPrice")
        max_price = params.get("maxPrice")
        category_id = params.get("categoryId")

        with session.begin():
            query = session.query(GoodsSpu).filter(
                GoodsSpu.is_put_on_sale == 1,
                GoodsSpu.is_available == 1,
            )

            # 关键词搜索
            if keyword:
                query = query.filter(
                    or_(
                        GoodsSpu.title.like(f'%{keyword}%'),
                        GoodsSpu.etitle.like(f'%{keyword}%'),
                    )
                )

            # 分类筛选
            if category_id:
                query = query.filter(GoodsSpu.category_id == int(category_id))

            # 价格区间筛选
            if min_price is not None:
                query = query.filter(GoodsSpu.min_sale_price >= int(min_price))
            if max_price is not None and max_price != 'undefined':
                query = query.filter(GoodsSpu.max_sale_price <= int(max_price))

            # 排序
            if sort_type == 1:  # 价格排序
                if sort_direction == '0':  # 升序
                    query = query.order_by(GoodsSpu.min_sale_price.asc())
                else:  # 降序
                    query = query.order_by(GoodsSpu.min_sale_price.desc())
            else:  # 综合排序（默认按创建时间倒序）
                query = query.order_by(GoodsSpu.create_time.desc())

            total_count = query.count()

            start = (page_num - 1) * page_size
            spus = query.limit(page_size).offset(start).all()

            spu_list = []
            for spu in spus:
                tags = json.loads(spu.tags) if spu.tags else []
                spu_list.append({
                    "spuId": spu.spu_id,
                    "thumb": spu.primary_image,
                    "title": spu.title,
                    "price": spu.min_sale_price,
                    "originPrice": spu.max_line_price,
                    "tags": [t.get("title", t) if isinstance(t, dict) else t for t in tags],
                    "desc": "",
                })

            return {
                "saasId": None,
                "storeId": None,
                "pageNum": page_num,
                "pageSize": page_size,
                "totalCount": total_count,
                "spuList": spu_list,
                "algId": 0,
            }

    @classmethod
    def get_simple_list(cls, page_index=1, page_size=20):
        """获取简单商品列表"""
        session = get_session()
        with session.begin():
            start = (page_index - 1) * page_size
            spus = session.query(GoodsSpu).filter(
                GoodsSpu.is_put_on_sale == 1,
                GoodsSpu.is_available == 1,
            ).order_by(GoodsSpu.create_time.desc()).limit(page_size).offset(start).all()

            result = []
            for spu in spus:
                tags = json.loads(spu.tags) if spu.tags else []
                result.append({
                    "spuId": spu.spu_id,
                    "thumb": spu.primary_image,
                    "title": spu.title,
                    "price": spu.min_sale_price,
                    "originPrice": spu.max_line_price,
                    "tags": [t.get("title", t) if isinstance(t, dict) else t for t in tags],
                })
            return result

    @classmethod
    def _format_spu_detail(cls, session, spu):
        """格式化SPU详情数据，匹配前端数据结构"""
        # 处理规格
        spec_list = []
        for spec in spu.specs.all():
            spec_values = json.loads(spec.spec_values) if spec.spec_values else []
            spec_list.append({
                "specId": spec.spec_id,
                "title": spec.title,
                "specValueList": spec_values,
            })

        # 处理SKU
        sku_list = []
        for sku in spu.skus.all():
            spec_info = json.loads(sku.spec_info) if sku.spec_info else []
            sku_list.append({
                "skuId": sku.sku_id,
                "skuImage": sku.sku_image,
                "specInfo": spec_info,
                "priceInfo": [
                    {"priceType": 1, "price": str(sku.price), "priceTypeName": "销售价格"},
                    {"priceType": 2, "price": str(sku.line_price), "priceTypeName": "划线价格"},
                ],
                "stockInfo": {
                    "stockQuantity": sku.stock_quantity,
                    "safeStockQuantity": 0,
                    "soldQuantity": sku.sold_quantity or 0,
                },
                "weight": {"value": sku.weight_value, "unit": sku.weight_unit},
                "volume": None,
                "profitPrice": None,
            })

        # 处理标签
        tags = json.loads(spu.tags) if spu.tags else []
        spu_tag_list = []
        for tag in tags:
            if isinstance(tag, dict):
                spu_tag_list.append(tag)
            else:
                spu_tag_list.append({"id": None, "title": tag, "image": None})

        # 处理限购信息
        limit_info = json.loads(spu.limit_info) if spu.limit_info else None

        # 处理图片列表
        images = json.loads(spu.images) if spu.images else []
        desc_images = json.loads(spu.desc) if spu.desc else []

        return {
            "saasId": "88888888",
            "storeId": spu.store_id or "1000",
            "spuId": spu.spu_id,
            "title": spu.title,
            "primaryImage": spu.primary_image,
            "images": images,
            "video": spu.video,
            "available": spu.is_available,
            "minSalePrice": spu.min_sale_price,
            "minLinePrice": spu.min_line_price,
            "maxSalePrice": spu.max_sale_price,
            "maxLinePrice": spu.max_line_price,
            "spuStockQuantity": spu.stock_quantity,
            "soldNum": spu.sold_num,
            "isPutOnSale": spu.is_put_on_sale,
            "categoryIds": [],
            "specList": spec_list,
            "skuList": sku_list,
            "spuTagList": spu_tag_list,
            "limitInfo": limit_info,
            "desc": desc_images,
            "etitle": spu.etitle or "",
            "isSoldOut": spu.is_sold_out or False,
            "isAvailable": spu.is_available,
            "promotionList": None,
            "minProfitPrice": None,
            "groupIdList": [],
        }


class GoodsCategoryDao:
    """商品分类数据访问"""

    @classmethod
    def get_category_tree(cls):
        """获取三级分类树"""
        session = get_session()
        with session.begin():
            all_categories = session.query(GoodsCategory).order_by(
                GoodsCategory.sort_order.asc()
            ).all()

            # 构建树形结构
            category_map = {}
            for cat in all_categories:
                category_map[cat.id] = {
                    "groupId": str(cat.id),
                    "name": cat.name,
                    "thumbnail": cat.thumbnail or "",
                    "children": [],
                }

            roots = []
            for cat in all_categories:
                if cat.parent_id and cat.parent_id in category_map:
                    category_map[cat.parent_id]["children"].append(category_map[cat.id])
                elif not cat.parent_id or cat.parent_id == 0:
                    roots.append(category_map[cat.id])

            return roots

    @classmethod
    def seed_default_categories(cls):
        """初始化默认分类数据"""
        session = get_session()
        with session.begin():
            existing = session.query(GoodsCategory).count()
            if existing > 0:
                return

            categories_data = [
                # 一级分类
                {"id": 1, "name": "女装", "parent_id": 0, "level": 1,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/miniapp/category/category-default.png"},
                {"id": 2, "name": "男装", "parent_id": 0, "level": 1,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/miniapp/category/category-default.png"},
                {"id": 3, "name": "数码家电", "parent_id": 0, "level": 1,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/miniapp/category/category-default.png"},
                # 二级分类
                {"id": 11, "name": "女装", "parent_id": 1, "level": 2,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/miniapp/category/category-default.png"},
                {"id": 21, "name": "男装", "parent_id": 2, "level": 2,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/miniapp/category/category-default.png"},
                {"id": 31, "name": "数码产品", "parent_id": 3, "level": 2,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/miniapp/category/category-default.png"},
                # 三级分类
                {"id": 101, "name": "连衣裙", "parent_id": 11, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-9.png"},
                {"id": 102, "name": "T恤", "parent_id": 11, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-1.png"},
                {"id": 103, "name": "卫衣", "parent_id": 11, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-1.png"},
                {"id": 104, "name": "毛衣", "parent_id": 11, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-5.png"},
                {"id": 105, "name": "西装", "parent_id": 11, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-7.png"},
                {"id": 106, "name": "裤子", "parent_id": 11, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-11.png"},
                {"id": 107, "name": "半身裙", "parent_id": 11, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-10.png"},
                {"id": 108, "name": "羽绒服", "parent_id": 11, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-4.png"},
                {"id": 201, "name": "T恤", "parent_id": 21, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-1.png"},
                {"id": 202, "name": "卫衣", "parent_id": 21, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-1.png"},
                {"id": 203, "name": "裤子", "parent_id": 21, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-11.png"},
                {"id": 301, "name": "智能设备", "parent_id": 31, "level": 3,
                 "thumbnail": "https://cdn-we-retail.ym.tencent.com/tsr/classify/img-1.png"},
            ]

            for cat_data in categories_data:
                cat = GoodsCategory(**cat_data)
                session.add(cat)


class GoodsCommentDao:
    """商品评价数据访问"""

    @classmethod
    def get_comments_by_spu(cls, spu_id):
        """获取商品评价列表"""
        session = get_session()
        with session.begin():
            spu = session.query(GoodsSpu).filter(GoodsSpu.spu_id == str(spu_id)).first()
            if not spu:
                return []

            comments = session.query(GoodsComment).filter(
                GoodsComment.spu_id == spu.id
            ).order_by(GoodsComment.create_time.desc()).all()

            result = []
            for c in comments:
                images = json.loads(c.images) if c.images else []
                videos = json.loads(c.videos) if c.videos else []
                spec_info = json.loads(c.spec_info) if c.spec_info else None
                result.append({
                    "spuId": spu.spu_id,
                    "skuId": c.sku_id,
                    "specInfo": spec_info,
                    "commentContent": c.content,
                    "commentScore": c.score,
                    "uid": c.user_id,
                    "userName": c.user_name,
                    "userHeadUrl": c.user_head_url,
                    "images": images,
                    "videos": videos,
                    "createTime": c.create_time.strftime('%Y-%m-%d %H:%M:%S') if c.create_time else "",
                })

            return {"homePageComments": result}

    @classmethod
    def get_comments_count(cls, spu_id):
        """获取商品评价统计"""
        session = get_session()
        with session.begin():
            spu = session.query(GoodsSpu).filter(GoodsSpu.spu_id == str(spu_id)).first()
            if not spu:
                return {
                    "commentCount": "0", "badCount": "0", "middleCount": "0",
                    "goodCount": "0", "hasImageCount": "0", "goodRate": 0, "uidCount": "0",
                }

            base_query = session.query(GoodsComment).filter(GoodsComment.spu_id == spu.id)
            total = base_query.count()
            bad = base_query.filter(GoodsComment.score <= 2).count()
            middle = base_query.filter(GoodsComment.score == 3).count()
            good = base_query.filter(GoodsComment.score >= 4).count()
            has_image = base_query.filter(GoodsComment.images.isnot(None)).filter(
                GoodsComment.images != '[]').filter(GoodsComment.images != '').count()

            return {
                "commentCount": str(total),
                "badCount": str(bad),
                "middleCount": str(middle),
                "goodCount": str(good),
                "hasImageCount": str(has_image),
                "goodRate": round(good / total * 100, 1) if total > 0 else 100.0,
                "uidCount": str(total),
            }

    @classmethod
    def add_comment(cls, data):
        """添加商品评价"""
        session = get_session()
        with session.begin():
            spu = session.query(GoodsSpu).filter(
                GoodsSpu.spu_id == str(data.get("spuId"))
            ).first()
            if not spu:
                return False

            comment = GoodsComment(
                spu_id=spu.id,
                sku_id=data.get("skuId"),
                spec_info=json.dumps(data.get("specInfo")) if data.get("specInfo") else None,
                content=data.get("content", ""),
                score=data.get("score", 5),
                user_id=data.get("userId", ""),
                user_name=data.get("userName", ""),
                user_head_url=data.get("userHeadUrl", ""),
                images=json.dumps(data.get("images", [])),
                videos=json.dumps(data.get("videos", [])),
            )
            session.add(comment)
            return True


class SearchDao:
    """搜索数据访问"""

    @classmethod
    def get_history(cls, user_id=None):
        """获取搜索历史"""
        session = get_session()
        with session.begin():
            query = session.query(SearchHistory)
            if user_id:
                query = query.filter(SearchHistory.user_id == str(user_id))
            records = query.order_by(SearchHistory.create_time.desc()).limit(20).all()
            return {"historyWords": [r.keyword for r in records]}

    @classmethod
    def get_popular(cls):
        """获取热门搜索词（基于搜索频次统计）"""
        session = get_session()
        with session.begin():
            results = session.query(
                SearchHistory.keyword,
                func.count(SearchHistory.id).label('count')
            ).group_by(SearchHistory.keyword).order_by(
                func.count(SearchHistory.id).desc()
            ).limit(12).all()

            popular = [r.keyword for r in results]
            if not popular:
                popular = [
                    "连衣裙", "T恤", "iPhone12", "车载手机支架",
                    "华为", "针织半身裙", "卫衣", "羽绒服",
                    "小米", "电脑", "耳机", "毛衣",
                ]
            return {"popularWords": popular}

    @classmethod
    def add_history(cls, keyword, user_id=None):
        """添加搜索记录"""
        session = get_session()
        with session.begin():
            record = SearchHistory(
                user_id=user_id,
                keyword=keyword,
            )
            session.add(record)


def seed_default_goods():
    """初始化默认商品数据"""
    session = get_session()
    with session.begin():
        existing = session.query(GoodsSpu).count()
        if existing > 0:
            return

        goods_list = [
            {
                "spu_id": "0",
                "title": "白色短袖连衣裙荷叶边裙摆宽松韩版休闲纯白清爽优雅连衣裙",
                "primary_image": "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-09a.png",
                "images": json.dumps([
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-09a.png",
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-09b.png",
                ]),
                "category_id": 101,
                "min_sale_price": 29800, "max_sale_price": 29800,
                "min_line_price": 29800, "max_line_price": 40000,
                "stock_quantity": 510, "sold_num": 1020,
                "tags": json.dumps([{"id": "13001", "title": "限时抢购", "image": None}]),
                "limit_info": json.dumps([{"text": "限购5件"}]),
                "desc": json.dumps([
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-09c.png",
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-09d.png",
                ]),
                "store_id": "1000",
                "specs": [
                    {"spec_id": "10011", "title": "颜色", "values": [
                        {"specValueId": "10012", "specId": "10011", "saasId": "88888888", "specValue": "米色荷叶边", "image": None}
                    ]},
                    {"spec_id": "10013", "title": "尺码", "values": [
                        {"specValueId": "11014", "specId": "10013", "saasId": "88888888", "specValue": "S", "image": None},
                        {"specValueId": "10014", "specId": "10013", "saasId": "88888888", "specValue": "M", "image": None},
                        {"specValueId": "11013", "specId": "10013", "saasId": "88888888", "specValue": "L", "image": None},
                    ]},
                ],
                "skus": [
                    {"sku_id": "135676631", "sku_image": "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-09a.png",
                     "price": 29800, "line_price": 40000, "stock_quantity": 175,
                     "spec_info": [{"specId": "10011", "specTitle": None, "specValueId": "10012", "specValue": None},
                                   {"specId": "10013", "specTitle": None, "specValueId": "11014", "specValue": None}]},
                    {"sku_id": "135676632", "sku_image": "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-09a.png",
                     "price": 29800, "line_price": 40000, "stock_quantity": 158,
                     "spec_info": [{"specId": "10011", "specTitle": None, "specValueId": "10012", "specValue": None},
                                   {"specId": "10013", "specTitle": None, "specValueId": "11013", "specValue": None}]},
                    {"sku_id": "135681631", "sku_image": "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-09a.png",
                     "price": 29800, "line_price": 40000, "stock_quantity": 177,
                     "spec_info": [{"specId": "10011", "specTitle": None, "specValueId": "10012", "specValue": None},
                                   {"specId": "10013", "specTitle": None, "specValueId": "10014", "specValue": None}]},
                ],
            },
            {
                "spu_id": "135686633",
                "title": "纯色纯棉休闲圆领短袖T恤纯白亲肤厚柔软细腻面料纯白短袖套头T恤",
                "primary_image": "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-08b.png",
                "images": json.dumps([
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-08a.png",
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-08a1.png",
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-08b.png",
                ]),
                "category_id": 102,
                "min_sale_price": 25900, "max_sale_price": 26900,
                "min_line_price": 31900, "max_line_price": 31900,
                "stock_quantity": 371, "sold_num": 1032,
                "tags": json.dumps([{"id": None, "title": "2020夏季新款", "image": None}]),
                "desc": json.dumps([
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-08c.png",
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-08d.png",
                ]),
                "store_id": "1000",
                "specs": [
                    {"spec_id": "10000", "title": "颜色", "values": [
                        {"specValueId": "10001", "specId": "10000", "saasId": "88888888", "specValue": "白色", "image": ""}
                    ]},
                    {"spec_id": "10002", "title": "尺码", "values": [
                        {"specValueId": "11003", "specId": "10002", "saasId": "88888888", "specValue": "S", "image": ""},
                        {"specValueId": "10003", "specId": "10002", "saasId": "88888888", "specValue": "M", "image": ""},
                        {"specValueId": "11002", "specId": "10002", "saasId": "88888888", "specValue": "L", "image": ""},
                    ]},
                ],
                "skus": [
                    {"sku_id": "135686634", "sku_image": None, "price": 25900, "line_price": 31900, "stock_quantity": 0,
                     "spec_info": [{"specId": "10000", "specTitle": None, "specValueId": "10001", "specValue": "白色"},
                                   {"specId": "10002", "specTitle": None, "specValueId": "10003", "specValue": "M"}]},
                    {"sku_id": "135691631", "sku_image": None, "price": 26900, "line_price": 31900, "stock_quantity": 177,
                     "spec_info": [{"specId": "10000", "specTitle": None, "specValueId": "10001", "specValue": "白色"},
                                   {"specId": "10002", "specTitle": None, "specValueId": "11003", "specValue": "S"}]},
                    {"sku_id": "135691632", "sku_image": None, "price": 26900, "line_price": 31900, "stock_quantity": 194,
                     "spec_info": [{"specId": "10000", "specTitle": None, "specValueId": "10001", "specValue": "白色"},
                                   {"specId": "10002", "specTitle": None, "specValueId": "11002", "specValue": "L"}]},
                ],
            },
            {
                "spu_id": "135691628",
                "title": "运动连帽拉链卫衣休闲开衫长袖多色运动细绒面料运动上衣",
                "primary_image": "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-17a.png",
                "images": json.dumps([
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-17a.png",
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-17a1.png",
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-17b.png",
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-17b1.png",
                ]),
                "category_id": 103,
                "min_sale_price": 25900, "max_sale_price": 25900,
                "min_line_price": 39900, "max_line_price": 39900,
                "stock_quantity": 0, "sold_num": 1022, "is_sold_out": True,
                "tags": json.dumps([{"id": None, "title": "2020夏季新款", "image": None}]),
                "desc": json.dumps([
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-17c.png",
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/nz-17d.png",
                ]),
                "store_id": "1000",
                "specs": [
                    {"spec_id": "127904180600844800", "title": "颜色", "values": [
                        {"specValueId": "127904180768617216", "specId": "127904180600844800", "saasId": "88888888", "specValue": "军绿色", "image": ""}
                    ]},
                    {"spec_id": "127904861604820480", "title": "尺码", "values": [
                        {"specValueId": "127904862494014208", "specId": "127904861604820480", "saasId": "88888888", "specValue": "XS", "image": ""},
                        {"specValueId": "127904862175246592", "specId": "127904861604820480", "saasId": "88888888", "specValue": "S", "image": ""},
                        {"specValueId": "127904862007474176", "specId": "127904861604820480", "saasId": "88888888", "specValue": "M", "image": ""},
                        {"specValueId": "127904861755815680", "specId": "127904861604820480", "saasId": "88888888", "specValue": "L", "image": ""},
                    ]},
                ],
                "skus": [
                    {"sku_id": "135686631", "sku_image": None, "price": 25900, "line_price": 39900, "stock_quantity": 0,
                     "spec_info": [{"specId": "127904180600844800", "specTitle": None, "specValueId": "127904180768617216", "specValue": "军绿色"},
                                   {"specId": "127904861604820480", "specTitle": None, "specValueId": "127904862494014208", "specValue": "XS"}]},
                    {"sku_id": "135686632", "sku_image": None, "price": 25900, "line_price": 39900, "stock_quantity": 0,
                     "spec_info": [{"specId": "127904180600844800", "specTitle": None, "specValueId": "127904180768617216", "specValue": "军绿色"},
                                   {"specId": "127904861604820480", "specTitle": None, "specValueId": "127904862007474176", "specValue": "M"}]},
                    {"sku_id": "135691629", "sku_image": None, "price": 25900, "line_price": 39900, "stock_quantity": 0,
                     "spec_info": [{"specId": "127904180600844800", "specTitle": None, "specValueId": "127904180768617216", "specValue": "军绿色"},
                                   {"specId": "127904861604820480", "specTitle": None, "specValueId": "127904862175246592", "specValue": "S"}]},
                    {"sku_id": "135691630", "sku_image": None, "price": 25900, "line_price": 39900, "stock_quantity": 0,
                     "spec_info": [{"specId": "127904180600844800", "specTitle": None, "specValueId": "127904180768617216", "specValue": "军绿色"},
                                   {"specId": "127904861604820480", "specTitle": None, "specValueId": "127904861755815680", "specValue": "L"}]},
                ],
            },
            {
                "spu_id": "135686623",
                "title": "腾讯极光盒子4智能网络电视机顶盒6K千兆网络机顶盒4K高分辨率",
                "primary_image": "https://cdn-we-retail.ym.tencent.com/tsr/goods/dz-3a.png",
                "images": json.dumps([
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/dz-3a.png",
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/dz-3b.png",
                ]),
                "category_id": 301,
                "min_sale_price": 9900, "max_sale_price": 10900,
                "min_line_price": 16900, "max_line_price": 16900,
                "stock_quantity": 510, "sold_num": 850,
                "tags": json.dumps([{"id": None, "title": "联名系列", "image": None}]),
                "desc": json.dumps([
                    "https://cdn-we-retail.ym.tencent.com/tsr/goods/dz-3c.png",
                ]),
                "store_id": "1000",
                "specs": [
                    {"spec_id": "20000", "title": "颜色", "values": [
                        {"specValueId": "20001", "specId": "20000", "saasId": "88888888", "specValue": "黑色", "image": ""}
                    ]},
                ],
                "skus": [
                    {"sku_id": "135686624", "sku_image": None, "price": 9900, "line_price": 16900, "stock_quantity": 510,
                     "spec_info": [{"specId": "20000", "specTitle": None, "specValueId": "20001", "specValue": "黑色"}]},
                ],
            },
        ]

        for g in goods_list:
            specs_data = g.pop("specs")
            skus_data = g.pop("skus")

            spu = GoodsSpu(**g)
            session.add(spu)
            session.flush()  # 获取spu.id

            for spec_data in specs_data:
                spec = GoodsSpec(
                    spec_id=spec_data["spec_id"],
                    spu_id=spu.id,
                    title=spec_data["title"],
                    spec_values=json.dumps(spec_data["values"]),
                )
                session.add(spec)

            for sku_data in skus_data:
                sku = GoodsSku(
                    sku_id=sku_data["sku_id"],
                    spu_id=spu.id,
                    sku_image=sku_data["sku_image"],
                    price=sku_data["price"],
                    line_price=sku_data["line_price"],
                    stock_quantity=sku_data["stock_quantity"],
                    spec_info=json.dumps(sku_data["spec_info"]),
                )
                session.add(sku)

        # 添加种子评价数据
        comments_data = [
            {"spu_id": "0", "user_name": "Dean", "content": "收到货了，第一时间试了一下，很漂亮特别喜欢，大爱大爱，颜色也很好看。棒棒!",
             "score": 4, "user_id": "88881048075",
             "user_head_url": "https://wx.qlogo.cn/mmopen/vi_32/5mKrvn3ibyDNaDZSZics3aoKlz1cv0icqn4EruVm6gKjsK0xvZZhC2hkUkRWGxlIzOEc4600JkzKn9icOLE6zjgsxw/132"},
            {"spu_id": "135686633", "user_name": "Alice", "content": "质量很好，面料柔软舒适，穿起来很舒服，推荐购买！", "score": 5,
             "user_id": "88881048076",
             "user_head_url": "https://wx.qlogo.cn/mmopen/vi_32/default.png"},
            {"spu_id": "135686633", "user_name": "Bob", "content": "不错，颜色跟图片一样，尺码也合适", "score": 4,
             "user_id": "88881048077",
             "user_head_url": "https://wx.qlogo.cn/mmopen/vi_32/default.png"},
            {"spu_id": "135686623", "user_name": "Charlie", "content": "很好用的盒子，播放流畅，值得购买", "score": 5,
             "user_id": "88881048078",
             "user_head_url": "https://wx.qlogo.cn/mmopen/vi_32/default.png"},
        ]
        for c in comments_data:
            spu = session.query(GoodsSpu).filter(GoodsSpu.spu_id == c.pop("spu_id")).first()
            if spu:
                comment = GoodsComment(spu_id=spu.id, **c)
                session.add(comment)
