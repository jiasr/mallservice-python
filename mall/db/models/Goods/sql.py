"""商品数据访问层"""
import json
import uuid
import time
from datetime import datetime

from sqlalchemy import func, or_, and_
from mall.db.engines.mysql import get_session
from mall.db.models.Goods.model import (
    GoodsSpu, GoodsSku, GoodsSpec
)
from mall.db.models.GoodsCatalog.model import GoodsCatalog
from mall.db.models.Stock.sql import InvGoodsDao
from mall.common.constant import SETTING_LIST_DEFAILT_PAGESIZE
from mall.db.engines.s3 import get_image_display_url
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def _safe_json_loads(val, default=None):
    """安全解析 JSON 字符串"""
    if default is None:
        default = []
    if not val or not str(val).strip():
        return default
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


def _get_child_category_ids(session, parent_id):
    """递归获取某个分类的所有子孙分类 ID（包含自身）"""
    ids = [parent_id]
    children = session.query(GoodsCatalog.id).filter(
        GoodsCatalog.parentid == parent_id
    ).all()
    for (cid,) in children:
        ids.extend(_get_child_category_ids(session, cid))
    return ids


class GoodsSpuDao:
    """商品SPU数据访问"""

    @staticmethod
    def _img_url(path):
        """将相对路径转为完整公网 URL"""
        return get_image_display_url(path)

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
        sort_type = int(params.get("sort", 0))
        sort_direction = params.get("sortType", "0")
        min_price = params.get("minPrice")
        max_price = params.get("maxPrice")
        category_id = params.get("categoryId")
        status = params.get("isPutOnSale")

        with session.begin():
            query = session.query(GoodsSpu).filter(
                GoodsSpu.is_available == 1,
            )

            if status is not None and status != '':
                query = query.filter(GoodsSpu.is_put_on_sale == int(status))

            if keyword:
                query = query.filter(
                    or_(
                        GoodsSpu.title.like(f'%{keyword}%'),
                    )
                )

            # 级联分类：后端递归查找该分类及所有子孙分类 ID
            if category_id:
                all_ids = _get_child_category_ids(session, category_id)
                query = query.filter(GoodsSpu.category_id.in_(all_ids))

            if min_price is not None:
                query = query.filter(GoodsSpu.min_sale_price >= int(min_price))
            if max_price is not None and max_price != 'undefined':
                query = query.filter(GoodsSpu.max_sale_price <= int(max_price))

            if sort_type == 1:
                if sort_direction == '0':
                    query = query.order_by(GoodsSpu.min_sale_price.asc())
                else:
                    query = query.order_by(GoodsSpu.min_sale_price.desc())
            else:
                query = query.order_by(GoodsSpu.create_time.desc())

            total_count = query.count()
            start = (page_num - 1) * page_size
            spus = query.limit(page_size).offset(start).all()

            spu_list = []
            for spu in spus:
                imgs = _safe_json_loads(spu.images)
                tags = _safe_json_loads(spu.tags)
                # 轻量 SKU 列表，支持直接加购
                skus = session.query(GoodsSku).filter(GoodsSku.spu_id == spu.id).all()
                # 实时反查进销存商品信息（含名称与真实库存，按条码批量避免 N+1）
                inv_info_map = InvGoodsDao.get_inv_info_by_barcodes(
                    session, [s.barcode for s in skus]
                )
                sku_list = []
                for sku in skus:
                    spec_info = _safe_json_loads(sku.spec_info)
                    inv = inv_info_map.get(sku.barcode or '')
                    sku_list.append({
                        "skuId": sku.sku_id,
                        "specInfo": spec_info,
                        "price": sku.price,
                        "barcode": sku.barcode or "",
                        "stock": (inv['stock'] if inv else sku.stock_quantity),
                        "invName": (inv['name'] if inv else ''),
                        "thumb": cls._img_url(sku.sku_image) if sku.sku_image else "",
                    })
                spu_list.append({
                    "spuId": spu.spu_id,
                    "thumb": cls._img_url(imgs[0]) if imgs else "",
                    "title": spu.title,
                    "price": spu.min_sale_price,
                    "tags": [t.get("title", t) if isinstance(t, dict) else t for t in tags],
                    "desc": "",
                    "skuList": sku_list,
                })

            return {
                "pageNum": page_num,
                "pageSize": page_size,
                "totalCount": total_count,
                "spuList": spu_list,
            }

    @classmethod
    def get_simple_list(cls, page_index=1, page_size=20):
        """获取简单商品列表"""
        session = get_session()
        with session.begin():
            page_index = max(page_index, 1)
            start = (page_index - 1) * page_size
            spus = session.query(GoodsSpu).filter(
                GoodsSpu.is_put_on_sale == 1,
                GoodsSpu.is_available == 1,
            ).order_by(GoodsSpu.create_time.desc()).limit(page_size).offset(start).all()

            result = []
            for spu in spus:
                tags = _safe_json_loads(spu.tags)
                tags = _safe_json_loads(spu.tags)
                imgs = _safe_json_loads(spu.images)
                result.append({
                    "spuId": spu.spu_id,
                    "thumb": cls._img_url(imgs[0]) if imgs else "",
                    "title": spu.title,
                    "price": spu.min_sale_price,
                    "tags": [t.get("title", t) if isinstance(t, dict) else t for t in tags],
                })
            return result

    @classmethod
    def _format_spu_detail(cls, session, spu):
        """格式化SPU详情数据，匹配前端数据结构"""
        spec_list = []
        for spec in session.query(GoodsSpec).filter(GoodsSpec.spu_id == spu.id).all():
            spec_values = _safe_json_loads(spec.spec_values)
            spec_list.append({
                "specId": spec.spec_id,
                "title": spec.title,
                "specValueList": spec_values,
            })

        sku_list = []
        detail_skus = session.query(GoodsSku).filter(GoodsSku.spu_id == spu.id).all()
        # 实时反查进销存真实库存（按条码批量，避免 N+1）
        detail_inv_stock_map = InvGoodsDao.get_stock_by_barcodes(
            session, [s.barcode for s in detail_skus]
        )
        for sku in detail_skus:
            spec_info = _safe_json_loads(sku.spec_info)
            sku_list.append({
                "skuId": sku.sku_id,
                "skuImage": cls._img_url(sku.sku_image),
                "specInfo": spec_info,
                "priceInfo": [
                    {"priceType": 1, "price": str(sku.price), "priceTypeName": "销售价格"},
                ],
                "stockInfo": {
                    "stockQuantity": detail_inv_stock_map.get(sku.barcode or '', sku.stock_quantity),
                    "safeStockQuantity": 0,
                    "soldQuantity": sku.sold_quantity or 0,
                },
                "weight": {"value": sku.weight_value, "unit": sku.weight_unit},
                "volume": None,
                "profitPrice": None,
            })

        tags = _safe_json_loads(spu.tags)
        spu_tag_list = []
        for tag in tags:
            if isinstance(tag, dict):
                spu_tag_list.append(tag)
            else:
                spu_tag_list.append({"id": None, "title": tag, "image": None})

        limit_info = _safe_json_loads(getattr(spu, 'limit_info', None), None)

        images_raw = _safe_json_loads(spu.images)
        images = [cls._img_url(u) for u in images_raw]
        primary_img = images[0] if images else ""

        # 商品详情描述（富文本HTML或纯文本）
        detail_content = (spu.desc or '').strip()

        return {
            "saasId": "88888888",
            "storeId": spu.store_id or "1000",
            "spuId": spu.spu_id,
            "title": spu.title,
            "primaryImage": primary_img,
            "images": images,
            "available": spu.is_available,
            "minSalePrice": spu.min_sale_price,
            "maxSalePrice": spu.max_sale_price,
            "spuStockQuantity": sum(
                detail_inv_stock_map.get(s.barcode or '', s.stock_quantity) for s in detail_skus
            ),
            "soldNum": spu.sold_num,
            "isPutOnSale": spu.is_put_on_sale,
            "categoryIds": [],
            "specList": spec_list,
            "skuList": sku_list,
            "spuTagList": spu_tag_list,
            "limitInfo": limit_info,
            "desc": [],
            "detailContent": detail_content,
            "isSoldOut": spu.is_sold_out or False,
            "isAvailable": spu.is_available,
            "promotionList": None,
            "minProfitPrice": None,
            "groupIdList": [],
        }

    @classmethod
    def create_spu(cls, data):
        """Admin 端新增商品（SPU + 规格 + SKU）"""
        session = get_session()
        with session.begin():

            # 图片统一为 images[]，第一张作为主图
            all_images = data.get("images", []) or []
            images_json = json.dumps(all_images) if all_images else "[]"
            desc = data.get("detail", "")
            tags = json.dumps(data.get("tags", [])) if data.get("tags") else "[]"
            store_id = data.get("storeId", "")

            spu_id = uuid.uuid4().hex
            spu = GoodsSpu(
                id = spu_id,
                spu_id = spu_id,
                title=data.get("title", "").strip(),
                images=images_json,#图片/视频(JSON数组)
                desc=desc,#商品详情

                category_id= data.get("categoryId", ""),
                min_sale_price=0,
                max_sale_price=0,
                stock_quantity=0,
                sold_num=0,
                is_put_on_sale=int(data.get("isPutOnSale", 0)),
                is_available=1,
                tags=tags,
                store_id=store_id,
            )
            session.add(spu)
            session.flush()

            min_price = None
            max_price = None
            total_stock = 0

            # 保存规格
            specs_data = data.get("specs", [])
            spec_id_map = {}
            for s in specs_data:
                spec_dbid = uuid.uuid4().hex
                spec = GoodsSpec(
                    id = spec_dbid,
                    spec_id = spec_dbid,
                    spu_id=spu.id,
                    title=s.get("title", ""),
                    spec_values=json.dumps(s.get("values", [])),
                )
                session.add(spec)
                spec_id_map[s.get("title", "")] = spec

            # 保存 SKU
            skus_data = data.get("skus", [])
            for sk in skus_data:
                sku_id = sk.get("skuId")
                price = int(sk.get("price", 0))
                stock = int(sk.get("stockQuantity", 0))
                spec_info = sk.get("specInfo", [])

                if min_price is None or price < min_price:
                    min_price = price
                if max_price is None or price > max_price:
                    max_price = price
                total_stock += stock

                sku_dbid = uuid.uuid4().hex
                sku = GoodsSku(
                    id=sku_dbid,
                    sku_id=sku_dbid,
                    spu_id=spu.id,
                    sku_image=sk.get("skuImage", ""),
                    price=price,
                    barcode=sk.get("barcode", ""),
                    stock_quantity=stock,
                    spec_info=json.dumps(spec_info),
                )
                session.add(sku)

            # 回写 SPU 价格/库存汇总
            spu.min_sale_price = min_price or 0
            spu.max_sale_price = max_price or 0
            spu.stock_quantity = total_stock
            session.flush()

            return { "title": spu.title}, None

    @classmethod
    def update_spu(cls, id, data):
        """更新商品（SKU 按 skuId 匹配更新以保留已售数量，前端移除的 SKU 删除，规格重建）"""
        session = get_session()
        with session.begin():
            spu = session.query(GoodsSpu).filter(GoodsSpu.spu_id == id).first()
            if not spu:
                return {"success": False, "message": "商品不存在"}
            spu.title = data.get("title", spu.title)
            spu.category_id = data.get("categoryId", spu.category_id)
            spu.is_put_on_sale = data.get("isPutOnSale", spu.is_put_on_sale)
            images = data.get("images", [])
            if images:
                spu.images = json.dumps(images)
            spu.desc = data.get("detail", spu.desc)
            tags = data.get("tags", [])
            if tags:
                spu.tags = json.dumps(tags)

            # ===== 规格：重建（specId 每次由前端新生成，无法匹配，重建不涉及销量） =====
            session.query(GoodsSpec).filter(GoodsSpec.spu_id == spu.id).delete()
            specs_data = data.get("specs", [])
            for s in specs_data:
                spec_dbid = uuid.uuid4().hex
                spec = GoodsSpec(
                    id=spec_dbid,
                    spec_id=spec_dbid,
                    spu_id=spu.id,
                    title=s.get("title", ""),
                    spec_values=json.dumps(s.get("values", [])),
                )
                session.add(spec)

            # ===== SKU：按 skuId 匹配更新（保留 sold_quantity），新增添加，移除的删除 =====
            skus_data = data.get("skus", [])
            incoming_sku_ids = []
            min_price = None
            max_price = None
            total_stock = 0

            for sk in skus_data:
                sku_id = (sk.get("skuId") or '').strip()
                price = int(sk.get("price", 0))
                stock = int(sk.get("stockQuantity", 0))
                spec_info = sk.get("specInfo", [])

                if min_price is None or price < min_price:
                    min_price = price
                if max_price is None or price > max_price:
                    max_price = price
                total_stock += stock

                sku = None
                if sku_id:
                    sku = session.query(GoodsSku).filter(GoodsSku.sku_id == sku_id).first()
                if sku:
                    # 更新已存在 SKU，保留 sold_quantity
                    sku.price = price
                    sku.barcode = sk.get("barcode", "")
                    sku.stock_quantity = stock
                    sku.sku_image = sk.get("skuImage", "")
                    sku.spec_info = json.dumps(spec_info)
                else:
                    # 新增 SKU
                    sku_dbid = uuid.uuid4().hex
                    sku = GoodsSku(
                        id=sku_dbid,
                        sku_id=sku_dbid,
                        spu_id=spu.id,
                        sku_image=sk.get("skuImage", ""),
                        price=price,
                        barcode=sk.get("barcode", ""),
                        stock_quantity=stock,
                        spec_info=json.dumps(spec_info),
                    )
                    session.add(sku)

                if sku_id:
                    incoming_sku_ids.append(sku_id)

            # 删除前端已移除的 SKU（该 SPU 下不在传入列表中的）
            if incoming_sku_ids:
                session.query(GoodsSku).filter(
                    GoodsSku.spu_id == spu.id,
                    ~GoodsSku.sku_id.in_(incoming_sku_ids),
                ).delete(synchronize_session=False)
            else:
                # 传入为空时，清空该 SPU 下所有 SKU
                session.query(GoodsSku).filter(GoodsSku.spu_id == spu.id).delete(synchronize_session=False)

            # 回写 SPU 价格/库存汇总
            spu.min_sale_price = min_price or 0
            spu.max_sale_price = max_price or 0
            spu.stock_quantity = total_stock
            session.flush()
            return {"success": True}

    @classmethod
    def delete_spu(cls, id):
        """删除商品"""
        session = get_session()
        with session.begin():
            session.query(GoodsSku).filter(GoodsSku.spu_id == id).delete()
            session.query(GoodsSpec).filter(GoodsSpec.spu_id == id).delete()
            spu = session.query(GoodsSpu).filter(GoodsSpu.spu_id == id).first()
            if spu:
                session.delete(spu)
        return {"success": True}

    @classmethod
    def get_sku_by_barcode(cls, barcode):
        """根据条形码查询SKU（含SPU信息）"""
        session = get_session()
        with session.begin():
            sku = session.query(GoodsSku).filter(
                GoodsSku.barcode == barcode
            ).first()
            if not sku:
                return None
            spu = session.query(GoodsSpu).filter(
                GoodsSpu.id == sku.spu_id
            ).first()
            spec_info = _safe_json_loads(sku.spec_info)
            imgs = _safe_json_loads(spu.images) if spu else []
            inv_stock_map = InvGoodsDao.get_stock_by_barcodes(session, [sku.barcode])
            return {
                'skuId': sku.sku_id,
                'skuDbId': sku.id,
                'spuId': spu.spu_id if spu else '',
                'spuDbId': sku.spu_id,
                'spuTitle': spu.title if spu else '',
                'barcode': sku.barcode or '',
                'price': sku.price or 0,
                'stockQuantity': inv_stock_map.get(sku.barcode or '', sku.stock_quantity or 0),
                'specInfo': spec_info,
                'skuImage': sku.sku_image or '',
                'spuImage': cls._img_url(imgs[0]) if imgs else '',
            }

    @classmethod
    def get_sku_detail(cls, sku_id):
        """根据SKU ID查询SKU详情"""
        session = get_session()
        with session.begin():
            sku = session.query(GoodsSku).filter(
                GoodsSku.sku_id == sku_id
            ).first()
            if not sku:
                return None
            spu = session.query(GoodsSpu).filter(
                GoodsSpu.id == sku.spu_id
            ).first()
            spec_info = _safe_json_loads(sku.spec_info)
            imgs = _safe_json_loads(spu.images) if spu else []
            inv_stock_map = InvGoodsDao.get_stock_by_barcodes(session, [sku.barcode])
            return {
                'skuId': sku.sku_id,
                'skuDbId': sku.id,
                'spuId': spu.spu_id if spu else '',
                'spuDbId': sku.spu_id,
                'spuTitle': spu.title if spu else '',
                'barcode': sku.barcode or '',
                'price': sku.price or 0,
                'stockQuantity': inv_stock_map.get(sku.barcode or '', sku.stock_quantity or 0),
                'specInfo': spec_info,
                'skuImage': sku.sku_image or '',
                'spuImage': cls._img_url(imgs[0]) if imgs else '',
            }

    @classmethod
    def put_on_sale(cls, id):
        """上架"""
        session = get_session()
        with session.begin():
            spu = session.query(GoodsSpu).filter(GoodsSpu.spu_id == id).first()
            if spu:
                spu.is_put_on_sale = 1
        return {"success": True}

    @classmethod
    def pull_off_sale(cls, id):
        """下架"""
        session = get_session()
        with session.begin():
            spu = session.query(GoodsSpu).filter(GoodsSpu.spu_id == id).first()
            if spu:
                spu.is_put_on_sale = 0
        return {"success": True}