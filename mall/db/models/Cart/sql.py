"""购物车数据访问层"""
import json
from sqlalchemy import func
from mall.db.engines.mysql import get_session
from mall.db.models.Cart.model import Cart
from mall.db.models.Goods.model import GoodsSpu, GoodsSku
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
        """获取用户购物车，同时校验商品有效性"""
        session = get_session()
        with session.begin():
            items = session.query(Cart).filter(Cart.user_id == user_id).all()

            valid_items = []
            invalid_items = []

            for item in items:
                spu = session.query(GoodsSpu).filter(GoodsSpu.spu_id == item.spu_id).first()
                sku = session.query(GoodsSku).filter(GoodsSku.sku_id == item.sku_id).first()

                # SKU 或 SPU 不存在 → 自动删除
                if not spu or not sku:
                    session.delete(item)
                    continue

                # SPU 下架
                if spu.is_put_on_sale == 0 or spu.is_available == 0:
                    invalid_items.append(cls._build_item(item, spu, sku, '商品已下架'))
                    continue

                # 库存为 0
                if sku.stock_quantity <= 0 or spu.is_sold_out:
                    invalid_items.append(cls._build_item(item, spu, sku, '商品已售罄'))
                    continue

                # 数量超库存 → 修正
                if item.quantity > sku.stock_quantity:
                    item.quantity = sku.stock_quantity
                    session.flush()
                    if sku.stock_quantity <= 0:
                        invalid_items.append(cls._build_item(item, spu, sku, '库存不足'))
                    else:
                        valid_items.append(cls._build_item(item, spu, sku))

                valid_items.append(cls._build_item(item, spu, sku))

            selected_price = sum(it['price'] * it['quantity'] for it in valid_items if it.get('isSelected'))
            selected_count = sum(it['quantity'] for it in valid_items if it.get('isSelected'))

            return {
                'validItems': valid_items,
                'invalidItems': invalid_items,
                'selectedPrice': selected_price,
                'selectedCount': selected_count,
            }

    @classmethod
    def _build_item(cls, cart_item, spu, sku, invalid_reason=None):
        """构建购物车项"""
        spec_info = json.loads(sku.spec_info) if sku.spec_info else []
        spec_label = '/'.join([s.get('specValues', s.get('specValue', '')) for s in spec_info])

        imgs = json.loads(spu.images) if spu.images else []
        thumb = get_image_display_url(imgs[0]) if imgs else ''

        item = {
            'cartId': cart_item.id,
            'spuId': spu.spu_id,
            'skuId': sku.sku_id,
            'title': spu.title,
            'thumb': thumb,
            'specLabel': spec_label,
            'specInfo': spec_info,
            'price': sku.price,
            'stock': sku.stock_quantity,
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
            if sku.stock_quantity <= 0:
                return {'success': False, 'message': '商品已售罄'}

            existing = session.query(Cart).filter(
                Cart.user_id == user_id, Cart.sku_id == sku_id
            ).first()

            if existing:
                new_qty = existing.quantity + quantity
                if new_qty > sku.stock_quantity:
                    return {'success': False, 'message': f'库存不足，最多可购买{sku.stock_quantity}件'}
                existing.quantity = new_qty
            else:
                if quantity > sku.stock_quantity:
                    return {'success': False, 'message': f'库存不足，最多可购买{sku.stock_quantity}件'}
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
                if sku and qty > sku.stock_quantity:
                    return {'success': False, 'message': f'库存不足，最多可购买{sku.stock_quantity}件'}
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
