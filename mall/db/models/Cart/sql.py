"""购物车数据访问层"""
import json
from sqlalchemy import func
from mall.db.engines.mysql import get_session
from mall.db.models.Cart.model import Cart
from mall.db.models.Goods.model import GoodsSpu, GoodsSku
from mall.db.models.Stock.sql import InvGoodsDao
from mall.db.engines.s3 import get_image_display_url
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class CartDao:

    @staticmethod
    def _img_url(path):
        if not path:
            return ''
        images = json.loads(path) if path else []
        if isinstance(images, list) and len(images) > 0:
            return get_image_display_url(images[0])
        return get_image_display_url(path) if path else ''

    @classmethod
    def get_user_cart(cls, user_id):
        """获取用户购物车，同时校验商品有效性（批量查询避免 N+1）"""
        session = get_session()
        with session.begin():
            items = session.query(Cart).filter(Cart.user_id == user_id).all()
            if not items:
                return {'validItems': [], 'invalidItems': [], 'selectedPrice': 0, 'selectedCount': 0}

            # 批量查询 SPU / SKU / 进销存库存，避免逐条 N+1
            spu_ids = [it.spu_id for it in items]
            sku_ids = [it.sku_id for it in items]
            spu_map = {s.spu_id: s for s in
                       session.query(GoodsSpu).filter(GoodsSpu.spu_id.in_(spu_ids)).all()}
            sku_map = {s.sku_id: s for s in
                       session.query(GoodsSku).filter(GoodsSku.sku_id.in_(sku_ids)).all()}

            barcodes = [sku_map[sid].barcode for sid in sku_ids if sid in sku_map]
            inv_stock_map = InvGoodsDao.get_stock_by_barcodes(session, barcodes)

            valid_items = []
            invalid_items = []

            for item in items:
                spu = spu_map.get(item.spu_id)
                sku = sku_map.get(item.sku_id)

                # SKU 或 SPU 不存在 → 自动删除
                if not spu or not sku:
                    session.delete(item)
                    continue

                # 实时读取进销存真实库存（按条码反查，无匹配则退回 SKU 库存）
                real_stock = inv_stock_map.get(sku.barcode or '', sku.stock_quantity or 0)

                # SPU 下架
                if spu.is_put_on_sale == 0 or spu.is_available == 0:
                    invalid_items.append(cls._build_item(item, spu, sku, real_stock, '商品已下架'))
                    continue

                # 库存为 0
                if real_stock <= 0 or spu.is_sold_out:
                    invalid_items.append(cls._build_item(item, spu, sku, real_stock, '商品已售罄'))
                    continue

                # 数量超库存 → 修正
                if item.quantity > real_stock:
                    item.quantity = real_stock
                    session.flush()
                    if real_stock <= 0:
                        invalid_items.append(cls._build_item(item, spu, sku, real_stock, '库存不足'))
                    else:
                        valid_items.append(cls._build_item(item, spu, sku, real_stock))

                valid_items.append(cls._build_item(item, spu, sku, real_stock))

            selected_price = sum(it['price'] * it['quantity'] for it in valid_items if it.get('isSelected'))
            selected_count = sum(it['quantity'] for it in valid_items if it.get('isSelected'))

            return {
                'validItems': valid_items,
                'invalidItems': invalid_items,
                'selectedPrice': selected_price,
                'selectedCount': selected_count,
            }

    @classmethod
    def _build_item(cls, cart_item, spu, sku, real_stock=None, invalid_reason=None):
        """构建购物车项"""
        spec_info = json.loads(sku.spec_info) if sku.spec_info else []
        spec_label = '/'.join([s.get('specValues', s.get('specValue', '')) for s in spec_info])

        imgs = json.loads(spu.images) if spu.images else []
        thumb = get_image_display_url(imgs[0]) if imgs else ''

        if real_stock is None:
            real_stock = sku.stock_quantity or 0

        item = {
            'cartId': cart_item.id,
            'spuId': spu.spu_id,
            'skuId': sku.sku_id,
            'title': spu.title,
            'thumb': thumb,
            'specLabel': spec_label,
            'specInfo': spec_info,
            'price': sku.price,
            'stock': real_stock,
            'quantity': cart_item.quantity,
            'isSelected': bool(cart_item.is_selected),
        }
        if invalid_reason:
            item['invalidReason'] = invalid_reason
        return item

    @classmethod
    def add_to_cart(cls, user_id, spu_id, sku_id, quantity=1):
        """加入购物车（已存在则叠加数量）"""
        session = get_session()
        with session.begin():
            # 校验库存
            sku = session.query(GoodsSku).filter(GoodsSku.sku_id == sku_id).first()
            if not sku:
                return {'success': False, 'message': 'SKU不存在'}
            # 实时读取进销存真实库存
            inv_stock_map = InvGoodsDao.get_stock_by_barcodes(session, [sku.barcode])
            real_stock = inv_stock_map.get(sku.barcode or '', sku.stock_quantity or 0)
            if real_stock <= 0:
                return {'success': False, 'message': '商品已售罄'}

            existing = session.query(Cart).filter(
                Cart.user_id == user_id, Cart.sku_id == sku_id
            ).first()

            if existing:
                new_qty = existing.quantity + quantity
                if new_qty > real_stock:
                    return {'success': False, 'message': f'库存不足，最多可购买{real_stock}件'}
                existing.quantity = new_qty
            else:
                if quantity > real_stock:
                    return {'success': False, 'message': f'库存不足，最多可购买{real_stock}件'}
                cart_item = Cart(
                    user_id=user_id, spu_id=spu_id, sku_id=sku_id, quantity=quantity
                )
                session.add(cart_item)

            total = int(session.query(func.sum(Cart.quantity)).filter(Cart.user_id == user_id).scalar() or 0)
            return {'success': True, 'cartCount': total}

    @classmethod
    def update_cart(cls, user_id, data):
        """更新数量/选中状态"""
        session = get_session()
        with session.begin():
            cart_id = data.get('cartId')
            item = session.query(Cart).filter(
                Cart.id == cart_id, Cart.user_id == user_id
            ).first()
            if not item:
                return {'success': False, 'message': '购物车项不存在'}

            if 'quantity' in data:
                qty = int(data['quantity'])
                sku = session.query(GoodsSku).filter(GoodsSku.sku_id == item.sku_id).first()
                if qty <= 0:
                    session.delete(item)
                    return {'success': True}
                if sku:
                    # 实时读取进销存真实库存
                    inv_stock_map = InvGoodsDao.get_stock_by_barcodes(session, [sku.barcode])
                    real_stock = inv_stock_map.get(sku.barcode or '', sku.stock_quantity or 0)
                    if qty > real_stock:
                        return {'success': False, 'message': f'库存不足，最多可购买{real_stock}件'}
                item.quantity = qty

            if 'isSelected' in data:
                item.is_selected = 1 if data['isSelected'] else 0

            return {'success': True}

    @classmethod
    def delete_cart(cls, user_id, data):
        """删除购物车项"""
        session = get_session()
        with session.begin():
            cart_ids = data.get('cartIds') or [data.get('cartId')]
            for cid in cart_ids:
                item = session.query(Cart).filter(
                    Cart.id == cid, Cart.user_id == user_id
                ).first()
                if item:
                    session.delete(item)
            return {'success': True}

    @classmethod
    def clear_cart(cls, user_id):
        """清空购物车"""
        session = get_session()
        with session.begin():
            session.query(Cart).filter(Cart.user_id == user_id).delete()
            return {'success': True}
