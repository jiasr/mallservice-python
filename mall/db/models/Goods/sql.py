"""商品数据访问层"""
import json
import uuid
import time
from datetime import datetime

from sqlalchemy import func, or_, and_
from mall.db.engines.mysql import get_session
from mall.db.models.Goods.model import (
    GoodsSpu, GoodsSku,GoodsSpec
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

    @classmethod
    def create_spu(cls, data):
        """Admin 端新增商品（SPU + 规格 + SKU）"""
        import uuid as _uuid
        session = get_session()
        with session.begin():
            spu_id = str(_uuid.uuid4().hex[:12])
            title = data.get("title", "").strip()
            if not title:
                return None, "商品标题不能为空"

            category_id = data.get("categoryId", "") or ""
            primary_image = data.get("primaryImage", "")
            images = json.dumps(data.get("images", [])) if data.get("images") else "[]"
            desc = json.dumps(data.get("desc", [])) if data.get("desc") else "[]"
            tags = json.dumps(data.get("tags", [])) if data.get("tags") else "[]"
            etitle = data.get("etitle", "")
            store_id = data.get("storeId", "1000")

            spu = GoodsSpu(
                id = uuid.uuid4().hex,
                spu_id=spu_id,
                title=title,
                etitle=etitle,
                primary_image=primary_image,
                images=images,
                desc=desc,
                category_id=category_id if category_id else None,
                min_sale_price=0,
                max_sale_price=0,
                min_line_price=0,
                max_line_price=0,
                stock_quantity=0,
                sold_num=0,
                is_put_on_sale=int(data.get("isPutOnSale", 0)),
                tags=tags,
                store_id=store_id,
            )
            session.add(spu)
            session.flush()

            min_price = None
            max_price = None
            min_lprice = None
            max_lprice = None
            total_stock = 0

            # 保存规格
            specs_data = data.get("specs", [])
            spec_id_map = {}
            for s in specs_data:
                spec_id = s.get("specId") or str(_uuid.uuid4().hex[:10])
                spec = GoodsSpec(
                    id = uuid.uuid4().hex,
                    spec_id=spec_id,
                    spu_id=spu.id,
                    title=s.get("title", ""),
                    spec_values=json.dumps(s.get("values", [])),
                )
                session.add(spec)
                spec_id_map[s.get("title", "")] = spec

            # 保存 SKU
            skus_data = data.get("skus", [])
            for sk in skus_data:
                sku_id = sk.get("skuId") or str(_uuid.uuid4().hex[:12])
                price = int(sk.get("price", 0))
                line_price = int(sk.get("linePrice", 0))
                stock = int(sk.get("stockQuantity", 0))
                spec_info = sk.get("specInfo", [])

                if min_price is None or price < min_price:
                    min_price = price
                if max_price is None or price > max_price:
                    max_price = price
                if min_lprice is None or line_price < min_lprice:
                    min_lprice = line_price
                if max_lprice is None or line_price > max_lprice:
                    max_lprice = line_price
                total_stock += stock

                sku = GoodsSku(
                    id=uuid.uuid4().hex,
                    sku_id=sku_id,
                    spu_id=spu.id,
                    sku_image=sk.get("skuImage", ""),
                    price=price,
                    line_price=line_price,
                    stock_quantity=stock,
                    spec_info=json.dumps(spec_info),
                )
                session.add(sku)

            # 回写 SPU 价格/库存汇总
            spu.min_sale_price = min_price or 0
            spu.max_sale_price = max_price or 0
            spu.min_line_price = min_lprice or 0
            spu.max_line_price = max_lprice or 0
            spu.stock_quantity = total_stock
            session.flush()

            return {"spuId": spu_id, "title": spu.title}, None